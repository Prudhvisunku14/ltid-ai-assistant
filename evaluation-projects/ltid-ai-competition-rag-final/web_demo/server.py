"""Web interface and JSON API for the LTID AI Competition RAG project (../prompt-c-rag).

This layer only ADDS a browser front end. Every answer comes from the project's own `rag_app` package
(BM25 retrieval, version resolution, citations, abstention); nothing is mocked and the project's code is not
modified. Standard library only.

  GET  /                       the web interface
  GET  /api/health             liveness
  GET  /api/config             retrieval method, upload limits, whether an LLM is configured
  GET  /api/examples           the project's own acceptance questions
  GET  /api/documents          every ingested document with version/status and whether it was uploaded
  POST /api/ask                {"question": "...", "use_llm": false}  -> answer, citations, notes
  POST /api/documents          {"filename": "x.txt", "content": "..."} -> adds a .txt/.md document and re-indexes
  DELETE /api/documents/<name> removes an UPLOADED document (shipped knowledge-base files cannot be removed)
  POST /api/reset              drops every uploaded document

Uploaded documents live in a per-process temporary folder, never inside the project, and disappear on restart.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import sys
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / "prompt-c-rag"
sys.path.insert(0, str(PROJECT))

from rag_app.__main__ import DEMO_QUESTIONS            # noqa: E402  (the project's own acceptance questions)
from rag_app.answer import answer_question, openai_compatible_llm  # noqa: E402
from rag_app.ingest import SUPPORTED_SUFFIXES            # noqa: E402
from rag_app.retrieve import Index                      # noqa: E402

log = logging.getLogger("rag_web")
MAX_BODY = 1_000_000          # bytes accepted in one request
MAX_CONTENT_CHARS = 200_000   # characters accepted for one uploaded document
MAX_QUESTION_CHARS = 1_000
MAX_UPLOADS = 20
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()\-]{0,99}$")
METHOD = "BM25 keyword retrieval with stemming and synonyms; extractive answers. No embeddings and no vector database."


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class KnowledgeBase:
    """The shipped knowledge base plus any uploaded documents, indexed with the project's own Index."""

    def __init__(self, shipped: Path):
        self.shipped = Path(shipped)
        self.lock = threading.RLock()
        self.work = Path(tempfile.mkdtemp(prefix="rag-kb-"))
        self.uploaded: set[str] = set()
        self.shipped_names: set[str] = set()
        self.reset()

    def _copy_shipped(self) -> None:
        for p in self.work.iterdir():
            p.unlink()
        self.shipped_names = set()
        for p in sorted(self.shipped.iterdir()):
            if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES:
                shutil.copyfile(p, self.work / p.name)
                self.shipped_names.add(p.name)

    def reset(self) -> None:
        with self.lock:
            self._copy_shipped()
            self.uploaded = set()
            self.index = Index.from_folder(self.work)

    def add(self, filename, content) -> dict:
        if not isinstance(filename, str) or not NAME_RE.match(filename):
            raise ApiError(400, "invalid_filename", "File names may use letters, digits, spaces and . _ ( ) - only, and must not contain folders.")
        if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ApiError(400, "unsupported_type", f"Only {', '.join(sorted(SUPPORTED_SUFFIXES))} files are supported.")
        if not isinstance(content, str) or not content.strip():
            raise ApiError(400, "empty_document", "The document is empty.")
        if len(content) > MAX_CONTENT_CHARS:
            raise ApiError(413, "too_large", f"The document is longer than {MAX_CONTENT_CHARS:,} characters.")
        if "\x00" in content:
            raise ApiError(400, "not_text", "The file does not look like plain text.")
        with self.lock:
            if filename in self.shipped_names:
                raise ApiError(409, "name_taken", f"{filename} is part of the shipped knowledge base; choose another file name.")
            if filename not in self.uploaded and len(self.uploaded) >= MAX_UPLOADS:
                raise ApiError(409, "limit_reached", f"At most {MAX_UPLOADS} uploaded documents are kept; remove one first.")
            target = self.work / filename
            previous = target.read_bytes() if target.exists() else None
            target.write_text(content, encoding="utf-8")
            try:
                self.index = Index.from_folder(self.work)
            except Exception as exc:                     # roll back: a bad upload must not break the knowledge base
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(previous)
                self.index = Index.from_folder(self.work)
                raise ApiError(400, "ingest_failed", f"The document could not be ingested: {exc}")
            self.uploaded.add(filename)
            return self._describe(next(d for d in self.index.docs if d.filename == filename))

    def remove(self, filename: str) -> None:
        with self.lock:
            if filename in self.shipped_names:
                raise ApiError(403, "shipped_document", "Shipped knowledge-base documents cannot be removed.")
            if filename not in self.uploaded:
                raise ApiError(404, "not_found", f"No uploaded document named {filename}.")
            (self.work / filename).unlink(missing_ok=True)
            self.uploaded.discard(filename)
            self.index = Index.from_folder(self.work)

    def _describe(self, d) -> dict:
        n = sum(1 for c in self.index.chunks if c.filename == d.filename)
        return {"filename": d.filename, "title": d.title, "family": d.family, "version": d.version, "status": d.status,
                "effective": d.effective, "superseded_by": d.superseded_by, "passages": n,
                "uploaded": d.filename in self.uploaded}

    def documents(self) -> list:
        with self.lock:
            return [self._describe(d) for d in sorted(self.index.docs, key=lambda d: d.filename.lower())]

    def ask(self, question, use_llm: bool) -> dict:
        if not isinstance(question, str) or not question.strip():
            raise ApiError(400, "empty_question", "Please enter a question.")
        if len(question) > MAX_QUESTION_CHARS:
            raise ApiError(400, "question_too_long", f"Questions are limited to {MAX_QUESTION_CHARS} characters.")
        llm = None
        if use_llm:
            if not llm_configured():
                raise ApiError(400, "llm_not_configured",
                               "LLM rephrasing is not configured. Set OPENAI_API_KEY (or RAG_LLM_BASE_URL for a local "
                               "OpenAI-compatible server) and restart, or ask without the LLM option.")
            llm = openai_compatible_llm()
        with self.lock:
            index = self.index
        ans = answer_question(index, question.strip(), llm=llm)
        out = ans.to_dict()
        out["status"] = "answered" if ans.found else "not_found"
        out["generator"] = "extractive"
        if use_llm:                                     # report honestly which writer produced the text
            baseline = answer_question(index, question.strip())
            if ans.found and ans.text != baseline.text:
                out["generator"] = "llm"
            else:
                out["notes"] = list(out["notes"]) + ["The LLM was not used for this answer (no evidence, unreachable, or its output "
                                                      "was rejected for citing an unknown file); the extractive answer is shown."]
        return out


