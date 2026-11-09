import datetime as dt, unittest
from pathlib import Path
from devpilot import rag

POL = Path(__file__).resolve().parent.parent / "data" / "policies"


class T(unittest.TestCase):
    def setUp(self): self.c = rag.Corpus(POL, dt.date(2026, 11, 10))

    def test_current_deadline_uses_newest_policy_and_verified_citation(self):
        r = rag.answer(self.c, "What is the current expense claim deadline?")
        self.assertFalse(r["abstained"]); self.assertIn("45", r["answer"]); self.assertNotIn("30 calendar", r["answer"])
        self.assertEqual(r["citations"][0]["doc_id"], "expense_policy_2025"); self.assertTrue(r["citations_verified"])

    def test_old_policy_is_in_force_before_new_one_starts(self):
        r = rag.answer(rag.Corpus(POL, dt.date(2024, 6, 1)), "What is the current expense claim deadline?")
        self.assertIn("30", r["answer"])

    def test_abstains_on_company_z_and_ignores_rumour(self):
        r = rag.answer(self.c, "Who approved our acquisition of Company Z?")
        self.assertTrue(r["abstained"]); self.assertNotIn("CFO", r["answer"])
        self.assertTrue(any("chat_rumour_draft" in n for n in r["excluded_documents_mentioning_topic"]))
        self.assertTrue(r["closest_verified"])

    def test_fabricated_citation_fails_verification(self):
        cit = {"path": str(POL / "expense_policy_2025.md"), "quote": "Claims are due in 90 days."}
        self.assertFalse(rag.verify_citation(cit))

    def test_unrelated_question_abstains(self):
        self.assertTrue(rag.answer(self.c, "What is the CEO's favourite colour?")["abstained"])
