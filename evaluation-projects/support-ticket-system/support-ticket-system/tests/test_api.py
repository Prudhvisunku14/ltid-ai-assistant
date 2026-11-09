from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import GOOD, ExplodingClassifier, FakeClassifier


def make(client, **extra):
    r = client.post("/api/tickets", json={**GOOD, **extra})
    return r


def test_submit_ticket_is_classified_by_ai(client, fake):
    r = make(client)
    assert r.status_code == 201
    t = r.json()
    assert t["category"] == "technical_issue" and t["category_source"] == "ai"
    assert t["priority"] == "high" and t["priority_reasoning"] == "Customer is blocked."
    assert t["status"] == "open"
    assert t["ai_category"] == "technical_issue"
    assert fake.calls == 1


def test_validation_rejects_bad_input(client):
    assert client.post("/api/tickets", json={"title": "ab", "description": "long enough text"}).status_code == 422
    assert client.post("/api/tickets", json={"title": "Fine title", "description": ""}).status_code == 422
    assert client.post("/api/tickets", json={"description": "no title here"}).status_code == 422
    assert client.post("/api/tickets", json={**GOOD, "category": "nonsense"}).status_code == 422


def test_disable_auto_classification_uses_manual_category(client, fake):
    r = make(client, auto_classify=False, category="billing")
    assert r.status_code == 201
    t = r.json()
    assert t["category"] == "billing" and t["category_source"] == "manual"
    assert t["priority"] == "medium" and t["priority_source"] == "default"
    assert fake.calls == 0  # the LLM was never consulted


def test_manual_mode_requires_category(client):
    assert make(client, auto_classify=False).status_code == 422


def test_manual_priority_in_manual_mode(client):
    t = make(client, auto_classify=False, category="general_inquiry", priority="low").json()
    assert t["priority"] == "low" and t["priority_source"] == "manual"


def test_user_values_win_over_ai_but_ai_suggestion_is_kept(client, fake):
    t = make(client, category="billing").json()
    assert t["category"] == "billing" and t["category_source"] == "manual"
    assert t["ai_category"] == "technical_issue"
    assert t["priority_source"] == "ai"
    assert fake.calls == 1


def test_no_llm_call_when_user_gives_both_values(client, fake):
    make(client, category="billing", priority="low")
    assert fake.calls == 0


def test_global_switch_disables_auto_classification(db_path):
    fake = FakeClassifier()
    c = TestClient(create_app(Settings(database_path=db_path, auto_classify_enabled=False), fake))
    assert c.get("/api/config").json()["auto_classify_enabled"] is False
    assert make(c).status_code == 422  # auto requested but switched off, no category
    ok = make(c, category="billing")
    assert ok.status_code == 201 and ok.json()["category_source"] == "manual"
    assert fake.calls == 0


def test_classifier_crash_does_not_block_submission(db_path):
    c = TestClient(create_app(Settings(database_path=db_path), ExplodingClassifier()))
    r = make(c)
    assert r.status_code == 201
    assert r.json()["category_source"] == "rules"


def test_manual_correction_of_category_and_priority(client):
    tid = make(client).json()["id"]
    r = client.patch(f"/api/tickets/{tid}", json={"category": "billing", "priority": "low"})
    t = r.json()
    assert r.status_code == 200
    assert (t["category"], t["category_source"]) == ("billing", "manual")
    assert (t["priority"], t["priority_source"]) == ("low", "manual")
    assert t["ai_category"] == "technical_issue" and t["ai_priority"] == "high"


def test_status_workflow(client):
    tid = make(client).json()["id"]
    for status in ("in_progress", "resolved", "open"):
        r = client.patch(f"/api/tickets/{tid}", json={"status": status})
        assert r.status_code == 200 and r.json()["status"] == status
    # a status change must not mark the AI classification as manual
    assert r.json()["category_source"] == "ai"


def test_update_validation_and_404(client):
    tid = make(client).json()["id"]
    assert client.patch(f"/api/tickets/{tid}", json={"status": "closed"}).status_code == 422
    assert client.patch(f"/api/tickets/{tid}", json={}).status_code == 422
    assert client.patch("/api/tickets/999", json={"status": "resolved"}).status_code == 404
    assert client.get("/api/tickets/999").status_code == 404


def test_list_and_filters(client):
    a = make(client).json()["id"]
    make(client, auto_classify=False, category="billing")
    client.patch(f"/api/tickets/{a}", json={"status": "resolved"})
    assert len(client.get("/api/tickets").json()) == 2
    assert [t["id"] for t in client.get("/api/tickets?status=resolved").json()] == [a]
    assert len(client.get("/api/tickets?category=billing").json()) == 1
    assert client.get("/api/tickets?status=bogus").status_code == 422


def test_dashboard_stats(client):
    assert client.get("/api/stats").json()["total"] == 0
    a = make(client).json()["id"]
    make(client, auto_classify=False, category="billing", priority="urgent")
    client.patch(f"/api/tickets/{a}", json={"status": "in_progress", "category": "general_inquiry"})
    s = client.get("/api/stats").json()
    assert s["total"] == 2
    assert s["by_status"] == {"open": 1, "in_progress": 1, "resolved": 0}
    assert s["by_category"] == {"technical_issue": 0, "billing": 1, "general_inquiry": 1}
    assert s["by_priority"]["urgent"] == 1 and s["by_priority"]["high"] == 1
    assert s["manually_corrected"] == 1


def test_tickets_persist_across_restarts(db_path):
    c1 = TestClient(create_app(Settings(database_path=db_path), FakeClassifier()))
    tid = make(c1).json()["id"]
    c2 = TestClient(create_app(Settings(database_path=db_path), FakeClassifier()))
    assert c2.get(f"/api/tickets/{tid}").json()["title"] == GOOD["title"]


def test_markup_is_stored_verbatim_and_dashboard_is_served(client):
    t = make(client, title="<script>alert(1)</script>").json()
    assert t["title"] == "<script>alert(1)</script>"  # escaping happens in the UI (esc())
    page = client.get("/")
    assert page.status_code == 200 and "Support Ticket Manager" in page.text
