import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from devbot import analyzer
from devbot.git_ops import Git
from devbot.llm import MockLLM
from devbot.pipeline import Options, run
from devbot.safety import SafetyError, check_git_args, validate_branch_name, validate_edit_path, validate_edit_set
import make_demo_repo


class SafetyTests(unittest.TestCase):
    def test_merge_and_force_blocked(self):
        for bad in (["merge", "x"], ["reset", "--hard"], ["push", "--force"], ["push", "origin", "main"],
                    ["push", "origin", "+x"], ["rebase", "main"], ["branch", "-D", "x"]):
            with self.assertRaises(SafetyError, msg=str(bad)):
                check_git_args(bad)

    def test_allowed_git(self):
        check_git_args(["checkout", "-b", "devbot/x"])
        check_git_args(["push", "--set-upstream", "origin", "devbot/x"])

    def test_branch_names(self):
        validate_branch_name("devbot/ok-1")
        for bad in ("main", "master", "a..b", "bad name"):
            with self.assertRaises(SafetyError):
                validate_branch_name(bad)

    def test_edit_paths(self):
        root = Path(tempfile.mkdtemp())
        validate_edit_path(root, "src/a.py")
        for bad in ("../x", "/etc/passwd", ".git/config", ".env", "k/server.pem", ".github/workflows/ci.yml"):
            with self.assertRaises(SafetyError, msg=bad):
                validate_edit_path(root, bad)
        with self.assertRaises(SafetyError):
            validate_edit_set(root, [])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = make_demo_repo.main(str(self.tmp / "repo"))

    def _run(self, live):
        llm = MockLLM.from_file(ROOT / "demo" / "demo_script.py")
        return run(Options(repo=str(self.repo), request="Add bulk discount", live=live, auto_approve=True,
                           out_dir=self.tmp / "out"), llm, log=lambda s: None), llm

    def test_analyzer(self):
        rep = analyzer.analyze(self.repo)
        self.assertEqual(list(rep.languages), ["Python"])
        self.assertIn("unittest", " ".join(t["tool"] for t in rep.dev_tools))

    def test_dry_run_changes_nothing(self):
        before = Git(self.repo).run("rev-parse", "HEAD")
        res, llm = self._run(live=False)
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.repairs_used, 1)
        self.assertEqual(Git(self.repo).run("rev-parse", "HEAD"), before)
        self.assertEqual(Git(self.repo).run("branch", "--list").split(), ["*", "main"])
        self.assertTrue(Git(self.repo).is_clean())

    def test_live_creates_branch_not_merge(self):
        main_head = Git(self.repo).run("rev-parse", "main")
        res, _ = self._run(live=True)
        g = Git(self.repo)
        self.assertEqual(g.run("rev-parse", "main"), main_head)       # main never moved
        self.assertTrue(g.run("rev-parse", "--abbrev-ref", "HEAD").startswith("devbot/"))
        self.assertTrue(Path(res.pr_location).exists())
        self.assertIn("Human review required", Path(res.pr_location).read_text())

    def test_not_approved_aborts(self):
        llm = MockLLM.from_file(ROOT / "demo" / "demo_script.py")
        res = run(Options(repo=str(self.repo), request="x", out_dir=self.tmp / "o"), llm,
                  log=lambda s: None, approve=lambda t: False)
        self.assertEqual(res.status, "aborted-not-approved")

    def test_live_dirty_tree_refused(self):
        (self.repo / "dirty.txt").write_text("x")
        with self.assertRaises(SafetyError):
            self._run(live=True)


if __name__ == "__main__":
    unittest.main()
