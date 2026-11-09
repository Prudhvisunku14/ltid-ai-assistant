import unittest
from devpilot import tools

NOENV = {}
def fake_run(cmd, timeout=20, cwd=None):
    return (127, "", "not found") if cmd[0] in ("gh", "docker") else (0, "ok 1.0", "")
def get_ok(url, headers=None, timeout=8): return 200, {"X-OAuth-Scopes": "repo"}, "{}"
def get_401(url, headers=None, timeout=8): return 401, {}, "no"
def get_down(url, headers=None, timeout=8): return 0, {}, "dns failure"


class T(unittest.TestCase):
    def status(self, rows, id): return next(r for r in rows if r["id"] == id)["live"]["status"]

    def test_missing_credentials_are_not_assumed_to_work(self):
        rows = tools.assess(run=fake_run, get=get_ok, env=NOENV)
        self.assertEqual(self.status(rows, "openai"), "unavailable")
        self.assertEqual(self.status(rows, "github"), "unavailable")
        self.assertEqual(self.status(rows, "docker"), "unavailable")
        self.assertEqual(self.status(rows, "gdrive"), "mock_only")

    def test_verified_only_on_live_200(self):
        rows = tools.assess(run=fake_run, get=get_ok, env={"OPENAI_API_KEY": "k", "GITHUB_TOKEN": "t"})
        self.assertEqual(self.status(rows, "openai"), "verified")
        gh = next(r for r in rows if r["id"] == "github")["live"]
        self.assertEqual(gh["observed_permissions"], "repo")

    def test_rejected_key_is_unauthorized(self):
        rows = tools.assess(run=fake_run, get=get_401, env={"OPENAI_API_KEY": "bad"})
        self.assertEqual(self.status(rows, "openai"), "unauthorized")

    def test_offline_with_key_is_unverified(self):
        rows = tools.assess(run=fake_run, get=get_down, env={"OPENAI_API_KEY": "k"})
        self.assertEqual(self.status(rows, "openai"), "configured_unverified")

    def test_crashing_probe_reported_unavailable(self):
        def boom(*a, **k): raise RuntimeError("x")
        rows = tools.assess(run=boom, get=get_ok, env=NOENV)
        self.assertEqual(self.status(rows, "git"), "unavailable")

    def test_report_cites_sources(self):
        self.assertIn("platform.openai.com", tools.render(tools.assess(run=fake_run, get=get_down, env=NOENV)))
