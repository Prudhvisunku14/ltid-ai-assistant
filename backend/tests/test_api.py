from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

def test_health(): assert c.get("/health").json() == {"status": "ok"}
def test_projects_has_ten_and_prompts_a_b_are_real():
    ps = c.get("/api/projects").json(); assert len(ps) == 14
    assert [p["id"] for p in ps[:2]] == ["prompt-a", "prompt-b"] and ps[0]["data_kind"] == "real" and ps[1]["data_kind"] == "real"
def test_tree_and_diff_reflect_real_changes():
    d = {x["path"]: x for x in c.get("/api/projects/prompt-a/diff").json()}
    assert d["app.js"]["status"] == "modified" and d["data/projects-data.js"]["status"] == "added"
def test_path_traversal_blocked():
    assert c.get("/api/projects/prompt-a/file", params={"path": "../../../etc/passwd"}).status_code in (400, 404)
def test_placeholder_project_has_no_fake_data():
    assert c.get("/api/projects/ecommerce/tests").status_code == 404
def test_report_states_pr_not_created():
    md = c.get("/api/projects/prompt-a/report").json()["markdown"]; assert "not_created" in md and "pending" in md
def test_pr_url_is_null():
    assert c.get("/api/projects/prompt-a/git").json()["draft_pr"]["url"] is None

# ---------------------------------------------------------------- Prompt A keeps working next to Prompt B
def test_prompt_a_endpoints_still_work():
    for ep in ("analysis", "timeline", "tests", "git", "summary", "tree", "diff", "screenshots", "report", "preview"):
        assert c.get(f"/api/projects/prompt-a/{ep}").status_code == 200, ep
    assert c.get("/api/projects/prompt-a/screenshot/desktop-1280-fold").headers["content-type"] == "image/png"
    assert c.get("/api/projects/prompt-a/report/download").headers["content-disposition"].endswith('prompt-a-evaluation-report.md"')
    assert c.get("/api/projects/prompt-a/evaluation").status_code == 404          # Prompt A has no weather evaluation

# ---------------------------------------------------------------- Prompt B
def test_prompt_b_card_is_complete_and_honest():
    p = c.get("/api/projects/prompt-b").json()
    assert p["name"] == "Prompt B — Weather Forecasting Demo" and p["client"] == "Eastbay City Lab" and p["synthetic"] is True
    assert p["category"] == "Data Science / Machine Learning" and p["repo"] == "LTID-rep/ltid-ai-competition-weather"
    assert "stdlib only" in p["stack"] and "unittest" in p["stack"] and p["stack"][0].startswith("Python")
    assert p["build_status"] == "passing" and "0 failed" in p["test_status"] and p["thumbnail"].endswith("desktop-1280-fold")
    assert "ZIP snapshot" in p["import_note"]
def test_prompt_b_tree_diff_show_actual_files():
    d = {x["path"]: x for x in c.get("/api/projects/prompt-b/diff").json()}
    assert d["weather_app/data.py"]["status"] == "added" and d["weather_app/evaluation.py"]["status"] == "added"
    assert d["weather_app/core.py"]["status"] == "modified" and d["weather_app/core.py"]["additions"] > 0
    assert "data/weather_history.csv" not in d                       # the synthetic dataset is unchanged
    assert not [x for x in d.values() if x["status"] == "deleted"]
    def names(n): return [n["path"]] + [p for ch in n["children"] for p in names(ch)]
    t = names(c.get("/api/projects/prompt-b/tree").json())
    assert "weather_app/forecast.py" in t and "tests/test_evaluation.py" in t and "weather_app/web/app.js" in t
    assert not any("__pycache__" in x or x.startswith(".git/") for x in t)
def test_prompt_b_file_content_and_original():
    f = c.get("/api/projects/prompt-b/file", params={"path": "weather_app/core.py"}).json()
    assert f["language"] == "python" and "load_rows" in f["content"] and f["original"] and f["change"] == "modified"
    assert c.get("/api/projects/prompt-b/file", params={"path": "weather_app/data.py"}).json()["original"] is None
def test_prompt_b_path_traversal_blocked():
    for bad in ("../../../etc/passwd", "../../prompt-a-website/source/app.js", "..\\..\\x"):
        assert c.get("/api/projects/prompt-b/file", params={"path": bad}).status_code in (400, 404)
        assert c.get("/api/projects/prompt-b/raw", params={"path": bad}).status_code in (400, 404)
    assert c.get("/api/projects/prompt-b/screenshot/..%2f..%2fgit").status_code == 404
