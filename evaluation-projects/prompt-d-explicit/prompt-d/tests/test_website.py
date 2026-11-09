import shutil, tempfile, unittest
from pathlib import Path
from devpilot import website

ROOT = Path(__file__).resolve().parent.parent
SPEC, REPO = ROOT / "data/drive_mock/website_spec.docx", ROOT / "workspace/site_repo"


class T(unittest.TestCase):
    def test_reads_requirements_from_real_docx(self):
        ids = [r[0] for r in website.read_docx_requirements(SPEC)]
        self.assertEqual(ids, ["REQ-1", "REQ-2", "REQ-3", "REQ-4"])

    def test_end_to_end_and_idempotent(self):
        work = Path(tempfile.mkdtemp()) / "w"
        r = website.run_website(SPEC, REPO, work)
        self.assertTrue(all(c["passed"] in (True, None) for c in r["checks"]), [c for c in r["checks"] if c["passed"] is False])
        self.assertTrue((work / "contact.html").exists())
        before = {p.name: p.read_text() for p in work.glob("*") if p.is_file()}
        website.implement(work, website.plan(r["requirements"]))
        after = {p.name: p.read_text() for p in work.glob("*") if p.is_file()}
        self.assertEqual({k: v for k, v in before.items() if k != "PR_DRAFT.md"}, {k: v for k, v in after.items() if k != "PR_DRAFT.md"})
        self.assertIn("NOT CREATED", r["git"]["pr"])  # no remote here: never pretend a PR exists

    def test_checks_catch_a_broken_site(self):
        work = Path(tempfile.mkdtemp()) / "w"; shutil.copytree(REPO, work)
        failed = [c for c in website.run_checks(work) if c["passed"] is False]
        self.assertTrue(failed)  # the untouched original site must fail the spec checks

    def test_unsupported_requirement_reported_not_faked(self):
        work = Path(tempfile.mkdtemp()) / "w"; shutil.copytree(REPO, work)
        res = website.implement(work, website.plan([("REQ-9", "Integrate a payment gateway")]))
        self.assertIn("UNSUPPORTED", res[0]["status"])
