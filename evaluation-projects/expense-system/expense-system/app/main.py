"""Flask HTTP layer (thin). Demo identity: X-User-Id header (no real authentication)."""
import os
from flask import Flask, Response, jsonify, request, send_from_directory
from . import policy as P, service as S

STATIC = os.path.join(os.path.dirname(__file__), "static")


def create_app(db_path=None, seed_demo=False):
    app = Flask(__name__, static_folder=STATIC, static_url_path="/static")
    path = db_path or os.environ.get("EXPENSE_DB", "expenses.db")
    S.init_db(path)
    if seed_demo:
        from seed import seed_all
        seed_all(path)

    @app.errorhandler(S.ExpenseError)
    def on_error(e):
        return jsonify(error=e.message), e.status

    def user():
        raw = request.headers.get("X-User-Id", "")
        u = S.get_employee(path, int(raw)) if raw.isdigit() else None
        if not u:
            raise S.ExpenseError("Select a user (X-User-Id header missing or unknown).", 401)
        return u

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/api/users")                      # demo user picker only
    def users():
        with S.db(path) as c:
            return jsonify(users=[dict(r) for r in c.execute("SELECT * FROM employees ORDER BY id")])

    @app.get("/api/policy")
    def policy():
        return jsonify(source=P.POLICY_FILE, effective=P.POLICY_EFFECTIVE, url=P.POLICY_URL,
                       rules=P.RULES, not_specified=P.NOT_SPECIFIED, categories=P.CATEGORIES,
                       constants={"window_days": P.SUBMISSION_WINDOW_DAYS, "receipt_threshold_jpy": P.RECEIPT_THRESHOLD_JPY,
                                  "hotel_cap_per_night_jpy": P.HOTEL_CAP_PER_NIGHT_JPY},
                       special={"domestic_travel": P.DOMESTIC_TRAVEL, "international_travel": P.INTERNATIONAL_TRAVEL,
                                "domestic_hotel": P.DOMESTIC_HOTEL})

    @app.post("/api/expenses")
    def submit():
        return jsonify(S.submit_expense(path, user(), request.get_json(silent=True) or {})), 201

    @app.get("/api/expenses")
    def listing():
        a = request.args
        return jsonify(expenses=S.list_expenses(path, user(), a.get("scope", "visible"), a.get("status"), a.get("month")))

    @app.get("/api/expenses/<int:eid>")
    def one(eid):
        return jsonify(S.get_expense(path, user(), eid))

    @app.post("/api/expenses/<int:eid>/decision")
    def decision(eid):
        b = request.get_json(silent=True) or {}
        return jsonify(S.decide(path, user(), eid, b.get("decision"), b.get("comment")))

    @app.get("/api/decisions")
    def history():
        eid = request.args.get("expense_id")
        return jsonify(decisions=S.decision_history(path, user(), int(eid) if eid and eid.isdigit() else None))

    @app.get("/api/reports/monthly")
    def report():
        return jsonify(S.monthly_report(path, user(), request.args.get("month")))

    @app.get("/api/reports/monthly.csv")
    def report_csv():
        m, v = request.args.get("month"), request.args.get("view", "summary")
        body = S.report_csv(path, user(), m, v)
        return Response(body, mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=expenses-{m}-{v}.csv"})

    return app