def test_prompt_b_tests_are_real_and_complete():
    t = c.get("/api/projects/prompt-b/tests").json()
    assert t["totals"]["failed"] == 0 and t["totals"]["passed"] >= 50
    names = {x["name"] for s in t["suites"] for x in s["cases"]}
    assert {"test_02_invalid_city_is_rejected_with_a_clear_message", "test_06_invalid_horizon_is_rejected", "test_11_independent_recomputation_of_heldout_mae"} <= names
def test_prompt_b_evaluation_uses_time_ordered_split_and_six_demos():
    e = c.get("/api/projects/prompt-b/evaluation").json()
    assert e["synthetic_data"] is True and "synthetic" in e["disclaimer"]
    assert len(e["demonstrations"]["cases"]) == 6 and {x["horizon_days"] for x in e["demonstrations"]["cases"]} == {1, 2, 3}
    assert len({x["city"] for x in e["demonstrations"]["cases"]}) == 2
    for city in e["evaluation"]["cities"]:
        s = city["split"]; assert s["shuffled"] is False and s["no_leakage"] and s["train_end"] < s["evaluation_start"]
    assert e["independent_check"]["all_match"] is True
    assert e["evaluation"]["overall"]["mae"] is not None and all(x["passed"] for x in e["robustness_checks"])
def test_prompt_b_downloads():
    r = c.get("/api/projects/prompt-b/evaluation/download"); assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.json()["evaluation"]
    r = c.get("/api/projects/prompt-b/report/download"); assert r.headers["content-type"].startswith("text/markdown") and r.text.startswith("# Evaluation Report")
    r = c.get("/api/projects/prompt-b/report/download.pdf"); assert r.status_code == 200 and r.content[:5] == b"%PDF-" and len(r.content) > 5000
def test_prompt_b_report_has_all_17_sections_and_states_publication_status():
    md = c.get("/api/projects/prompt-b/report").json()["markdown"]
    import re
    nums = [int(m) for m in re.findall(r"^## (\d+)\. ", md, re.M)]; assert nums == list(range(1, 18))
    assert "not_pushed" in md and "not_created" in md and "pending" in md
    assert "Imported ZIP snapshot" in md or "IMPORTED ZIP SNAPSHOT" in md
    assert "Educational demonstration using synthetic observations" in md and "MAE = " in md
def test_prompt_b_git_state_is_truthful():
    g = c.get("/api/projects/prompt-b/git").json()
    assert g["base_branch"] == "main" and g["dev_branch"] == "ltid-assistant/prompt-b-weather" and len(g["commits"]) >= 1
    if g["push"]["status"] != "pushed": assert g["draft_pr"]["url"] is None and g["draft_pr"]["status"] == "not_created"
def test_prompt_b_preview_and_screenshots():
    p = c.get("/api/projects/prompt-b/preview").json(); assert p["url"].endswith(":8002") and "weather_app --serve" in p["start_hint"]
    names = {s["name"] for s in c.get("/api/projects/prompt-b/screenshots").json()}; assert {"desktop-1280-fold", "mobile-375-full"} <= names
    assert c.get("/api/preview-config").json()["previews"]["prompt-b"].endswith(":8002")
def test_overview_counts_all_implemented_projects():
    o = c.get("/api/overview").json()
    assert o["built_projects"] == 9 and o["tests_passed"] > 100 and o["failed_builds"] == 0 and o["placeholder_projects"] == 5

def test_prompt_c_card_and_recorded_test_evidence():
    p = c.get("/api/projects/prompt-c-rag").json()
    assert p["name"] == "Prompt C — Grounded RAG" and p["data_kind"] == "imported"
    assert p["test_status"] == "29 passed, 0 failed" and p["preview_url"] is None
    t = c.get("/api/projects/prompt-c-rag/tests").json()
    assert t["totals"] == {"passed": 29, "failed": 0}
    assert len(t["suites"][0]["cases"]) == 29 and t["suites"][0]["exit_code"] == 0

def test_prompt_d_card_and_recorded_test_evidence():
    p = c.get("/api/projects/prompt-d-explicit").json()
    assert p["name"] == "Prompt D — DevPilot Explainability" and p["data_kind"] == "real"
    assert p["test_status"] == "23 passed, 0 failed" and p["preview_url"] is None
    t = c.get("/api/projects/prompt-d-explicit/tests").json()
    assert t["totals"] == {"passed": 23, "failed": 0}
    assert {s["id"] for s in t["suites"]} == {"change", "forecast", "rag", "tools", "website"}
    assert sum(len(s["cases"]) for s in t["suites"]) == 23
