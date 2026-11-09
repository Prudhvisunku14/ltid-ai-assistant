"""Tests for the Expense Management System. Clock frozen at 2026-11-10 (Japan time).
Rule IDs (R1-R5, S1-S3) refer to app/policy.py and trace to Policy_Expense_v2_Current.txt."""
import csv, io
from datetime import date
import pytest
from app import service as S
from app.main import create_app
import seed

TODAY = date(2026, 11, 10)
KENJI, HARUKA, YUI, DAICHI, MEI, REN, AKARI, NAOKI = 2, 1, 3, 4, 5, 6, 7, 8


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(S, "today_jst", lambda: TODAY)


@pytest.fixture
def path(tmp_path):
    p = str(tmp_path / "t.db")
    S.init_db(p)
    seed.seed_employees(p)
    return p


@pytest.fixture
def seeded(tmp_path):
    p = str(tmp_path / "s.db")
    app = create_app(p, seed_demo=True)
    return app


def H(uid):
    return {"X-User-Id": str(uid)}


@pytest.fixture
def client(path):
    return create_app(path).test_client()


def post(client, uid, **kw):
    d = dict(expense_date="2026-11-09", amount_jpy=1000, category="Meals", description="Lunch")
    d.update(kw)
    return client.post("/api/expenses", json=d, headers=H(uid))


def decide(client, uid, eid, decision="approved", comment=None):
    return client.post(f"/api/expenses/{eid}/decision", json={"decision": decision, "comment": comment}, headers=H(uid))


# ================= R1: 10-day submission window (v2; v1's 30 days must NOT apply)
def test_r1_exactly_10_days_old_accepted(client):
    assert post(client, KENJI, expense_date="2026-10-31").status_code == 201


def test_r1_11_days_old_rejected_and_cites_policy(client):
    r = post(client, KENJI, expense_date="2026-10-30")
    assert r.status_code == 422
    assert "Policy_Expense_v2_Current.txt" in r.get_json()["error"] and "2026-10-01" in r.get_json()["error"]


def test_r1_v1_thirty_day_window_not_used(client):
    assert post(client, KENJI, expense_date="2026-10-20").status_code == 422   # 21 days old: ok under v1, not v2


def test_s1_future_date_rejected(client):
    assert post(client, KENJI, expense_date="2026-11-11").status_code == 400


# ================= R2: receipts at JPY 2,000+
def test_r2_1999_needs_no_receipt(client):
    assert post(client, KENJI, amount_jpy=1999).status_code == 201


def test_r2_2000_without_receipt_rejected(client):
    r = post(client, KENJI, amount_jpy=2000)
    assert r.status_code == 422 and "receipt" in r.get_json()["error"].lower()


def test_r2_2000_with_receipt_ok(client):
    assert post(client, KENJI, amount_jpy=2000, receipt_ref="R-1").status_code == 201


def test_r2_blank_receipt_counts_as_missing(client):
    assert post(client, KENJI, amount_jpy=5000, receipt_ref="   ").status_code == 422


# ================= R3: domestic travel needs pre-trip manager approval
TRAVEL = dict(category="Travel - Domestic", amount_jpy=12000, receipt_ref="R", trip_start="2026-11-08", expense_date="2026-11-09")


def test_r3_missing_trip_fields_rejected(client):
    assert post(client, KENJI, **TRAVEL).status_code == 400


def test_r3_pre_approval_before_trip_ok(client):
    assert post(client, KENJI, pre_approval_date="2026-11-05", **TRAVEL).status_code == 201


@pytest.mark.parametrize("pre", ["2026-11-08", "2026-11-09"])
def test_r3_pre_approval_not_before_trip_rejected(client, pre):
    r = post(client, KENJI, pre_approval_date=pre, **TRAVEL)
    assert r.status_code == 422 and "before the trip" in r.get_json()["error"]


def test_r3_trip_start_after_expense_rejected(client):
    t = dict(TRAVEL, trip_start="2026-11-10")
    assert post(client, KENJI, pre_approval_date="2026-11-05", **t).status_code == 400


