from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
PIDS = {"appointment-booking": 25, "expense-system": 64, "support-ticket-system": 32, "docchange": 23}


def test_three_uploaded_projects_are_in_gallery_as_real_cards():
    ps = {p["id"]: p for p in c.get("/api/projects").json()}
    for pid, n in PIDS.items():
        p = ps[pid]
        assert p["data_kind"] == "real" and p["status"] == "built", pid
        assert p["build_status"] == "passing" and p["test_status"] == f"{n} passed, 0 failed", (pid, p["test_status"])
        assert p["preview_url"].startswith("http://localhost:800"), pid
        assert p["import_note"].startswith("Uploaded folder")
    assert ps["appointment-booking"]["client"] == "Kaizen Consulting"
    assert ps["expense-system"]["client"].startswith("Northstar Services")
    assert ps["support-ticket-system"]["client"] is None                  # not stated in the README: not invented
    assert ps["expense-system"]["launch_label"] == "Launch Expense App"


def test_totals_include_the_new_projects():
    o = c.get("/api/overview").json()
    assert o["summaries"]["expense-system"]["tests_passed"] == 64
    assert o["summaries"]["appointment-booking"]["tests_passed"] == 25
    assert o["summaries"]["support-ticket-system"]["tests_passed"] == 32
    assert o["built_projects"] >= 8


def test_tests_endpoint_is_real_and_parsed_completely():
    for pid, n in PIDS.items():
        t = c.get(f"/api/projects/{pid}/tests").json()
        assert t["totals"]["passed"] == n and t["totals"]["failed"] == 0, pid
        suite = t["suites"][0]
        assert suite["parse_complete"] is True and suite["parsed_count"] == n, pid
        assert suite["exit_code"] == 0


def test_support_suite_includes_parametrised_names_with_spaces():
    names = {x["name"] for x in c.get("/api/projects/support-ticket-system/tests").json()["suites"][0]["cases"]}
    assert any("Site is down" in n for n in names)


def test_tree_lists_real_files_and_nothing_is_marked_changed():
    def names(n): return [n["path"]] + [p for ch in n["children"] for p in names(ch)]
    t = names(c.get("/api/projects/appointment-booking/tree").json())
    assert "app/booking.py" in t and "tests/test_booking.py" in t and "run.py" in t
    assert not any("__pycache__" in x for x in t)
    assert c.get("/api/projects/appointment-booking/diff").json() == []     # no baseline exists


def test_file_content_and_traversal_are_safe():
    f = c.get("/api/projects/expense-system/file", params={"path": "app/service.py"}).json()
    assert f["language"] == "python" and "def " in f["content"] and f["original"] == f["content"]
    for pid in PIDS:
        for bad in ("../../../../../../../../etc/passwd", "../" * 12 + "windows/win.ini", r"..\..\..\..\..\..\..\x"):
            assert c.get(f"/api/projects/{pid}/file", params={"path": bad}).status_code in (400, 404)


def test_analysis_timeline_git_report_and_preview():
    for pid in PIDS:
        a = c.get(f"/api/projects/{pid}/analysis").json()
        assert a["requirements"] and a["tools"] and a["limitations"], pid
        assert c.get(f"/api/projects/{pid}/timeline").json()[0]["status"] == "completed"
        g = c.get(f"/api/projects/{pid}/git").json()
        assert g["push"]["status"] == "not_pushed" and g["draft_pr"]["url"] is None
        md = c.get(f"/api/projects/{pid}/report").json()["markdown"]
        assert md.startswith("# Evaluation Report") and f"{PIDS[pid]} passed, 0 failed" in md
        assert c.get(f"/api/projects/{pid}/preview").json()["url"].startswith("http://localhost:800")


def test_live_screenshot_is_served_as_png():
    r = c.get("/api/projects/appointment-booking/screenshot/appointment-booking-home")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert c.get("/api/projects/appointment-booking/screenshot/..%2F..%2Fx").status_code == 404
