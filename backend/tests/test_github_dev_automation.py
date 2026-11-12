"""GitHub Development Automation System (devbot) as shown in the dashboard. The backend only reads files and recorded
evidence; the counts below are what evaluation-projects/scripts/collect_external.py recorded from real runs."""
import json
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
PID = "github-dev-automation"
SUITES = {"project-tests": 9, "web-tests": 21, "browser-ui": 17}
TOTAL = sum(SUITES.values())


def test_card_is_listed_once_with_honest_status():
    ps = c.get("/api/projects").json()
    p = next(x for x in ps if x["id"] == PID)
    assert p["name"] == "GitHub Development Automation System" and p["data_kind"] == "real" and p["status"] == "built"
    assert p["launch_label"] == "Launch devbot" and p["preview_url"].endswith(":8009")
    assert p["test_status"] == f"{TOTAL} passed, 0 failed" and p["build_status"] == "passing"
    assert [x["id"] for x in ps].count(PID) == 1
    assert "never merges" in p["description"] and "own OpenAI API key" in p["description"]
    assert "never run against the live OpenAI API" in p["import_note"] and "never run" in p["import_note"]


def test_every_suite_is_recorded_and_fully_parsed():
    t = c.get(f"/api/projects/{PID}/tests").json()
    assert t["totals"] == {"passed": TOTAL, "failed": 0}
    suites = {s["id"]: s for s in t["suites"]}
    assert {k: len(v["cases"]) for k, v in suites.items()} == SUITES
    assert all(s["parse_complete"] and s["exit_code"] == 0 for s in suites.values())
    names = {x["name"] for s in t["suites"] for x in s["cases"]}
    assert {"test_merge_and_force_blocked", "test_live_creates_branch_not_merge", "test_server_ignores_keys_in_its_own_environment",
            "test_key_echoed_by_the_api_is_scrubbed", "gpt_mode_asks_for_the_users_api_key_in_a_masked_field",
            "key_is_not_in_url_or_browser_storage"} <= names


def test_source_tree_shows_devbot_and_the_web_layer_but_no_junk():
    def names(n): return [n["path"]] + [p for ch in n["children"] for p in names(ch)]
    t = names(c.get(f"/api/projects/{PID}/tree").json())
    for f in ("GitHub Development Automation System/devbot/pipeline.py", "GitHub Development Automation System/devbot/safety.py",
              "web_demo/server.py", "web_demo/static/index.html", "web_demo/Dockerfile", "web_demo/tests/test_server.py"):
        assert f in t, f
    assert not any("__pycache__" in x or ".git/" in x or x.endswith(".zip") for x in t)
    f = c.get(f"/api/projects/{PID}/file", params={"path": "GitHub Development Automation System/devbot/safety.py"}).json()
    assert f["language"] == "python" and "PROTECTED_BRANCHES" in f["content"]


def test_traversal_is_blocked():
    for bad in ("../../../../../../../../etc/passwd", "../" * 12 + "windows/win.ini", "../prompt-b-weather/source/README.md"):
        assert c.get(f"/api/projects/{PID}/file", params={"path": bad}).status_code in (400, 404)


def test_analysis_discloses_what_was_not_verified():
    a = c.get(f"/api/projects/{PID}/analysis").json()
    assert any(r["id"] == "X1" and "own OpenAI API key" in r["text"] for r in a["requirements"])
    lim = " ".join(a["limitations"])
    assert "never been called against the live OpenAI API" in lim and "never run" in lim and "executes that repository's code" in lim
    blob = json.dumps(a)
    assert "sk-" not in blob and "ghp_" not in blob                              # no key-shaped strings in the evidence


def test_preview_report_screenshot_and_overview_counts():
    p = c.get(f"/api/projects/{PID}/preview").json()
    assert p["url"].endswith(":8009") and "server.py" in p["start_hint"]
    assert c.get("/api/preview-config").json()["previews"][PID].endswith(":8009")
    md = c.get(f"/api/projects/{PID}/report").json()["markdown"]
    assert md.startswith("# Evaluation Report — GitHub Development Automation System") and f"{TOTAL} passed, 0 failed" in md
    assert c.get(f"/api/projects/{PID}/screenshot/{PID}-home").headers["content-type"] == "image/png"
    names = {s["name"] for s in c.get(f"/api/projects/{PID}/screenshots").json()}
    assert {"devbot-key-prompt", "devbot-plan-approval", "devbot-result", "devbot-mobile"} <= names
    assert c.get("/api/overview").json()["summaries"][PID]["tests_passed"] == TOTAL
