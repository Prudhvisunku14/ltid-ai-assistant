"""Tests for the web layer. Every answer asserted here comes from the project's real rag_app package.
Run from web_demo/:  python -m unittest discover -s tests -v        (standard library only; no network)"""
import http.client
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.create_server("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.call("POST", "/api/reset", {})                      # every test starts from the shipped knowledge base

    def call(self, method, path, body=None, raw=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        h = {"Content-Type": "application/json", **(headers or {})}
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        text = r.read()
        c.close()
        try:
            return r.status, json.loads(text) if text else None
        except ValueError:
            return r.status, text

    # ---------------------------------------------------------------- basics
    def test_health_config_examples(self):
        st, h = self.call("GET", "/api/health")
        self.assertEqual((st, h["status"], h["documents"]), (200, "ok", 5))
        st, c = self.call("GET", "/api/config")
        self.assertEqual(st, 200)
        self.assertIn("No embeddings and no vector database", c["retrieval"])      # the method is stated honestly
        self.assertTrue(c["fictional_data"])
        st, e = self.call("GET", "/api/examples")
        self.assertEqual(st, 200)
        self.assertIn("When must an expense claim be submitted?", e["questions"])

    def test_static_page_and_unknown_routes(self):
        st, body = self.call("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn(b"LTID AI Competition", body)
        self.assertEqual(self.call("GET", "/api/nope")[0], 404)
        self.assertEqual(self.call("GET", "/../prompt-c-rag/README.md")[0], 404)
        self.assertEqual(self.call("PUT", "/api/ask", {})[0], 405)

    def test_documents_lists_shipped_files_with_versions(self):
        st, d = self.call("GET", "/api/documents")
        docs = {x["filename"]: x for x in d["documents"]}
        self.assertEqual(len(docs), 5)
        self.assertFalse(any(x["uploaded"] for x in docs.values()))
        self.assertEqual((docs["Policy_Expense_v1_Superseded.txt"]["status"], docs["Policy_Expense_v1_Superseded.txt"]["superseded_by"]), ("superseded", 2))
        self.assertEqual((docs["Policy_Expense_v2_Current.txt"]["status"], docs["Policy_Expense_v2_Current.txt"]["effective"]), ("current", "2026-10-01"))
        self.assertEqual(docs["Project_Helpdesk_ServiceSpec.txt"]["status"], "draft")

    # ---------------------------------------------------------------- asking
    def test_supported_answer_has_filename_line_and_excerpt(self):
        st, a = self.call("POST", "/api/ask", {"question": "When must an expense claim be submitted?"})
        self.assertEqual(st, 200)
        self.assertEqual((a["status"], a["found"], a["generator"]), ("answered", True, "extractive"))
        self.assertIn("10 calendar days", a["answer"])
        c = a["citations"][0]
        self.assertEqual((c["filename"], c["status"]), ("Policy_Expense_v2_Current.txt", "current"))
        self.assertGreaterEqual(c["line_no"], 1)
        self.assertIn("10 calendar days", c["excerpt"])
        self.assertTrue(any("superseded" in n for n in a["notes"]))                 # v1 was ignored and the user is told

    def test_the_four_required_topics_are_answered_from_the_right_files(self):
        expect = {"What is the hotel reimbursement limit per night?": ("JPY 15,000", "Policy_Expense_v2_Current.txt"),
                  "How much notice is needed for planned annual leave?": ("5 working days", "Policy_Leave_Current.txt"),
                  "Who must approve a production deployment?": ("release approval", "Engineering_Deployment_Guide.txt")}
        for q, (text, fn) in expect.items():
            with self.subTest(q=q):
                st, a = self.call("POST", "/api/ask", {"question": q})
                self.assertIn(text, a["answer"])
                self.assertEqual(a["citations"][0]["filename"], fn)

    def test_unanswerable_questions_abstain_without_citations(self):
        for q in ("Who approved our acquisition of Company Z?", "What is the capital of France?", "asdf qwerty zzz"):
            with self.subTest(q=q):
                st, a = self.call("POST", "/api/ask", {"question": q})
                self.assertEqual((st, a["status"], a["found"], a["citations"]), (200, "not_found", False, []))
                self.assertIn("not found in the available documents", a["answer"])

    def test_history_question_labels_superseded_version(self):
        st, a = self.call("POST", "/api/ask", {"question": "What was the old expense claim deadline in version 1?"})
        self.assertIn("SUPERSEDED", a["answer"])
        self.assertIn("30 calendar days", a["answer"])

    def test_invalid_questions_are_rejected_with_messages(self):
        for body, code in (({"question": ""}, "empty_question"), ({"question": "   "}, "empty_question"), ({}, "empty_question"),
                           ({"question": 42}, "empty_question"), ({"question": "x" * 1001}, "question_too_long")):
            with self.subTest(body=str(body)[:30]):
                st, e = self.call("POST", "/api/ask", body)
                self.assertEqual((st, e["error"]["code"]), (400, code))
        self.assertEqual(self.call("POST", "/api/ask", raw=b"{not json")[1]["error"]["code"], "bad_json")
        self.assertEqual(self.call("POST", "/api/ask", raw=b"[1,2]")[1]["error"]["code"], "bad_json")

    # ---------------------------------------------------------------- optional LLM
    def test_llm_option_without_configuration_gives_a_clear_error(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("RAG_LLM_BASE_URL", None)
            st, e = self.call("POST", "/api/ask", {"question": "When must an expense claim be submitted?", "use_llm": True})
            self.assertEqual((st, e["error"]["code"]), (400, "llm_not_configured"))
            self.assertIn("OPENAI_API_KEY", e["error"]["message"])
            self.assertFalse(self.call("GET", "/api/config")[1]["llm_configured"])

    def test_unreachable_llm_falls_back_to_the_extractive_answer_and_says_so(self):
        with mock.patch.dict(os.environ, {"RAG_LLM_BASE_URL": "http://127.0.0.1:9/v1"}):     # nothing listens on port 9
            st, a = self.call("POST", "/api/ask", {"question": "When must an expense claim be submitted?", "use_llm": True})
        self.assertEqual((st, a["found"], a["generator"]), (200, True, "extractive"))
        self.assertIn("10 calendar days", a["answer"])
        self.assertTrue(any("LLM was not used" in n for n in a["notes"]))

    # ---------------------------------------------------------------- upload
    def test_uploaded_document_becomes_searchable_and_can_be_removed(self):
        text = "Travel Policy - version 1 (effective 2026-01-01)\nCar rentals require director approval before booking."
        st, d = self.call("POST", "/api/documents", {"filename": "Travel_Policy.txt", "content": text})
        self.assertEqual((st, d["filename"], d["uploaded"], d["status"]), (201, "Travel_Policy.txt", True, "current"))
        self.assertGreaterEqual(d["passages"], 1)
        st, a = self.call("POST", "/api/ask", {"question": "Who must approve car rentals?"})
        self.assertTrue(a["found"])
        self.assertEqual(a["citations"][0]["filename"], "Travel_Policy.txt")
        st, listing = self.call("GET", "/api/documents")
        self.assertEqual(len(listing["documents"]), 6)
        st, after = self.call("DELETE", "/api/documents/Travel_Policy.txt")
        self.assertEqual((st, len(after["documents"])), (200, 5))
        self.assertFalse(self.call("POST", "/api/ask", {"question": "Who must approve car rentals?"})[1]["found"])

    def test_a_newer_uploaded_version_supersedes_the_shipped_one(self):
        text = "Expense Policy - VERSION 3 (effective 2026-12-01)\nAll claims must be submitted within 5 calendar days after an expense occurs."
        self.assertEqual(self.call("POST", "/api/documents", {"filename": "Policy_Expense_v3_Current.txt", "content": text})[0], 201)
        st, a = self.call("POST", "/api/ask", {"question": "When must an expense claim be submitted?"})
        self.assertIn("5 calendar days", a["answer"])
        self.assertEqual(a["citations"][0]["filename"], "Policy_Expense_v3_Current.txt")
        docs = {d["filename"]: d for d in self.call("GET", "/api/documents")[1]["documents"]}
        self.assertEqual(docs["Policy_Expense_v2_Current.txt"]["status"], "superseded")

    def test_invalid_uploads_are_rejected_and_do_not_change_the_knowledge_base(self):
        good = "Some Policy - version 1\nA short sentence about nothing in particular."
        bad = [({"filename": "notes.pdf", "content": good}, 400, "unsupported_type"),
               ({"filename": "../evil.txt", "content": good}, 400, "invalid_filename"),
               ({"filename": "a/b.txt", "content": good}, 400, "invalid_filename"),
               ({"filename": "..\\evil.txt", "content": good}, 400, "invalid_filename"),
               ({"filename": "", "content": good}, 400, "invalid_filename"),
               ({"filename": "empty.txt", "content": "   "}, 400, "empty_document"),
               ({"filename": "nul.txt", "content": "abc\x00def"}, 400, "not_text"),
               ({"filename": "big.txt", "content": "word. " * 40000}, 413, "too_large"),
               ({"filename": "Policy_Leave_Current.txt", "content": good}, 409, "name_taken"),
               ({"filename": "nofile.txt"}, 400, "empty_document")]
        for body, status, code in bad:
            with self.subTest(code=code, name=str(body.get("filename"))):
                st, e = self.call("POST", "/api/documents", body)
                self.assertEqual((st, e["error"]["code"]), (status, code))
        self.assertEqual(len(self.call("GET", "/api/documents")[1]["documents"]), 5)

    def test_shipped_documents_cannot_be_removed(self):
        st, e = self.call("DELETE", "/api/documents/Policy_Leave_Current.txt")
        self.assertEqual((st, e["error"]["code"]), (403, "shipped_document"))
        self.assertEqual(self.call("DELETE", "/api/documents/nothing.txt")[0], 404)
        self.assertEqual(len(self.call("GET", "/api/documents")[1]["documents"]), 5)

    def test_reset_removes_every_upload(self):
        self.call("POST", "/api/documents", {"filename": "One.txt", "content": "One Policy - version 1\nThe first rule applies to everyone."})
        st, r = self.call("POST", "/api/reset", {})
        self.assertEqual((st, len(r["documents"]), any(d["uploaded"] for d in r["documents"])), (200, 5, False))

    def test_requests_with_bodies_always_get_a_reply_even_when_rejected(self):
        """Regression: replying without reading the body made Windows reset the connection for 4-20% of requests."""
        body = {"question": "x" * 500}
        for method, path, want in (("PUT", "/api/ask", 405), ("PATCH", "/api/documents", 405), ("POST", "/api/nope", 404), ("DELETE", "/api/zzz", 404)):
            for i in range(60):
                with self.subTest(method=method, i=i):
                    st, _ = self.call(method, path, body)
                    self.assertEqual(st, want)
        big = server.MAX_BODY + 50_000
        for i in range(5):
            st, e = self.call("POST", "/api/documents", raw=b'{"filename":"a.txt","content":"' + b"x" * big + b'"}')
            self.assertEqual((st, e["error"]["code"]), (413, "too_large"))

    def test_uploads_never_touch_the_project_files(self):
        shipped = server.PROJECT / "knowledge_base"
        before = sorted((p.name, p.stat().st_size) for p in shipped.iterdir())
        self.call("POST", "/api/documents", {"filename": "Temp_Only.txt", "content": "Temp Policy - version 1\nThis exists only in memory of the demo."})
        self.assertEqual(sorted((p.name, p.stat().st_size) for p in shipped.iterdir()), before)
        self.assertFalse((shipped / "Temp_Only.txt").exists())


if __name__ == "__main__":
    unittest.main()