def test_non_travel_does_not_need_trip_fields(client):
    assert post(client, KENJI).status_code == 201


# ================= R4: international travel -> manager AND finance
INTL = dict(category="Travel - International", amount_jpy=150000, receipt_ref="TKT")


def test_r4_requires_both_approvals_manager_first(client):
    e = post(client, MEI, **INTL).get_json()
    assert e["required_approvals"] == ["manager", "finance"] and e["awaiting"] == ["manager", "finance"]
    a = decide(client, DAICHI, e["id"]).get_json()
    assert a["status"] == "pending" and a["awaiting"] == ["finance"]
    b = decide(client, AKARI, e["id"]).get_json()
    assert b["status"] == "approved" and b["awaiting"] == []


def test_r4_finance_first_then_manager(client):
    e = post(client, MEI, **INTL).get_json()
    assert decide(client, AKARI, e["id"]).get_json()["status"] == "pending"
    assert decide(client, DAICHI, e["id"]).get_json()["status"] == "approved"


@pytest.mark.parametrize("rejecter,other", [(DAICHI, AKARI), (AKARI, DAICHI)])
def test_r4_any_rejection_is_final(client, rejecter, other):
    e = post(client, MEI, **INTL).get_json()
    assert decide(client, rejecter, e["id"], "rejected", "no").get_json()["status"] == "rejected"
    assert decide(client, other, e["id"]).status_code == 409


def test_domestic_expense_needs_only_manager(client):
    e = post(client, KENJI).get_json()
    assert e["required_approvals"] == ["manager"]
    assert decide(client, HARUKA, e["id"]).get_json()["status"] == "approved"


def test_finance_cannot_decide_non_international(client):
    e = post(client, KENJI).get_json()
    assert decide(client, AKARI, e["id"]).status_code == 403


# ================= R5: hotel cap 15,000 per night excluding tax
def hotel(client, amount, tax, nights, uid=YUI):
    return post(client, uid, category="Hotel - Domestic", amount_jpy=amount, tax_jpy=tax, nights=nights, receipt_ref="H").get_json()


def test_r5_room_exactly_at_cap_no_excess(client):
    e = hotel(client, 16500, 1500, 1)
    assert e["cap_excess_jpy"] == 0 and e["reimbursable_jpy"] == 16500


def test_r5_one_yen_over_cap(client):
    e = hotel(client, 16501, 1500, 1)
    assert e["cap_excess_jpy"] == 1 and e["reimbursable_jpy"] == 16500


def test_r5_tax_excluded_from_cap_test(client):
    # total 17,000 > 15,000 but room is only 14,900 -> no excess
    assert hotel(client, 17000, 2100, 1)["cap_excess_jpy"] == 0


def test_r5_cap_scales_with_nights(client):
    assert hotel(client, 31500, 1500, 2)["cap_excess_jpy"] == 0          # room 30,000 = 2 x 15,000
    assert hotel(client, 33500, 1500, 2)["cap_excess_jpy"] == 2000


def test_r5_old_v1_cap_12000_not_applied(client):
    assert hotel(client, 14000, 0, 1)["cap_excess_jpy"] == 0


def test_r5_validation(client):
    assert post(client, YUI, category="Hotel - Domestic", amount_jpy=9000, receipt_ref="x").status_code == 400  # nights missing
    assert post(client, YUI, category="Hotel - Domestic", amount_jpy=9000, nights=1, tax_jpy=9001, receipt_ref="x").status_code == 400


# ================= input validation
@pytest.mark.parametrize("amt", [0, -5, 12.5, "abc", None, True])
def test_invalid_amounts(client, amt):
    assert post(client, KENJI, amount_jpy=amt).status_code == 400


def test_invalid_category_description_date(client):
    assert post(client, KENJI, category="Yacht").status_code == 400
    assert post(client, KENJI, description="  ").status_code == 400
    assert post(client, KENJI, expense_date="11/09/2026").status_code == 400


