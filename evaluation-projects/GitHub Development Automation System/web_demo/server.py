"""Web interface for devbot (GitHub Development Automation System), added by the LTID Assistant integration.

The devbot source in ../GitHub Development Automation System is NOT modified; this file imports and drives it.

What it does
  * Asks the user for THEIR OpenAI API key in the browser (optionally a GitHub token for cloning a private repository).
  * Runs devbot in DRY-RUN mode only: everything happens in a throw-away copy; nothing is pushed, merged or deployed.
  * Shows the plan and waits for the user to click Approve (or Reject) before any file is edited.

Secrets
  * Keys arrive in the JSON body of a request, live only in memory for the length of that run, are never written to disk,
    never put in the environment of the test subprocess, never logged, and are scrubbed from every message sent back.
  * The server never falls back to an OPENAI_API_KEY / GITHUB_TOKEN set in its own environment.

Standard library only (devbot needs git on PATH).   python server.py     (HOST / PORT from the environment)
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PROJECT = Path(os.environ.get("DEVBOT_PROJECT_DIR") or HERE.parent / "GitHub Development Automation System").resolve()
STATIC = HERE / "static"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "demo"))
os.environ["GIT_TERMINAL_PROMPT"] = "0"          # a private/missing repo must fail, never wait for a password

from devbot import analyzer, planner                                   # noqa: E402
from devbot.git_ops import parse_github_slug                           # noqa: E402
from devbot.llm import MockLLM, OpenAILLM                              # noqa: E402
from devbot.pipeline import Options, run                               # noqa: E402
from devbot.safety import SafetyError, check_git_args                  # noqa: E402
import make_demo_repo                                                  # noqa: E402

OPENAI_BASE = os.environ.get("DEVBOT_WEB_OPENAI_BASE_URL", "https://api.openai.com/v1")  # tests point this at a fake
DEFAULT_MODEL = "gpt-4o-mini"
DEMO_REQUEST = "Add a 10% bulk discount to calculate_total for orders of 10 or more books, and add tests"
MAX_BODY = 64 * 1024
MAX_REQUEST_CHARS = 2000
MAX_LOG_LINES = 1500
MAX_REPO_BYTES = 50 * 1024 * 1024
CLONE_TIMEOUT = int(os.environ.get("DEVBOT_WEB_CLONE_TIMEOUT", "120"))
APPROVAL_TIMEOUT = int(os.environ.get("DEVBOT_WEB_APPROVAL_TIMEOUT", "900"))
KEEP_JOBS = 10
GITHUB_URL = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]{1,100})/([A-Za-z0-9_.-]{1,100}?)(?:\.git)?/?$")
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "host.docker.internal"} | \
    {h.strip().lower() for h in os.environ.get("DEVBOT_WEB_ALLOWED_HOSTS", "").split(",") if h.strip()}

SECRET_PATTERNS = [re.compile(p) for p in (
    r"sk-[A-Za-z0-9_\-*.]{6,}", r"gh[pousr]_[A-Za-z0-9]{16,}", r"github_pat_[A-Za-z0-9_]{16,}",
    r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}", r"(?i)basic\s+[A-Za-z0-9+/=]{16,}")]


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class LLMError(Exception):
    """A readable, secret-free description of a model/API failure."""


def make_redactor(*secrets: str):
    """Return a function that scrubs the given secrets (and anything shaped like a key/token) from text."""
    plain = [s for s in secrets if s]
    extra = []
    for s in plain:
        extra.append(base64.b64encode(f"x-access-token:{s}".encode()).decode())
    needles = sorted(set(plain + extra), key=len, reverse=True)

    def redact(text: str) -> str:
        text = text if isinstance(text, str) else str(text)
        for n in needles:
            text = text.replace(n, "[hidden]")
        for pat in SECRET_PATTERNS:
            text = pat.sub("[hidden]", text)
        return text
    return redact


# --------------------------------------------------------------------------------------------- LLM wrapper
class FriendlyLLM:
    """Wraps the real OpenAILLM so API failures become short messages that never contain the key."""

    def __init__(self, inner, redact):
        self.inner, self.redact, self.name = inner, redact, inner.name

    def complete_json(self, task, system, user):
        try:
            return self.inner.complete_json(task, system, user)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                err = json.loads(e.read().decode("utf-8", "replace")).get("error", {})
                detail = err.get("message") or err.get("code") or ""
            except Exception:                                   # noqa: BLE001
                pass
            hint = {401: "OpenAI rejected the API key (401). Check that you pasted a valid key.",
                    403: "OpenAI refused the request (403): the key may not have access to this model.",
                    404: "OpenAI could not find that model or endpoint (404). Check the model name.",
                    429: "OpenAI rate limit or quota reached (429)."}.get(e.code, f"OpenAI returned HTTP {e.code}.")
            raise LLMError(self.redact(f"{hint} {detail}".strip())[:300]) from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            raise LLMError(self.redact(f"Could not reach the OpenAI API: {getattr(e, 'reason', e)}")[:300]) from None
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise LLMError(f"The model's reply for the '{task}' step was not valid JSON in the expected shape. "
                           "Try again or choose another model.") from None


# --------------------------------------------------------------------------------------------- repositories
def _auth_flags(token: str | None) -> list[str]:
    if not token:
        return []
    b = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {b}"]


def _dir_size(path: Path) -> int:
    total = 0
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            try:
                total += (Path(dp) / f).stat().st_size
            except OSError:
                pass
    return total


def shallow_clone(url: str, dest: Path, token: str | None, redact) -> None:
    args = ["clone", "--depth", "1", url, str(dest)]
    check_git_args(args)
    try:
        r = subprocess.run(["git", *_auth_flags(token), *args], capture_output=True, text=True, timeout=CLONE_TIMEOUT)
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        raise ApiError(400, "clone_timeout", f"Cloning took longer than {CLONE_TIMEOUT}s and was stopped.") from None
    except FileNotFoundError:
        raise ApiError(500, "git_missing", "git is not installed on the server.") from None
    if r.returncode:
        shutil.rmtree(dest, ignore_errors=True)
        msg = redact((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "clone failed")
        raise ApiError(400, "clone_failed", f"Could not clone {url}: {msg}. For a private repository add a GitHub token.")
    if _dir_size(dest) > MAX_REPO_BYTES:
        shutil.rmtree(dest, ignore_errors=True)
        raise ApiError(400, "repo_too_large", "That repository is larger than 50 MB; devbot's web interface will not take it.")


def prepare_repo(source: str, repo_url: str, token: str | None, work: Path, redact) -> Path:
    if source == "demo":
        return make_demo_repo.main(str(work / "bookshop-api"))
    return_path = work / "clone"
    shallow_clone(repo_url, return_path, token, redact)
    return return_path


# --------------------------------------------------------------------------------------------- request validation
def _clean(body: dict) -> dict:
    """Validate a request body shared by analyze/run. Returns normalised fields (secrets included, kept in memory)."""
    if not isinstance(body, dict):
        raise ApiError(400, "bad_request", "The request body must be a JSON object.")
    source = body.get("source", "demo")
    if source not in ("demo", "github"):
        raise ApiError(400, "bad_source", "source must be 'demo' or 'github'.")
    repo_url = (body.get("repo_url") or "").strip()
    if source == "github":
        m = GITHUB_URL.match(repo_url)
        if not m:
            raise ApiError(400, "bad_repo_url", "Enter a repository address like https://github.com/owner/name "
                                                "(only github.com HTTPS addresses are accepted; local paths are not).")
        if not body.get("trust_confirmed"):
            raise ApiError(400, "trust_required", "Tick the box confirming you trust this repository: devbot runs its "
                                                  "tests, and tests are arbitrary code.")
    key = body.get("openai_key") or ""
    token = body.get("github_token") or ""
    for label, val in (("OpenAI API key", key), ("GitHub token", token)):
        if not isinstance(val, str) or len(val) > 300 or re.search(r"\s", val.strip()) or not val.isprintable():
            raise ApiError(400, "bad_secret", f"The {label} looks malformed (spaces or unusual characters).")
    model = (body.get("model") or DEFAULT_MODEL).strip()
    if not re.fullmatch(r"[A-Za-z0-9._:\-]{1,64}", model):
        raise ApiError(400, "bad_model", "The model name may only contain letters, digits, '.', '-', '_' and ':'.")
    return {"source": source, "repo_url": repo_url, "key": key.strip(), "token": token.strip(), "model": model}


# --------------------------------------------------------------------------------------------- jobs
class Job:
    def __init__(self, mode: str, source: str, request: str):
        self.id = uuid.uuid4().hex[:12]
        self.mode, self.source, self.request = mode, source, request
        self.status = "running"      # running | awaiting_approval | done | safety_stop | error
        self.log: list[str] = []
        self.plan = ""
        self.result: dict | None = None
        self.error = ""
        self.started = time.time()
        self.finished: float | None = None
        self._approval = threading.Event()
        self._approved = False
        self._lock = threading.Lock()

    def add_log(self, text: str) -> None:
        with self._lock:
            for line in str(text).splitlines() or [""]:
                if len(self.log) < MAX_LOG_LINES:
                    self.log.append(line)
                elif len(self.log) == MAX_LOG_LINES:
                    self.log.append("... (log truncated)")

    def decide(self, approved: bool) -> bool:
        with self._lock:
            if self.status != "awaiting_approval":
                return False
            self._approved = approved
        self._approval.set()
        return True

    def to_dict(self, since: int = 0) -> dict:
        with self._lock:
            return {"id": self.id, "status": self.status, "mode": self.mode, "source": self.source,
                    "request": self.request, "plan": self.plan, "result": self.result, "error": self.error,
                    "log": self.log[since:], "log_total": len(self.log),
                    "elapsed_s": round((self.finished or time.time()) - self.started, 1)}


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()
ACTIVE: list[str] = []          # at most one running job at a time


def _read_limited(path: str, limit: int = 60000) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def _execute(job: Job, fields: dict, request: str, max_repairs: int) -> None:
    redact = make_redactor(fields["key"], fields["token"])
    work = Path(tempfile.mkdtemp(prefix="devbot-web-"))
    log = lambda s: job.add_log(redact(s))                                  # noqa: E731
    try:
        if job.mode == "mock":
            llm = MockLLM.from_file(PROJECT / "demo" / "demo_script.py")
        else:
            llm = FriendlyLLM(OpenAILLM(api_key=fields["key"], model=fields["model"], base_url=OPENAI_BASE), redact)
        repo = prepare_repo(fields["source"], fields["repo_url"], fields["token"] or None, work, redact)
        log(f"repository ready ({'built-in fictional bookshop-api' if fields['source'] == 'demo' else fields['repo_url']})")

        def approve(plan_text: str) -> bool:
            with job._lock:
                job.plan = redact(plan_text)
                job.status = "awaiting_approval"
            job.add_log("-- waiting for your approval of the plan (nothing has been changed yet) --")
            got = job._approval.wait(APPROVAL_TIMEOUT)
            with job._lock:
                ok = got and job._approved
                job.status = "running"
            job.add_log("plan approved by you" if ok else ("plan rejected by you" if got else "approval timed out"))
            return ok

        opts = Options(repo=str(repo), request=request, live=False, auto_approve=False, max_repairs=max_repairs,
                       out_dir=work / "out", allow_repos=[], token=fields["token"] or None)
        res = run(opts, llm, log=log, approve=approve)
        result = {"status": res.status, "branch": res.branch, "files_changed": res.files_changed,
                  "tests_ok": res.tests_ok, "repairs_used": res.repairs_used, "mode": "dry-run",
                  "pr_preview": redact(_read_limited(res.pr_location)) if res.pr_location else "",
                  "diff": "", "note": "Dry-run: the original repository was not changed and nothing was pushed."}
        if res.report_path:
            try:
                result["diff"] = redact(json.loads(Path(res.report_path).read_text(encoding="utf-8")).get("diff", ""))[:60000]
            except (OSError, ValueError):
                pass
        with job._lock:
            job.result, job.status = result, "done"
    except SafetyError as e:
        with job._lock:
            job.error, job.status = redact(f"Safety stop: {e}"), "safety_stop"
    except ApiError as e:
        with job._lock:
            job.error, job.status = e.message, "error"
    except LLMError as e:
        with job._lock:
            job.error, job.status = str(e), "error"
    except Exception as e:                                                  # noqa: BLE001
        with job._lock:
            job.error, job.status = redact(f"{type(e).__name__}: {e}")[:400], "error"
    finally:
        fields["key"] = fields["token"] = ""                                 # drop our references to the secrets
        shutil.rmtree(work, ignore_errors=True)
        job.finished = time.time()
        with JOBS_LOCK:
            if job.id in ACTIVE:
                ACTIVE.remove(job.id)


def start_run(body: dict) -> Job:
    fields = _clean(body)
    mode = body.get("mode", "mock")
    if mode not in ("mock", "openai"):
        raise ApiError(400, "bad_mode", "mode must be 'mock' (offline demo) or 'openai'.")
    request = (body.get("request") or "").strip()
    if not request:
        raise ApiError(400, "empty_request", "Describe the change you want first.")
    if len(request) > MAX_REQUEST_CHARS:
        raise ApiError(400, "request_too_long", f"Keep the request under {MAX_REQUEST_CHARS} characters.")
    if mode == "mock" and fields["source"] != "demo":
        raise ApiError(400, "mock_needs_demo_repo", "The offline demo is scripted for the built-in bookshop-api repository "
                                                    "only. Choose that repository, or use GPT with your own key.")
    if mode == "openai" and not fields["key"]:
        raise ApiError(400, "api_key_required", "Enter your OpenAI API key to use GPT (or switch to the offline demo).")
    try:
        max_repairs = max(0, min(3, int(body.get("max_repairs", 2))))
    except (TypeError, ValueError):
        raise ApiError(400, "bad_max_repairs", "max_repairs must be a number from 0 to 3.") from None
    with JOBS_LOCK:
        if ACTIVE:
            raise ApiError(409, "busy", "A run is already in progress. Wait for it to finish (or reject its plan).")
        job = Job(mode, fields["source"], request)
        JOBS[job.id] = job
        ACTIVE.append(job.id)
        for old in [j for j in JOBS.values() if j.finished][:-KEEP_JOBS]:
            JOBS.pop(old.id, None)
    threading.Thread(target=_execute, args=(job, fields, request, max_repairs), daemon=True).start()
    return job


def do_analyze(body: dict) -> dict:
    fields = _clean(body)
    redact = make_redactor(fields["key"], fields["token"])
    work = Path(tempfile.mkdtemp(prefix="devbot-web-an-"))
    try:
        repo = prepare_repo(fields["source"], fields["repo_url"], fields["token"] or None, work, redact)
        rep = analyzer.analyze(repo)
        out = {"languages": rep.languages, "frameworks": rep.frameworks, "package_managers": rep.package_managers,
               "dev_tools": rep.dev_tools, "key_files": rep.key_files[:40], "test_command": " ".join(
                   "python" if c == sys.executable else c for c in rep.test_command),
               "file_count": len(rep.files), "tree": rep.tree[:6000], "overview": "", "overview_source": "none"}
        if fields["key"]:
            llm = FriendlyLLM(OpenAILLM(api_key=fields["key"], model=fields["model"], base_url=OPENAI_BASE), redact)
            try:
                out["overview"] = redact(planner.explain_repo(llm, rep, analyzer.read_source_context(repo, rep.files)))
                out["overview_source"] = llm.name
            except LLMError as e:
                out["overview_error"] = str(e)
        return out
    except SafetyError as e:
        raise ApiError(400, "safety_stop", redact(str(e))) from None
    finally:
        fields["key"] = fields["token"] = ""
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------------------------- HTTP
def config() -> dict:
    git = shutil.which("git")
    return {"title": "devbot – GitHub Development Automation System", "demo_request": DEMO_REQUEST,
            "default_model": DEFAULT_MODEL, "git_available": bool(git), "live_mode": False,
            "openai_endpoint": OPENAI_BASE, "key_policy": "Your key is kept in this browser tab's memory and sent only "
            "with your own requests; the server never stores or logs it and does not use any key of its own.",
            "max_repairs": 3, "approval_timeout_s": APPROVAL_TIMEOUT}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "devbot-web"

    def log_message(self, fmt, *args):                       # request lines only (never bodies); keep stderr quiet
        if os.environ.get("DEVBOT_WEB_VERBOSE"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, payload, ctype="application/json; charset=utf-8", head=False):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                    "script-src 'self'; connect-src 'self'; img-src 'self' data:")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _error(self, e: ApiError):
        self._send(e.status, {"error": {"code": e.code, "message": e.message}})

    def _read_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:                                      # drain so the connection is not reset on Windows
            remaining = n
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            raise ApiError(413, "too_large", "Request body is too large.")
        return self.rfile.read(n) if n else b""

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        host = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        return host in ALLOWED_HOSTS

    def _dispatch(self, method: str):
        try:
            body_bytes = self._read_body() if method in ("POST", "PUT", "DELETE", "PATCH") else b""  # always read first
            if not self._host_ok():
                raise ApiError(403, "bad_host", "Unexpected Host header.")
            path = urlparse(self.path).path
            if method in ("GET", "HEAD"):
                return self._get(path, urlparse(self.path).query, head=(method == "HEAD"))
            if method == "POST":
                return self._post(path, body_bytes)
            self.send_response(405)
            self.send_header("Allow", "GET, HEAD, POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
        except ApiError as e:
            self._error(e)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:                                # noqa: BLE001
            self._error(ApiError(500, "internal_error", f"{type(e).__name__}"))

    do_GET = lambda self: self._dispatch("GET")                # noqa: E731
    do_HEAD = lambda self: self._dispatch("HEAD")              # noqa: E731
    do_POST = lambda self: self._dispatch("POST")              # noqa: E731
    do_PUT = lambda self: self._dispatch("PUT")                # noqa: E731
    do_DELETE = lambda self: self._dispatch("DELETE")          # noqa: E731
    do_PATCH = lambda self: self._dispatch("PATCH")            # noqa: E731

    def _get(self, path: str, query: str, head: bool):
        if path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8", head)
        if path == "/app.js":
            return self._send(200, (STATIC / "app.js").read_bytes(), "text/javascript; charset=utf-8", head)
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon", head)
        if path == "/api/health":
            return self._send(200, {"status": "ok", "project": "devbot", "git": bool(shutil.which("git"))}, head=head)
        if path == "/api/config":
            return self._send(200, config(), head=head)
        m = re.fullmatch(r"/api/runs/([0-9a-f]{12})", path)
        if m:
            job = JOBS.get(m.group(1))
            if not job:
                raise ApiError(404, "no_such_run", "That run does not exist (the server may have restarted).")
            since = 0
            for kv in query.split("&"):
                if kv.startswith("since=") and kv[6:].isdigit():
                    since = int(kv[6:])
            return self._send(200, job.to_dict(since), head=head)
        raise ApiError(404, "not_found", "Unknown path.")

    def _post(self, path: str, raw: bytes):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ApiError(415, "json_required", "Send the request as application/json.")
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "bad_json", "The request body is not valid JSON.") from None
        if path == "/api/analyze":
            return self._send(200, do_analyze(body))
        if path == "/api/runs":
            return self._send(202, start_run(body).to_dict())
        m = re.fullmatch(r"/api/runs/([0-9a-f]{12})/(approve|reject)", path)
        if m:
            job = JOBS.get(m.group(1))
            if not job:
                raise ApiError(404, "no_such_run", "That run does not exist.")
            if not job.decide(m.group(2) == "approve"):
                raise ApiError(409, "not_waiting", "This run is not waiting for approval.")
            return self._send(200, {"ok": True})
        raise ApiError(404, "not_found", "Unknown path.")


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    return Server((host, port), Handler)


def main() -> int:
    host, port = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8009"))
    if not (PROJECT / "devbot").is_dir():
        print(f"devbot source not found at {PROJECT}", file=sys.stderr)
        return 2
    srv = make_server(host, port)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=srv.shutdown, daemon=True).start())
    print(f"devbot web interface on http://{host}:{port}  (dry-run only; keys come from the browser)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
