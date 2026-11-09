import json, shutil, tempfile, unittest
from pathlib import Path
from devpilot import change, demo
from devpilot.llm import ScriptedLLM

DEMO = Path(__file__).resolve().parent.parent / "examples" / "change_demo"


def fresh():
    d = Path(tempfile.mkdtemp()) / "p"; shutil.copytree(DEMO, d); return d


class T(unittest.TestCase):
    def test_plan_implement_fail_repair_pass(self):
        d = fresh(); r = change.run_change(d, demo.REQUEST, ScriptedLLM(demo.scripted_replies()), evidence_root=d.parent / "ev")
        self.assertEqual(r["status"], "success")
        self.assertEqual([a["tests"]["passed"] for a in r["attempts"]], [False, True])
        self.assertIn("free_at_100", (d / "test_shipping.py").read_text())
        self.assertTrue((Path(r["evidence_dir"]) / "report.md").exists())

    def test_rolls_back_when_repairs_exhausted(self):
        d = fresh(); orig = (d / "shipping.py").read_text()
        bad = json.dumps({"files": [{"path": "shipping.py", "content": "def shipping_cost(t, express=False):\n    return 0\n"}]})
        plan = json.dumps({"approach": "x", "files_to_change": [], "tests_to_add": [], "risks": []})
        r = change.run_change(d, "break it", ScriptedLLM([plan] + [bad] * 5), max_repairs=1, evidence_root=d.parent / "ev")
        self.assertTrue(r["status"].startswith("FAILED")); self.assertEqual((d / "shipping.py").read_text(), orig)

    def test_refuses_path_escape(self):
        d = fresh(); evil = json.dumps({"files": [{"path": "../escape.py", "content": "x=1"}]})
        plan = json.dumps({"approach": "x"})
        r = change.run_change(d, "evil", ScriptedLLM([plan, evil]), evidence_root=d.parent / "ev")
        self.assertIn("unsafe", r["status"]); self.assertFalse((d.parent / "escape.py").exists())

    def test_no_llm_means_no_changes_and_honest_status(self):
        from devpilot.llm import OpenAILLM
        d = fresh(); before = change.snapshot(d)
        r = change.run_change(d, "anything", OpenAILLM(api_key=""), evidence_root=d.parent / "ev")
        self.assertTrue(r["status"].startswith("NOT ATTEMPTED")); self.assertEqual(change.snapshot(d), before)
