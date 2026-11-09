import hashlib, json, os, sys, tempfile, threading, unittest, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from monitor import differ, analyzer, server
from monitor.sources import LocalFolderSource, GoogleDriveSource, split_name
from monitor.service import compare_versions, scan_all
from monitor.store import Store

SNAP = Path(__file__).resolve().parent.parent / "drive_snapshot"
MOCK = Path(__file__).resolve().parent.parent / "mock_drive"

def snapshot(root):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}

class TestDiffer(unittest.TestCase):
    def test_modified_added_removed(self):
        a = "# A\nline one\nline two\n# B\nold b\n"
        b = "# A\nline one\nline 2\nline three\n# C\nnew c\n"
        ch = differ.compare(a, b)
        kinds = sorted(c["kind"] for c in ch)
        self.assertEqual(kinds, ["modified", "section_added", "section_removed"])
        mod = next(c for c in ch if c["kind"] == "modified")
        self.assertEqual(mod["before"], ["line two"]); self.assertEqual(mod["after"], ["line 2", "line three"])
        self.assertEqual(mod["old_source"]["lines"], [3, 3])
    def test_rename_detected(self):
        ch = differ.compare("# 2. Authentication\nx\n", "# 2. Authentication and Access Control\nx\n")
        self.assertEqual([c["kind"] for c in ch], ["section_renamed"])
    def test_identical(self):
        self.assertEqual(differ.compare("# A\nx\n", "# A\nx\n"), [])
    def test_plain_text_numbered_headings(self):
        secs = differ.parse_sections("1. Performance\ntext\n2. Security\nmore\n")
        self.assertEqual([s["title"] for s in secs], ["1. Performance", "2. Security"])

class TestAnalyzer(unittest.TestCase):
    def one(self, a, b):
        ch = differ.compare(f"# S\n{a}\n", f"# S\n{b}\n")
        return analyzer.analyze(ch)["items"][ch[0]["id"]]
    def test_number_change(self):
        r = self.one("The system shall respond within 5 seconds.", "The system shall respond within 2 seconds.")
        self.assertTrue(r["requirement_impact"]); self.assertIn("Numeric", r["reasons"][0])
    def test_weakened(self):
        r = self.one("Admins shall use MFA.", "Admins should use MFA.")
        self.assertEqual(r["severity"], "high")
    def test_strengthened(self):
        self.assertIn("strengthened", self.one("Admins should use MFA.", "Admins shall use MFA.")["reasons"][0])
    def test_cosmetic_low(self):
        r = self.one("Notes for the team.", "Notes for the whole team.")
        self.assertFalse(r["requirement_impact"])
    def test_label_always_present(self):
        self.assertIn("not verified", self.one("a", "b")["label"])

class TestApiSpecRules(unittest.TestCase):
    def test_partner_api_changes_flagged(self):
        r = compare_versions(LocalFolderSource(MOCK), "Partner_API_Spec", "v1", "v2")
        its = r["interpretation"]["items"]; txt = " ".join(" ".join(i["reasons"]) for i in its.values())
        self.assertIn("endpoint path", txt); self.assertIn("Deprecation", txt); self.assertIn("60", txt)
        self.assertFalse(any(c["kind"] == "section_removed" for c in r["changes"]))  # rename matched by content
    def test_draft_number_is_noise(self):
        ch = differ.compare("# T\nStatus: Draft 2.\n", "# T\nStatus: Draft 3.\n")
        self.assertFalse(analyzer.analyze(ch)["items"][ch[0]["id"]]["requirement_impact"])

class TestSources(unittest.TestCase):
    def test_split_name(self):
        self.assertEqual(split_name("SRS_v2"), ("SRS", "v2")); self.assertEqual(split_name("Plan"), ("Plan", None))
    def test_mock_documents_and_versions(self):
        docs = {d["name"]: [v["id"] for v in d["versions"]] for d in LocalFolderSource(MOCK).documents()}
        self.assertEqual(docs["Fleet_SRS"], ["v1", "v2", "v3"])
        self.assertIn("Security_Policy", docs)
    def test_flat_files_grouped_by_name(self):
        with tempfile.TemporaryDirectory() as t:
            for n in ("SRS_v1.md", "SRS_v2.md", "SRS_v10.md"): Path(t, n).write_text("# A\nx")
            self.assertEqual([v["id"] for v in LocalFolderSource(t).versions("SRS")], ["v1", "v2", "v10"])

class FakeDrive:
    """Minimal stand-in for googleapiclient service to test Drive adapter logic offline."""
    def __init__(self): self.calls = []
    def files(self): return self
    def revisions(self): return self
    def list(self, **kw):
        self.calls.append(("list", kw.get("q", "revisions")))
        class E:
            def __init__(s, d): s.d = d
            def execute(s): return s.d
        if "q" in kw:
            return E({"files": [
                {"id": "1", "name": "SRS_v1.docx", "mimeType": "application/x", "modifiedTime": "t1"},
                {"id": "2", "name": "SRS_v2.docx", "mimeType": "application/x", "modifiedTime": "t2"},
                {"id": "3", "name": "Spec", "mimeType": "application/vnd.google-apps.document", "modifiedTime": "t3"}]})
        return E({"revisions": [{"id": "a", "modifiedTime": "x"}, {"id": "b", "modifiedTime": "y"}]})
