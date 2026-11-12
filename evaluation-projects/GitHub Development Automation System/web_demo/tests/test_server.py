"""Tests for the devbot web interface. They drive the REAL devbot pipeline (real git, real test runs, real branch/commit in
a scratch copy). The OpenAI path is exercised over real HTTP against a LOCAL FAKE OpenAI-compatible server, so these tests
prove the key handling and the request/response plumbing but NOT that a live OpenAI model produces good edits.
    python -m unittest discover -s web_demo/tests -t web_demo      (from the integration folder)
"""
import http.client
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE.parent
spec = importlib.util.spec_from_file_location("devbot_web_server", WEB / "server.py")
srv = importlib.util.module_from_spec(spec)
sys.modules["devbot_web_server"] = srv
spec.loader.exec_module(srv)

from devbot import prompts                      # noqa: E402  (importable after server.py extended sys.path)
from devbot.llm import MockLLM                  # noqa: E402

KEY = "sk-test-UNIQUE-SECRET-1234567890abcdef"
TOKEN = "ghp_UNIQUEGITHUBTOKEN1234567890abcdef"
SYSTEM_TO_TASK = {prompts.EXPLAIN: "explain", prompts.PLAN: "plan", prompts.EDIT: "edit",
                  prompts.REPAIR: "repair", prompts.SUMMARY: "summary"}