def test_manager_without_approver_cannot_submit(client):
    r = post(client, NAOKI)
    assert r.status_code == 422 and "approving manager" in r.get_json()["error"]


# ================= status tracking & decisions
def test_new_expense_is_pending_then_approved_or_rejected(client):
    a, b = post(client, KENJI).get_json(), post(client, KENJI, description="Other").get_json()
    assert a["status"] == b["status"] == "pending"
    assert decide(client, HARUKA, a["id"]).get_json()["status"] == "approved"
    assert decide(client, HARUKA, b["id"], "rejected", "not business").get_json()["status"] == "rejected"
    s = {e["id"]: e["status"] for e in client.get("/api/expenses?scope=mine", headers=H(KENJI)).get_json()["expenses"]}
    assert s == {a["id"]: "approved", b["id"]: "rejected"}


def test_decision_is_final(client):
    e = post(client, KENJI).get_json()
    decide(client, HARUKA, e["id"])
    r = decide(client, HARUKA, e["id"], "rejected")
    assert r.status_code == 409
    assert client.get(f"/api/expenses/{e['id']}", headers=H(KENJI)).get_json()["status"] == "approved"


def test_self_approval_blocked(client):
    e = post(client, HARUKA).get_json()
    assert decide(client, HARUKA, e["id"]).status_code == 403


def test_wrong_manager_and_employee_cannot_decide(client):
    e = post(client, KENJI).get_json()
    assert decide(client, DAICHI, e["id"]).status_code == 404      # other team's manager can't even see it
    assert decide(client, YUI, e["id"]).status_code == 404         # peer employee
    assert decide(client, KENJI, e["id"]).status_code == 403       # self


def test_bad_decision_value(client):
    e = post(client, KENJI).get_json()
    assert decide(client, HARUKA, e["id"], "maybe").status_code == 400


# ================= approval history
def test_history_records_who_what_when_comment(client):
    e = post(client, MEI, **INTL).get_json()
    decide(client, DAICHI, e["id"], "approved", "ok by manager")
    decide(client, AKARI, e["id"], "approved", "ok by finance")
    h = client.get(f"/api/decisions?expense_id={e['id']}", headers=H(AKARI)).get_json()["decisions"]
    assert [(d["role"], d["approver_name"], d["decision"], d["comment"]) for d in reversed(h)] == [
        ("manager", "Daichi Ito", "approved", "ok by manager"), ("finance", "Akari Fujita", "approved", "ok by finance")]
    assert all(d["decided_at"] for d in h)


def test_history_includes_rejections_and_is_append_only(client):
    e = post(client, KENJI).get_json()
    decide(client, HARUKA, e["id"], "rejected", "dup")
    decide(client, HARUKA, e["id"], "approved")                    # refused
    h = client.get("/api/decisions", headers=H(HARUKA)).get_json()["decisions"]
    assert len(h) == 1 and h[0]["decision"] == "rejected"


def test_history_visibility(client):
    e = post(client, KENJI).get_json()
    decide(client, HARUKA, e["id"])
    assert len(client.get("/api/decisions", headers=H(KENJI)).get_json()["decisions"]) == 1     # own
    assert client.get("/api/decisions", headers=H(YUI)).get_json()["decisions"] == []           # peer
    assert client.get("/api/decisions", headers=H(DAICHI)).get_json()["decisions"] == []        # other team


# ================= access control
def test_requires_identity(client):
    assert client.get("/api/expenses").status_code == 401
    assert client.get("/api/expenses", headers=H(999)).status_code == 401


def test_visibility_rules(client):
    a = post(client, KENJI).get_json()
    post(client, MEI)
    ids = lambda uid: {e["employee_name"] for e in client.get("/api/expenses", headers=H(uid)).get_json()["expenses"]}
    assert ids(KENJI) == {"Kenji Mori"} and ids(HARUKA) == {"Kenji Mori"} and ids(DAICHI) == {"Mei Kobayashi"}
    assert ids(AKARI) == {"Kenji Mori", "Mei Kobayashi"}
    assert client.get(f"/api/expenses/{a['id']}", headers=H(YUI)).status_code == 404


