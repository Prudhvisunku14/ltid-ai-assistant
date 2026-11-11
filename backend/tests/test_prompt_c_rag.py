"""Prompt C is the 'LTID AI Competition – RAG' project (evaluation-projects/ltid-ai-competition-rag-final).
The old 'Prompt C — Grounded RAG' implementation must not appear anywhere in the dashboard."""
import json
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
PID = "prompt-c-rag"
TOTAL = 51          # 18 project tests + 17 web-interface tests + 16 real-browser checks


def test_card_is_the_new_project_and_the_old_name_is_gone():
    ps = c.get("/api/projects").json()
    p = next(x for x in ps if x["id"] == PID)
    assert p["name"] == "LTID AI Competition – RAG" and p["data_kind"] == "real" and p["status"] == "built"
    assert p["category"] == "AI / Retrieval-Augmented Generation" and p["launch_label"] == "Launch RAG App"
    assert p["test_status"] == f"{TOTAL} passed, 0 failed" and p["build_status"] == "passing"
    assert p["preview_url"].endswith(":8008")
    assert "BM25 retrieval" in p["stack"] and "HTML/CSS/vanilla JS" in p["stack"]
    assert "No embeddings or vector database" in p["description"]               # the method is described honestly
    assert "local git repository" in p["import_note"] and "never run against a live model" in p["import_note"]
    blob = json.dumps(ps) + json.dumps(c.get("/api/overview").json())
    assert "Prompt C — Grounded RAG" not in blob and "ltid-ai-competition-rag-main" not in blob
    assert [x["id"] for x in ps].count(PID) == 1                                  # exactly one Prompt C


def test_all_three_suites_are_recorded_and_fully_parsed():
    t = c.get(f"/api/projects/{PID}/tests").json()
    assert t["totals"] == {"passed": TOTAL, "failed": 0}
    suites = {s["id"]: s for s in t["suites"]}
    assert set(suites) == {"project-tests", "web-tests", "browser-ui"}
    assert [len(suites[k]["cases"]) for k in ("project-tests", "web-tests", "browser-ui")] == [18, 17, 16]
    assert all(s["parse_complete"] and s["exit_code"] == 0 for s in suites.values())
    names = {x["name"] for s in t["suites"] for x in s["cases"]}
    assert {"test_hotel_limit", "test_abstains_when_unsupported", "test_a_newer_uploaded_version_supersedes_the_shipped_one",
            "test_requests_with_bodies_always_get_a_reply_even_when_rejected",
            "uploaded_document_is_retrieved_and_cited", "html_in_uploaded_text_is_shown_as_text_not_executed"} <= names


def test_source_tree_shows_the_project_and_the_web_layer():
    def names(n): return [n["path"]] + [p for ch in n["children"] for p in names(ch)]
    t = names(c.get(f"/api/projects/{PID}/tree").json())
    for f in ("prompt-c-rag/rag_app/answer.py", "prompt-c-rag/rag_app/retrieve.py", "prompt-c-rag/knowledge_base/Policy_Expense_v2_Current.txt",
              "web_demo/server.py", "web_demo/static/index.html", "web_demo/tests/test_server.py"):
        assert f in t, f
    assert not any("__pycache__" in x or ".git/" in x for x in t)
    f = c.get(f"/api/projects/{PID}/file", params={"path": "prompt-c-rag/rag_app/answer.py"}).json()
    assert f["language"] == "python" and "NOT_FOUND" in f["content"]


def test_traversal_is_blocked():
    for bad in ("../../../../../../../../etc/passwd", "../" * 12 + "windows/win.ini", "../prompt-b-weather/source/README.md"):
        assert c.get(f"/api/projects/{PID}/file", params={"path": bad}).status_code in (400, 404)


def test_analysis_states_requirements_and_the_known_gap():
    a = c.get(f"/api/projects/{PID}/analysis").json()
    assert any(r["id"] == "R5" and r["area"] == "Versions" for r in a["requirements"])
    assert any("INTERNATIONAL" in l.upper() and "domestic" in l.lower() for l in a["limitations"])     # the wrong near-miss answer is disclosed
    assert {i["id"] for i in a["existing_issues"]} == {"N1", "N2"}
    assert any(t["name"].startswith("Embeddings") and t["decision"] == "Not used" for t in a["tools"])


def test_git_state_is_the_projects_real_local_repository():
    g = c.get(f"/api/projects/{PID}/git").json()
    assert g["dev_branch"] == "feature/rag-system" and len(g["commits"]) == 1
    assert g["push"]["status"] == "not_pushed" and g["draft_pr"]["url"] is None


def test_preview_report_screenshot_and_overview_counts():
    p = c.get(f"/api/projects/{PID}/preview").json()
    assert p["url"].endswith(":8008") and "server.py" in p["start_hint"]
    md = c.get(f"/api/projects/{PID}/report").json()["markdown"]
    assert md.startswith("# Evaluation Report — LTID AI Competition – RAG") and f"{TOTAL} passed, 0 failed" in md
    assert c.get(f"/api/projects/{PID}/screenshot/{PID}-home").headers["content-type"] == "image/png"
    assert c.get("/api/overview").json()["summaries"][PID]["tests_passed"] == TOTAL
    assert c.get("/api/preview-config").json()["previews"][PID].endswith(":8008")