class FakeOpenAI:
    """Minimal /v1/chat/completions that answers from devbot's own demo script, and records what it was sent."""

    def __init__(self):
        self.mode = "ok"                      # ok | 401 | echo-key | 429
        self.auth_headers: list[str] = []
        self.models: list[str] = []
        self.script = MockLLM.from_file(srv.PROJECT / "demo" / "demo_script.py")
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n))
                outer.auth_headers.append(self.headers.get("Authorization", ""))
                outer.models.append(body.get("model"))
                if outer.mode in ("401", "echo-key", "429"):
                    code = 429 if outer.mode == "429" else 401
                    msg = ("Incorrect API key provided: " + self.headers.get("Authorization", "").replace("Bearer ", "")
                           if outer.mode == "echo-key" else "bad")
                    data = json.dumps({"error": {"message": msg, "code": "invalid_api_key"}}).encode()
                    self.send_response(code)
                else:
                    task = SYSTEM_TO_TASK[body["messages"][0]["content"]]
                    reply = outer.script.complete_json(task, "", "")
                    data = json.dumps({"choices": [{"message": {"content": json.dumps(reply)}}]}).encode()
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = srv.make_server("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.fake = FakeOpenAI()
        cls._old_base = srv.OPENAI_BASE
        srv.OPENAI_BASE = cls.fake.url

    @classmethod
    def tearDownClass(cls):
        srv.OPENAI_BASE = cls._old_base
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.fake.close()

    def setUp(self):
        self.fake.mode = "ok"
        self.fake.script = MockLLM.from_file(srv.PROJECT / "demo" / "demo_script.py")
        self.fake.auth_headers.clear()
        self.fake.models.clear()
        self._wait_idle()

    def tearDown(self):
        self._wait_idle()

    def _wait_idle(self, timeout=60):
        end = time.time() + timeout
        while srv.ACTIVE and time.time() < end:
            for jid in list(srv.ACTIVE):                       # a test that left a run waiting: reject it
                job = srv.JOBS.get(jid)
                if job and job.status == "awaiting_approval":
                    job.decide(False)
            time.sleep(0.1)

    def call(self, method, path, body=None, headers=None, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        payload = r.read()
        conn.close()
        try:
            parsed = json.loads(payload)
        except ValueError:
            parsed = payload
        return r.status, parsed, r

    def wait_for(self, run_id, statuses, timeout=90):
        end = time.time() + timeout
        job = {}
        while time.time() < end:
            _, job, _ = self.call("GET", f"/api/runs/{run_id}")
            if job["status"] in statuses:
                return job
            time.sleep(0.15)
        self.fail(f"run did not reach {statuses}; last: {job.get('status')} {job.get('error')} {job.get('log', [])[-3:]}")

    def start(self, **over):
        body = {"mode": "mock", "source": "demo", "request": srv.DEMO_REQUEST}
        body.update(over)
        status, data, _ = self.call("POST", "/api/runs", body)
        return status, data


class BasicsAndSecurity(Base):
    def test_page_config_and_headers(self):
        s, page, r = self.call("GET", "/")
        self.assertEqual(s, 200)
        html = page.decode()
        self.assertIn('type="password"', html)                    # the key is asked for in a masked field
        self.assertIn("OpenAI API key", html)
        self.assertIn("script-src 'self'", r.getheader("Content-Security-Policy"))
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), None)
        s, cfg, _ = self.call("GET", "/api/config")
        self.assertEqual((s, cfg["live_mode"], cfg["git_available"]), (200, False, True))
        self.assertEqual(self.call("GET", "/api/health")[1]["status"], "ok")
        self.assertEqual(self.call("GET", "/app.js")[0], 200)
        self.assertEqual(self.call("GET", "/nope")[0], 404)

    def test_post_requires_json_content_type(self):
        s, data, _ = self.call("POST", "/api/runs", raw=b'{"mode":"mock"}', headers={"Content-Type": "text/plain"})
        self.assertEqual((s, data["error"]["code"]), (415, "json_required"))
        s, data, _ = self.call("POST", "/api/runs", raw=b"{not json", headers={"Content-Type": "application/json"})
        self.assertEqual((s, data["error"]["code"]), (400, "bad_json"))

    def test_foreign_host_header_is_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.putrequest("GET", "/api/config", skip_host=True)
        conn.putheader("Host", "evil.example.com")
        conn.endheaders()
        r = conn.getresponse()
        self.assertEqual(r.status, 403)
        r.read()
        conn.close()

    def test_unread_bodies_never_reset_the_connection(self):
        big = b"x" * 70_000
        for i in range(25):
            s, _, _ = self.call("POST", "/api/runs", raw=big, headers={"Content-Type": "application/json"})
            self.assertEqual(s, 413)
            s, _, _ = self.call("PUT", "/api/runs", raw=b'{"a":1}', headers={"Content-Type": "application/json"})
            self.assertEqual(s, 405)
            s, _, _ = self.call("POST", "/api/unknown", body={"a": 1})
            self.assertEqual(s, 404)

    def test_server_ignores_keys_in_its_own_environment(self):
        os.environ["OPENAI_API_KEY"] = "sk-from-server-environment-should-never-be-used"
        os.environ["GITHUB_TOKEN"] = "ghp_fromserverenvironmentshouldnotbeused1234"
        try:
            s, data = self.start(mode="openai")
            self.assertEqual((s, data["error"]["code"]), (400, "api_key_required"))
        finally:
            del os.environ["OPENAI_API_KEY"]
            del os.environ["GITHUB_TOKEN"]

    def test_input_validation(self):
        cases = [
            (dict(request=""), "empty_request"),
            (dict(request="x" * 2001), "request_too_long"),
            (dict(mode="live"), "bad_mode"),
            (dict(source="local"), "bad_source"),
            (dict(mode="openai", openai_key=""), "api_key_required"),
            (dict(mode="openai", openai_key="sk bad key"), "bad_secret"),
            (dict(mode="openai", openai_key=KEY, model="gpt 4; rm -rf"), "bad_model"),
            (dict(source="github", repo_url="/etc", mode="openai", openai_key=KEY, trust_confirmed=True), "bad_repo_url"),
            (dict(source="github", repo_url="http://github.com/a/b", mode="openai", openai_key=KEY, trust_confirmed=True), "bad_repo_url"),
            (dict(source="github", repo_url="https://evil.example/a/b", mode="openai", openai_key=KEY, trust_confirmed=True), "bad_repo_url"),
            (dict(source="github", repo_url="https://github.com/a/b", mode="openai", openai_key=KEY), "trust_required"),
            (dict(source="github", repo_url="https://github.com/a/b", trust_confirmed=True), "mock_needs_demo_repo"),
            (dict(max_repairs="many"), "bad_max_repairs"),
        ]
        for over, code in cases:
            s, data = self.start(**over)
            self.assertEqual((s, data["error"]["code"]), (400, code), over)

    def test_redactor(self):
        red = srv.make_redactor(KEY, TOKEN)
        text = f"auth {KEY} and {TOKEN} and Bearer abcdefghijklmnop and sk-live-ABCDEFGH and basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="
        out = red(text)
        for secret in (KEY, TOKEN, "abcdefghijklmnop", "sk-live-ABCDEFGH", "QWxhZGRpbjpvcGVuIHNlc2FtZQ"):
            self.assertNotIn(secret, out)
        import base64
        self.assertNotIn(base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode(), red("h " + base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()))