def test_approvals_queue_lists_only_actionable(client):
    a = post(client, KENJI).get_json()
    b = post(client, MEI, **INTL).get_json()
    q = lambda uid: [e["id"] for e in client.get("/api/expenses?scope=approvals", headers=H(uid)).get_json()["expenses"]]
    assert q(HARUKA) == [a["id"]] and q(DAICHI) == [b["id"]] and q(AKARI) == [b["id"]] and q(KENJI) == []
    decide(client, DAICHI, b["id"])
    assert q(DAICHI) == []


# ================= seed data + monthly totals
def test_seed_loads_through_business_rules(seeded):
    c = seeded.test_client()
    ex = c.get("/api/expenses", headers=H(AKARI)).get_json()["expenses"]
    assert len(ex) == 12
    assert {e["status"] for e in ex} == {"pending", "approved", "rejected"}


def test_monthly_totals_by_employee_and_category(seeded):
    c = seeded.test_client()
    r = c.get("/api/reports/monthly?month=2026-10", headers=H(AKARI)).get_json()
    cell = {(x["employee"], x["category"]): x for x in r["by_employee_category"]}
    assert cell[("Kenji Mori", "Meals")]["claimed_jpy"] == 1800
    assert cell[("Kenji Mori", "Travel - Domestic")]["approved_jpy"] == 28400
    h = cell[("Yui Tanaka", "Hotel - Domestic")]
    assert (h["claimed_jpy"], h["approved_jpy"], h["approved_reimbursable_jpy"]) == (19800, 19800, 16800)
    assert cell[("Yui Tanaka", "Office Supplies")]["rejected_jpy"] == 6500
    emp = {x["employee"]: x["claimed_jpy"] for x in r["by_employee"]}
    assert emp == {"Kenji Mori": 30200, "Mei Kobayashi": 252000, "Yui Tanaka": 26300}
    assert r["grand_total"]["claimed_jpy"] == 308500 == sum(emp.values())
    assert r["grand_total"]["approved_jpy"] + r["grand_total"]["pending_jpy"] + r["grand_total"]["rejected_jpy"] == 308500


def test_month_is_by_expense_date_not_submission(seeded):
    c = seeded.test_client()
    nov = c.get("/api/reports/monthly?month=2026-11", headers=H(AKARI)).get_json()
    assert {d["id"] for d in nov["detail"]}.isdisjoint({d["id"] for d in c.get("/api/reports/monthly?month=2026-10", headers=H(AKARI)).get_json()["detail"]})
    assert nov["grand_total"]["expenses"] == 6
    assert nov["grand_total"]["claimed_jpy"] == 185000 + 3200 + 31500 + 950 + 2400 + 12300


def test_manager_report_limited_to_direct_reports(seeded):
    c = seeded.test_client()
    r = c.get("/api/reports/monthly?month=2026-10", headers=H(HARUKA)).get_json()
    assert {x["employee"] for x in r["by_employee"]} == {"Kenji Mori", "Yui Tanaka"}


def test_employee_cannot_view_reports(seeded):
    c = seeded.test_client()
    assert c.get("/api/reports/monthly?month=2026-10", headers=H(KENJI)).status_code == 403
    assert c.get("/api/reports/monthly.csv?month=2026-10", headers=H(KENJI)).status_code == 403


@pytest.mark.parametrize("m", ["2026-13", "2026-1", "abc", ""])
def test_bad_month(seeded, m):
    assert seeded.test_client().get(f"/api/reports/monthly?month={m}", headers=H(AKARI)).status_code == 400


def test_empty_month_report(seeded):
    r = seeded.test_client().get("/api/reports/monthly?month=2025-01", headers=H(AKARI)).get_json()
    assert r["grand_total"]["claimed_jpy"] == 0 and r["by_employee_category"] == []


# ================= CSV export
def parse(resp):
    assert resp.mimetype == "text/csv" and "attachment" in resp.headers["Content-Disposition"]
    txt = resp.data.decode("utf-8")
    assert txt.startswith("\ufeff")
    return list(csv.reader(io.StringIO(txt.lstrip("\ufeff"))))