def llm_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("RAG_LLM_BASE_URL"))


def make_handler(kb: KnowledgeBase):
    index_html = (HERE / "static" / "index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        server_version = "LtidRagWeb/1.0"

        def _send(self, status: int, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload):
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _read_body(self) -> None:
            """Read the whole request body BEFORE answering. Replying while unread bytes remain and then closing the
            socket makes Windows reset the connection, so the client may never see the reply."""
            self._raw, self._too_large, self._bad_length = b"", False, False
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._bad_length = True
                return
            if n <= 0:
                return
            self._raw = self.rfile.read(min(n, MAX_BODY))
            if n > MAX_BODY:
                self._too_large = True
                left = min(n - MAX_BODY, 50_000_000)          # discard the rest (bounded) so the reply can be delivered
                while left > 0:
                    chunk = self.rfile.read(min(65536, left))
                    if not chunk:
                        break
                    left -= len(chunk)

        def _body(self) -> dict:
            if self._bad_length:
                raise ApiError(400, "bad_request", "Invalid Content-Length.")
            if self._too_large:
                raise ApiError(413, "too_large", f"Requests are limited to {MAX_BODY:,} bytes.")
            try:
                data = json.loads(self._raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ApiError(400, "bad_json", "The request body must be valid UTF-8 JSON.")
            if not isinstance(data, dict):
                raise ApiError(400, "bad_json", "The request body must be a JSON object.")
            return data

        def _route(self, method: str):
            path = urlparse(self.path).path
            if method in ("GET", "HEAD"):
                if path in ("/", "/index.html"):
                    return self._send(200, index_html, "text/html; charset=utf-8")
                if path == "/favicon.ico":
                    return self._send(204, b"", "image/x-icon")
                if path == "/api/health":
                    return self._json(200, {"status": "ok", "app": "ltid-rag-web", "documents": len(kb.documents())})
                if path == "/api/config":
                    return self._json(200, {"title": "LTID AI Competition – RAG", "retrieval": METHOD, "llm_configured": llm_configured(),
                                            "supported_types": sorted(SUPPORTED_SUFFIXES), "max_upload_chars": MAX_CONTENT_CHARS,
                                            "max_uploads": MAX_UPLOADS, "fictional_data": True})
                if path == "/api/examples":
                    return self._json(200, {"questions": DEMO_QUESTIONS})
                if path == "/api/documents":
                    return self._json(200, {"documents": kb.documents()})
            elif method == "POST":
                if path == "/api/ask":
                    b = self._body()
                    return self._json(200, kb.ask(b.get("question"), bool(b.get("use_llm"))))
                if path == "/api/documents":
                    b = self._body()
                    return self._json(201, kb.add(b.get("filename"), b.get("content")))
                if path == "/api/reset":
                    kb.reset()
                    return self._json(200, {"documents": kb.documents()})
            elif method == "DELETE" and path.startswith("/api/documents/"):
                kb.remove(unquote(path[len("/api/documents/"):]))
                return self._json(200, {"documents": kb.documents()})
            raise ApiError(404, "not_found", "Not found")

        def _handle(self, method: str):
            try:
                if method != "GET" and method != "HEAD":
                    self._read_body()
                if method in ("PUT", "PATCH"):
                    self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
                    self.send_header("Allow", "GET, HEAD, POST, DELETE")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self._route(method)
            except ApiError as e:
                self._json(e.status, {"error": {"code": e.code, "message": e.message}})
            except BrokenPipeError:
                pass
            except Exception:                              # never leak a traceback
                log.exception("unhandled error for %s %s", method, self.path)
                self._json(500, {"error": {"code": "internal_error", "message": "Unexpected server error."}})

        def do_GET(self): self._handle("GET")        # noqa: N802,E704
        def do_HEAD(self): self._handle("HEAD")      # noqa: N802,E704
        def do_POST(self): self._handle("POST")      # noqa: N802,E704
        def do_DELETE(self): self._handle("DELETE")  # noqa: N802,E704

        def do_PUT(self): self._handle("PUT")        # noqa: N802,E704
        def do_PATCH(self): self._handle("PATCH")    # noqa: N802,E704

        def log_message(self, fmt, *args):
            log.info("%s - %s", self.address_string(), fmt % args)

    return Handler


def create_server(host: str, port: int, kb: KnowledgeBase | None = None) -> ThreadingHTTPServer:
    kb = kb or KnowledgeBase(PROJECT / "knowledge_base")
    return ThreadingHTTPServer((host, port), make_handler(kb))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8008"))
    httpd = create_server(host, port)
    print(f"LTID AI Competition - RAG running at http://{host}:{port}/  (LLM configured: {llm_configured()})", flush=True)
    # `docker stop` sends SIGTERM; as PID 1 Python ignores it, so Docker waits 10 s and kills the container (exit 137).
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=httpd.shutdown, daemon=True).start())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
