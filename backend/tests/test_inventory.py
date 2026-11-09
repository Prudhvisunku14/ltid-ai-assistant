from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)


def test_inventory_card_is_in_gallery_next_to_prompt_b():
    ids = [p["id"] for p in c.get("/api/projects").json()]
    assert ids.index("inventory") == ids.index("prompt-b") + 1
    p = c.get("/api/projects/inventory").json()
    assert p["name"] == "Inventory Management System" and p["data_kind"] == "real" and p["synthetic"] is False
    assert p["repo"].startswith("local repository") and "pushed" in p["import_note"]
    assert p["stack"][0].startswith("Python") and "SQLite" in p["stack"] and "stdlib only" in p["stack"]


def test_inventory_tests_are_real_and_complete():
    t = c.get("/api/projects/inventory/tests").json()
    assert t["totals"]["failed"] == 0 and t["totals"]["passed"] == 34
    names = {x["name"] for s in t["suites"] for x in s["cases"]}
    assert {"test_crud_lifecycle", "test_threshold_is_strictly_below", "test_favicon_request_is_204_not_404"} <= names
    assert {s["id"] for s in t["suites"]} == {"unit-http", "browser-e2e"}


def test_inventory_tree_and_diff_show_the_real_repository():
    d = {x["path"]: x for x in c.get("/api/projects/inventory/diff").json()}
    assert d["app/db.py"]["status"] == "added" and d["app/server.py"]["status"] == "added"
    assert d["README.md"]["status"] != "added"                 # the skeleton README is in the baseline
    t = c.get("/api/projects/inventory/tree").json()
    def names(n): return [n["path"]] + [p for ch in n["children"] for p in names(ch)]
    allp = names(t)
    assert "app/db.py" in allp and "static/app.js" in allp and "tests/test_db.py" in allp
    assert not any(".git/" in x for x in allp)


def test_inventory_file_and_traversal():
    f = c.get("/api/projects/inventory/file", params={"path": "app/db.py"}).json()
    assert f["language"] == "python" and ("def " in f["content"] or "class " in f["content"])
    for bad in ("../../../etc/passwd", "../../prompt-b-weather/source/service.py"):
        assert c.get("/api/projects/inventory/file", params={"path": bad}).status_code in (400, 404)


def test_inventory_timeline_git_report_and_preview():
    steps = c.get("/api/projects/inventory/timeline").json()
    assert len(steps) >= 8 and any(s["status"] == "blocked" for s in steps)
    g = c.get("/api/projects/inventory/git").json()
    assert g["push"]["status"] == "not_pushed" and g["draft_pr"]["url"] is None
    md = c.get("/api/projects/inventory/report").json()["markdown"]
    assert md.startswith("# Evaluation Report — Inventory") and "not_pushed" in md and "34 passed" in md
    assert c.get("/api/projects/inventory/preview").json()["url"].endswith(":8003")
    assert c.get("/api/projects/inventory/screenshot/main-list").headers["content-type"] == "image/png"


def test_inventory_placeholder_free_and_prompts_unchanged():
    assert c.get("/api/projects/prompt-a/tests").status_code == 200
    assert c.get("/api/projects/prompt-b/tests").status_code == 200
    assert c.get("/api/projects/inventory/evaluation").status_code == 404   # not a weather project
    o = c.get("/api/overview").json()
    assert o["summaries"]["inventory"]["tests_passed"] == 34