def test_csv_summary_matches_json(seeded):
    c = seeded.test_client()
    rows = parse(c.get("/api/reports/monthly.csv?month=2026-10&view=summary", headers=H(AKARI)))
    assert rows[0] == ["month", "employee", "category", "expenses", "claimed_jpy", "approved_jpy", "pending_jpy", "rejected_jpy", "approved_reimbursable_jpy"]
    assert len(rows) - 1 == 6 and sum(int(r[4]) for r in rows[1:]) == 308500
    assert ["2026-10", "Yui Tanaka", "Hotel - Domestic", "1", "19800", "19800", "0", "0", "16800"] in rows


def test_csv_other_views(seeded):
    c = seeded.test_client()
    e = parse(c.get("/api/reports/monthly.csv?month=2026-10&view=by_employee", headers=H(AKARI)))
    assert [r[1] for r in e[1:]] == ["Kenji Mori", "Mei Kobayashi", "Yui Tanaka"]
    d = parse(c.get("/api/reports/monthly.csv?month=2026-11&view=detail", headers=H(AKARI)))
    assert len(d) - 1 == 6 and d[0][0] == "id"
    assert c.get("/api/reports/monthly.csv?month=2026-11&view=nope", headers=H(AKARI)).status_code == 400


def test_csv_formula_injection_neutralised(path):
    c = create_app(path).test_client()
    post(c, KENJI, description='=HYPERLINK("http://evil","x")', expense_date="2026-11-09")
    rows = parse(c.get("/api/reports/monthly.csv?month=2026-11&view=detail", headers=H(AKARI)))
    assert rows[1][4].startswith("'=")


def test_csv_commas_and_quotes_round_trip(path):
    c = create_app(path).test_client()
    post(c, KENJI, description='Dinner, "client" meeting')
    rows = parse(c.get("/api/reports/monthly.csv?month=2026-11&view=detail", headers=H(AKARI)))
    assert rows[1][4] == 'Dinner, "client" meeting'


# ================= persistence & integrity
def test_data_persists_across_restart(path):
    c1 = create_app(path).test_client()
    e = post(c1, KENJI).get_json()
    decide(c1, HARUKA, e["id"], "approved", "fine")
    c2 = create_app(path).test_client()
    got = c2.get(f"/api/expenses/{e['id']}", headers=H(KENJI)).get_json()
    assert got["status"] == "approved" and got["decisions"][0]["comment"] == "fine"


def test_reseeding_does_not_duplicate(tmp_path):
    p = str(tmp_path / "d.db")
    create_app(p, seed_demo=True); create_app(p, seed_demo=True)
    assert len(create_app(p).test_client().get("/api/expenses", headers=H(AKARI)).get_json()["expenses"]) == 12


def test_policy_endpoint_cites_current_version_only(client):
    p = client.get("/api/policy").get_json()
    assert p["source"] == "Policy_Expense_v2_Current.txt" and p["effective"] == "2026-10-01"
    assert p["constants"] == {"window_days": 10, "receipt_threshold_jpy": 2000, "hotel_cap_per_night_jpy": 15000}
    assert all(r["source"] for r in p["rules"]) and p["not_specified"]


def test_xss_text_is_stored_verbatim_for_client_escaping(client):
    e = post(client, KENJI, description="<script>x</script>").get_json()
    assert e["description"] == "<script>x</script>"   # UI escapes on render (esc())


def test_concurrent_decisions_only_one_recorded(path):
    import threading
    app = create_app(path)
    e = post(app.test_client(), KENJI).get_json()
    codes = []
    def go(d):
        codes.append(decide(app.test_client(), HARUKA, e["id"], d).status_code)
    ts = [threading.Thread(target=go, args=("approved" if i % 2 else "rejected",)) for i in range(10)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert codes.count(200) == 1 and codes.count(409) == 9
    assert len(app.test_client().get("/api/decisions", headers=H(HARUKA)).get_json()["decisions"]) == 1
