import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .service import compare_versions, scan_all
from .sources import make_source
from .store import Store

STATIC = Path(__file__).parent / "static"

def make_handler(src, store):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, code, body, ctype="application/json"):
            b = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/": return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
                if u.path == "/api/documents": return self._send(200, {"source": src.name, "documents": src.documents()})
                if u.path == "/api/history": return self._send(200, store.history())
                if u.path == "/api/history/item":
                    r = store.get(int(q["id"])); return self._send(200 if r else 404, r or {"error": "not found"})
                if u.path == "/api/compare":
                    r = compare_versions(src, q["doc"], q["a"], q["b"]); store.save(q["doc"], q["a"], q["b"], r); return self._send(200, r)
                if u.path == "/api/source":
                    return self._send(200, {"text": src.read_text(q["doc"], q["v"])})
                self._send(404, {"error": "not found"})
            except (KeyError, StopIteration, ValueError) as e:
                self._send(400, {"error": f"bad request: {e}"})
        def do_POST(self):
            if self.path == "/api/scan": return self._send(200, {"comparisons": scan_all(src, store)})
            self._send(404, {"error": "not found"})
    return H

def build(src=None, db=":memory:", port=8000, host="127.0.0.1"):
    src = src or make_source()
    return ThreadingHTTPServer((host, port), make_handler(src, Store(db)))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    srv = build(db=os.environ.get("HISTORY_DB", "history.db"), port=port)
    print(f"Dashboard: http://127.0.0.1:{port}  (source={os.environ.get('DRIVE_SOURCE', 'snapshot')})")
    srv.serve_forever()