class OfflineDemoRun(Base):
    def test_full_run_waits_for_approval_then_repairs_and_prepares_a_draft(self):
        s, job = self.start()
        self.assertEqual(s, 202)
        job = self.wait_for(job["id"], {"awaiting_approval"})
        self.assertIn("Files to change", job["plan"])
        self.assertIsNone(job["result"])
        joined = "\n".join(job["log"])
        self.assertNotIn("Step 6", joined)                         # nothing edited before approval
        self.assertEqual(self.call("POST", f"/api/runs/{job['id']}/approve", {})[0], 200)
        job = self.wait_for(job["id"], {"done"})
        r = job["result"]
        self.assertEqual((r["status"], r["tests_ok"], r["repairs_used"], r["mode"]), ("ok", True, 1, "dry-run"))
        self.assertTrue(r["branch"].startswith("devbot/"))
        self.assertIn("Human review required", r["pr_preview"])
        self.assertIn("BULK_THRESHOLD", r["diff"])
        log = "\n".join(job["log"])
        self.assertIn("verified: original repository unchanged by dry-run", log)
        self.assertIn("never merges", log)
        self.assertIn("repair attempt 1/2", log)

    def test_reject_changes_nothing(self):
        s, job = self.start()
        job = self.wait_for(job["id"], {"awaiting_approval"})
        self.assertEqual(self.call("POST", f"/api/runs/{job['id']}/reject", {})[0], 200)
        job = self.wait_for(job["id"], {"done"})
        self.assertEqual(job["result"]["status"], "aborted-not-approved")
        self.assertEqual(job["result"]["files_changed"], [])
        self.assertNotIn("Step 6", "\n".join(job["log"]))

    def test_only_one_run_at_a_time_and_approve_needs_a_waiting_run(self):
        s, job = self.start()
        job = self.wait_for(job["id"], {"awaiting_approval"})
        s, data = self.start()
        self.assertEqual((s, data["error"]["code"]), (409, "busy"))
        self.assertEqual(self.call("POST", f"/api/runs/{job['id']}/reject", {})[0], 200)
        self.wait_for(job["id"], {"done"})
        s, data, _ = self.call("POST", f"/api/runs/{job['id']}/approve", {})
        self.assertEqual((s, data["error"]["code"]), (409, "not_waiting"))
        self.assertEqual(self.call("GET", "/api/runs/000000000000")[0], 404)

    def test_log_can_be_read_incrementally(self):
        s, job = self.start()
        job = self.wait_for(job["id"], {"awaiting_approval"})
        total = job["log_total"]
        _, tail, _ = self.call("GET", f"/api/runs/{job['id']}?since={total}")
        self.assertEqual(tail["log"], [])