class TestDrive(unittest.TestCase):
    def test_grouping_and_readonly_scope(self):
        d = GoogleDriveSource("root", service=FakeDrive())
        docs = {x["name"]: [v["id"] for v in x["versions"]] for x in d.documents()}
        self.assertEqual(docs, {"SRS": ["v1", "v2"], "Spec": ["r1", "r2"]})
        self.assertEqual(GoogleDriveSource.SCOPES, ["https://www.googleapis.com/auth/drive.readonly"])
    def test_no_write_calls_in_source(self):
        src = (Path(__file__).resolve().parent.parent / "monitor" / "sources.py").read_text()
        for bad in (".create(", ".update(", ".delete(", ".emptyTrash(", "files().copy(", ".insert("):
            self.assertNotIn(bad, src)

class TestEndToEnd(unittest.TestCase):
    def test_srs_v1_v2_findings(self):
        r = compare_versions(LocalFolderSource(MOCK), "Fleet_SRS", "v1", "v2")
        it = r["interpretation"]["items"]; by = {c["before"][0] if c["before"] else c["after"][0]: it[c["id"]] for c in r["changes"]}
        perf = next(v for k, v in by.items() if "5 seconds" in k); self.assertTrue(perf["requirement_impact"]); self.assertIn("FT-101", perf["requirement_ids"])
        mfa = next(v for k, v in by.items() if "FT-202" in k); self.assertEqual(mfa["severity"], "high")
        self.assertEqual(r["verified"]["summary"]["counts"]["modified"], 5)  # FT-101, 103, 202, 401 + status line
    def test_srs_v2_v3_detects_removal(self):
        r = compare_versions(LocalFolderSource(MOCK), "Fleet_SRS", "v2", "v3")
        rem = [c for c in r["changes"] if c["kind"] == "removed" and "FT-402" in c["before"][0]]
        self.assertEqual(len(rem), 1)
        self.assertEqual(r["interpretation"]["items"][rem[0]["id"]]["severity"], "high")
        self.assertTrue(any(c["kind"] == "section_renamed" for c in r["changes"]))
    def test_originals_unchanged_after_scan_and_api(self):
        before = snapshot(MOCK)
        src = LocalFolderSource(MOCK); store = Store(":memory:")
        self.assertEqual(scan_all(src, store), 5)  # 2 SRS + 3 other docs
        srv = server.build(src, port=0); port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        get = lambda p: json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}{p}"))
        self.assertEqual(len(get("/api/documents")["documents"]), 4)
        r = get("/api/compare?doc=Security_Policy&a=v1&b=v2")
        self.assertTrue(r["verified"]["label"].startswith("VERIFIED")); self.assertIn("not verified", r["interpretation"]["summary"]["label"])
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/scan", method="POST"))
        hist = get("/api/history"); self.assertEqual(len(hist), 5)
        self.assertIn(b"Document Change Monitor", urllib.request.urlopen(f"http://127.0.0.1:{port}/").read())
        with self.assertRaises(urllib.error.HTTPError): get("/api/compare?doc=Nope&a=v1&b=v2")
        srv.shutdown(); srv.server_close()
        self.assertEqual(before, snapshot(MOCK))

class TestRealDriveSnapshot(unittest.TestCase):
    """Documents captured read-only from the shared LTID Drive folder."""
    def setUp(self): self.src = LocalFolderSource(SNAP, "snapshot")
    def test_expense_policy_real_versions_detected(self):
        docs = {d["name"]: [v["id"] for v in d["versions"]] for d in self.src.documents()}
        self.assertEqual(docs["Policy_Expense"], ["v1", "v2"])
        r = compare_versions(self.src, "Policy_Expense", "v1", "v2")
        self.assertEqual(r["origins"]["old"]["origin"], "REAL"); self.assertEqual(r["origins"]["new"]["origin"], "REAL")
        self.assertEqual(r["origins"]["new"]["drive_id"], "1xCJWu-5BKSGN_-Qil5dQZBq8_a827IbI")
        txt = " ".join(" ".join(i["reasons"]) for i in r["interpretation"]["items"].values())
        for token in ("30 calendar days", "10 calendar days", "JPY 12,000", "JPY 15,000", "JPY 2,000"): self.assertIn(token, txt)
        self.assertEqual(r["interpretation"]["summary"]["max_severity"], "high")
    def test_mock_files_are_labelled_and_not_real(self):
        r = compare_versions(self.src, "03_RAG_Requirements", "v1", "v2")
        self.assertEqual(r["origins"]["old"]["origin"], "REAL (text rendition; renamed _v1 locally)")
        self.assertTrue(r["origins"]["new"]["origin"].startswith("MOCK")); self.assertIsNone(r["origins"]["new"]["drive_id"])
        removed = [c for c in r["changes"] if c["kind"] == "removed" and any("Versions" in x for x in c["before"])]
        self.assertEqual(len(removed), 1)  # the superseded-version requirement was dropped in the mock revision
        self.assertEqual(r["interpretation"]["items"][removed[0]["id"]]["severity"], "high")
    def test_snapshot_untouched_by_scan(self):
        before = snapshot(SNAP); scan_all(self.src, Store(":memory:")); self.assertEqual(before, snapshot(SNAP))
    def test_every_manifest_entry_exists(self):
        m = json.loads((SNAP / "MANIFEST.json").read_text())
        for f in m["files"]: self.assertTrue((SNAP / f["snapshot"]).exists(), f["snapshot"])
        self.assertEqual(sum(f["drive_id"] is None for f in m["files"]), 2)  # exactly the 2 mock files

if __name__ == "__main__": unittest.main(verbosity=2)