class OpenAIPathWithFakeServer(Base):
    def run_to_end(self, **over):
        s, job = self.start(mode="openai", openai_key=KEY, **over)
        self.assertEqual(s, 202, job)
        job = self.wait_for(job["id"], {"awaiting_approval", "error", "done", "safety_stop"})
        if job["status"] == "awaiting_approval":
            self.call("POST", f"/api/runs/{job['id']}/approve", {})
            job = self.wait_for(job["id"], {"done", "error", "safety_stop"})
        return job

    def assert_no_secret(self, *objs):
        for o in objs:
            text = json.dumps(o)
            self.assertNotIn(KEY, text)
            self.assertNotIn(TOKEN, text)

    def test_user_key_is_used_as_bearer_token_and_never_echoed(self):
        s, first = self.start(mode="openai", openai_key=KEY, model="gpt-test-model")
        self.assert_no_secret(first)
        mid = self.wait_for(first["id"], {"awaiting_approval"})
        self.assert_no_secret(mid)
        self.call("POST", f"/api/runs/{first['id']}/approve", {})
        job = self.wait_for(first["id"], {"done"})
        self.assertEqual(job["result"]["status"], "ok")
        self.assert_no_secret(job)
        self.assertTrue(self.fake.auth_headers and all(h == f"Bearer {KEY}" for h in self.fake.auth_headers))
        self.assertEqual(set(self.fake.models), {"gpt-test-model"})
        self.assertIn("openai:gpt-test-model", "\n".join(job["log"]))

    def test_key_is_not_written_to_disk_or_environment(self):
        job = self.run_to_end()
        self.assertEqual(job["status"], "done")
        for k, v in os.environ.items():
            self.assertNotIn(KEY, v, k)
        needle = KEY.encode()
        tmp = Path(tempfile.gettempdir())
        roots = [srv.PROJECT, WEB] + [d for d in tmp.glob("devbot-*") if d.is_dir()]
        for root in roots:
            for dp, _dn, fn in os.walk(root):
                for f in fn:
                    p = Path(dp) / f
                    if p.name == "test_server.py" or ".git" in p.parts:
                        continue
                    try:
                        if p.stat().st_size < 2_000_000 and needle in p.read_bytes():
                            self.fail(f"key found in {p}")
                    except OSError:
                        pass

    def test_rejected_key_gives_a_friendly_error(self):
        self.fake.mode = "401"
        job = self.run_to_end()
        self.assertEqual(job["status"], "error")
        self.assertIn("rejected the API key", job["error"])
        self.assert_no_secret(job)

    def test_key_echoed_by_the_api_is_scrubbed(self):
        self.fake.mode = "echo-key"
        job = self.run_to_end()
        self.assertEqual(job["status"], "error")
        self.assert_no_secret(job)
        self.assertIn("[hidden]", job["error"])

    def test_rate_limit_message(self):
        self.fake.mode = "429"
        self.assertIn("429", self.run_to_end()["error"])

    def test_unreachable_api_is_reported_without_a_traceback(self):
        old = srv.OPENAI_BASE
        srv.OPENAI_BASE = "http://127.0.0.1:9/v1"
        try:
            job = self.run_to_end()
        finally:
            srv.OPENAI_BASE = old
        self.assertEqual(job["status"], "error")
        self.assertIn("Could not reach the OpenAI API", job["error"])

    def test_analyze_without_key_is_heuristic_only_and_with_key_adds_overview(self):
        s, a, _ = self.call("POST", "/api/analyze", {"source": "demo"})
        self.assertEqual(s, 200)
        self.assertEqual(list(a["languages"]), ["Python"])
        self.assertIn("unittest", a["test_command"])
        self.assertEqual(a["overview"], "")
        self.assertEqual(self.fake.auth_headers, [])               # no model call without a key
        s, a, _ = self.call("POST", "/api/analyze", {"source": "demo", "openai_key": KEY})
        self.assertEqual(s, 200)
        self.assertTrue(a["overview"])
        self.assertEqual(self.fake.auth_headers, [f"Bearer {KEY}"])
        self.assert_no_secret(a)

    def test_github_source_uses_a_shallow_clone_and_the_same_pipeline(self):
        # A local repository stands in for GitHub (no network in tests); the URL check is relaxed for this one test.
        import make_demo_repo
        tmp = Path(tempfile.mkdtemp(prefix="devbot-web-test-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        origin = make_demo_repo.main(str(tmp / "origin"))
        old = srv.GITHUB_URL
        srv.GITHUB_URL = re.compile(r"^(file:///.+)$")
        try:
            url = origin.as_uri()
            job = self.run_to_end(source="github", repo_url=url, trust_confirmed=True, github_token=TOKEN)
            self.assertEqual(job["status"], "done", job.get("error"))
            self.assertEqual(job["result"]["status"], "ok")
            self.assert_no_secret(job)
            before = (origin / "bookshop" / "pricing.py").read_text()
            self.assertNotIn("BULK_THRESHOLD", before)              # the origin repository was never touched
        finally:
            srv.GITHUB_URL = old

    def test_clone_failure_is_reported_and_token_is_not_leaked(self):
        redact = srv.make_redactor("", TOKEN)
        with self.assertRaises(srv.ApiError) as cm:
            srv.shallow_clone("file:///definitely/not/here", Path(tempfile.mkdtemp()) / "c", TOKEN, redact)
        self.assertEqual(cm.exception.code, "clone_failed")
        self.assertNotIn(TOKEN, cm.exception.message)

    def test_oversized_repository_is_refused(self):
        import make_demo_repo
        tmp = Path(tempfile.mkdtemp(prefix="devbot-web-test-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        origin = make_demo_repo.main(str(tmp / "origin"))
        old = srv.MAX_REPO_BYTES
        srv.MAX_REPO_BYTES = 10
        try:
            with self.assertRaises(srv.ApiError) as cm:
                srv.shallow_clone(origin.as_uri(), tmp / "clone", None, srv.make_redactor())
            self.assertEqual(cm.exception.code, "repo_too_large")
        finally:
            srv.MAX_REPO_BYTES = old


if __name__ == "__main__":
    unittest.main()
