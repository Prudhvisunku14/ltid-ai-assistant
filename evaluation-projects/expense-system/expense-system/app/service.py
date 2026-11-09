"""Business logic + persistence (SQLite). All money is whole JPY."""
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo
from . import policy as P

JST = ZoneInfo("Asia/Tokyo")


def today_jst():
    return datetime.now(JST).date()


def now_jst():
    return datetime.now(JST).isoformat(timespec="seconds")


class ExpenseError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


SCHEMA = """
CREATE TABLE IF NOT EXISTS employees(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('employee','manager','finance')),
    manager_id INTEGER REFERENCES employees(id));
CREATE TABLE IF NOT EXISTS expenses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    expense_date TEXT NOT NULL, amount_jpy INTEGER NOT NULL CHECK(amount_jpy>0),
    category TEXT NOT NULL, description TEXT NOT NULL,
    receipt_ref TEXT, tax_jpy INTEGER, nights INTEGER,
    trip_start TEXT, pre_approval_date TEXT,
    required_approvals TEXT NOT NULL,            -- 'manager' or 'manager,finance'
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
    submitted_on TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(              -- append-only approval history
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL REFERENCES expenses(id),
    approver_id INTEGER NOT NULL REFERENCES employees(id),
    role TEXT NOT NULL CHECK(role IN ('manager','finance')),
    decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
    comment TEXT, decided_at TEXT NOT NULL,
    UNIQUE(expense_id, role));                      -- one decision per required role
CREATE INDEX IF NOT EXISTS ix_exp_emp ON expenses(employee_id, expense_date);
"""


@contextmanager
def db(path, write=False):
    c = sqlite3.connect(path, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        if write:
            c.execute("BEGIN IMMEDIATE")
        yield c
        if write:
            c.execute("COMMIT")
    except BaseException:
        if write and c.in_transaction:
            c.execute("ROLLBACK")
        raise
    finally:
        c.close()


def init_db(path):
    with db(path) as c:
        c.executescript(SCHEMA)


# ------------------------------------------------------------------ helpers
def _date(v, field):
    try:
        return date.fromisoformat(v)
    except (TypeError, ValueError):
        raise ExpenseError(f"{field} must be a date in YYYY-MM-DD format.")


def _int(v, field, minimum):
    if isinstance(v, str) and re.fullmatch(r"\d+", v.strip()):
        v = int(v.strip())
    if isinstance(v, bool) or not isinstance(v, int):
        raise ExpenseError(f"{field} must be a whole number of yen.")
    if v < minimum:
        raise ExpenseError(f"{field} must be at least {minimum:,}.")
    return v


def _text(v, field, max_len, required=True):
    v = v.strip() if isinstance(v, str) else ""
    if required and not v:
        raise ExpenseError(f"{field} is required.")
    if len(v) > max_len:
        raise ExpenseError(f"{field} must be at most {max_len} characters.")
    return v


def get_employee(path, emp_id):
    with db(path) as c:
        r = c.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    return dict(r) if r else None


def hotel_figures(row):
    """Cap maths for domestic hotel claims (R5). Returns (cap_excess, reimbursable)."""
    amount = row["amount_jpy"]
    if row["category"] != P.DOMESTIC_HOTEL:
        return 0, amount
    room = amount - (row["tax_jpy"] or 0)
    excess = max(0, room - P.HOTEL_CAP_PER_NIGHT_JPY * row["nights"])
    return excess, amount - excess


def _detail(c, row):
    d = dict(row)
    emp = c.execute("SELECT name, manager_id FROM employees WHERE id=?", (row["employee_id"],)).fetchone()
    d["employee_name"] = emp["name"]
    d["required_approvals"] = row["required_approvals"].split(",")
    decs = [dict(x) for x in c.execute(
        "SELECT d.id, d.role, d.decision, d.comment, d.decided_at, d.approver_id, e.name AS approver_name "
        "FROM decisions d JOIN employees e ON e.id=d.approver_id WHERE d.expense_id=? ORDER BY d.id",
        (row["id"],))]
    d["decisions"] = decs
    done = {x["role"] for x in decs if x["decision"] == "approved"}
    d["awaiting"] = [r for r in d["required_approvals"] if r not in done] if row["status"] == "pending" else []
    d["cap_excess_jpy"], d["reimbursable_jpy"] = hotel_figures(row)
    return d


def can_view(c, user, row):
    if user["role"] == "finance" or row["employee_id"] == user["id"]:
        return True
    emp = c.execute("SELECT manager_id FROM employees WHERE id=?", (row["employee_id"],)).fetchone()
    return user["role"] == "manager" and emp["manager_id"] == user["id"]


def _check_can_decide(c, user, row):
    """Return the role the user would act in, or raise ExpenseError."""
    if row["status"] != "pending":
        raise ExpenseError(f"This expense is already {row['status']}; decisions are final.", 409)
    if row["employee_id"] == user["id"]:
        raise ExpenseError("You cannot decide your own expense.", 403)
    emp = c.execute("SELECT manager_id FROM employees WHERE id=?", (row["employee_id"],)).fetchone()
    required = row["required_approvals"].split(",")
    if user["role"] == "manager" and emp["manager_id"] == user["id"]:
        role = "manager"
    elif user["role"] == "finance" and "finance" in required:
        role = "finance"
    else:
        raise ExpenseError("You are not an authorised approver for this expense.", 403)
    if c.execute("SELECT 1 FROM decisions WHERE expense_id=? AND role=?", (row["id"], role)).fetchone():
        raise ExpenseError(f"The {role} decision has already been recorded.", 409)
    return role


# ------------------------------------------------------------------ submit
def submit_expense(path, user, data, today=None):
    today = today or today_jst()
    exp_date = _date(data.get("expense_date"), "Date")
    amount = _int(data.get("amount_jpy"), "Amount", 1)
    category = data.get("category")
    if category not in P.CATEGORIES:
        raise ExpenseError("Unknown category. Choose one of: " + ", ".join(P.CATEGORIES))
    description = _text(data.get("description"), "Description", 500)
    receipt = _text(data.get("receipt_ref"), "Receipt reference", 200, required=False)

    if exp_date > today:                                                     # S1
        raise ExpenseError("Expense date cannot be in the future.")
    age = (today - exp_date).days
    if age > P.SUBMISSION_WINDOW_DAYS:                                       # R1
        raise ExpenseError(f"Rejected per {P.CITE}: claims must be submitted within "
                           f"{P.SUBMISSION_WINDOW_DAYS} calendar days after the expense occurs "
                           f"(this one is {age} days old).", 422)
    if amount >= P.RECEIPT_THRESHOLD_JPY and not receipt:                    # R2
        raise ExpenseError(f"Rejected per {P.CITE}: a receipt is required for any expense of "
                           f"JPY {P.RECEIPT_THRESHOLD_JPY:,} or more. Add a receipt reference.", 422)

    trip_start = pre_approval = tax = nights = None
    if category == P.DOMESTIC_TRAVEL:                                        # R3
        trip_start = _date(data.get("trip_start"), "Trip start date")
        pre_approval = _date(data.get("pre_approval_date"), "Manager pre-approval date")
        if trip_start > exp_date:
            raise ExpenseError("Trip start date cannot be after the expense date.")
        if pre_approval >= trip_start:
            raise ExpenseError(f"Rejected per {P.CITE}: domestic travel requires manager approval "
                               "before the trip; the pre-approval date must be earlier than the trip start.", 422)
        trip_start, pre_approval = trip_start.isoformat(), pre_approval.isoformat()
    if category == P.DOMESTIC_HOTEL:                                         # R5 inputs
        nights = _int(data.get("nights"), "Nights", 1)
        tax = _int(data.get("tax_jpy", 0) if data.get("tax_jpy") not in (None, "") else 0, "Tax", 0)
        if tax > amount:
            raise ExpenseError("Tax portion cannot exceed the total amount.")
    required = "manager,finance" if category == P.INTERNATIONAL_TRAVEL else "manager"   # R4

    with db(path, write=True) as c:
        emp = c.execute("SELECT * FROM employees WHERE id=?", (user["id"],)).fetchone()
        if emp["manager_id"] is None:
            raise ExpenseError("No approving manager is configured for you, so a claim cannot be routed.", 422)
        cur = c.execute(
            "INSERT INTO expenses(employee_id,expense_date,amount_jpy,category,description,receipt_ref,tax_jpy,"
            "nights,trip_start,pre_approval_date,required_approvals,submitted_on,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["id"], exp_date.isoformat(), amount, category, description, receipt or None, tax, nights,
             trip_start, pre_approval, required, today.isoformat(), now_jst()))
        row = c.execute("SELECT * FROM expenses WHERE id=?", (cur.lastrowid,)).fetchone()
        return _detail(c, row)


# ------------------------------------------------------------------ read
def get_expense(path, user, expense_id):
    with db(path) as c:
        row = c.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not row or not can_view(c, user, row):
            raise ExpenseError("Expense not found.", 404)
        d = _detail(c, row)
        try:
            _check_can_decide(c, user, row)
            d["can_decide"] = True
        except ExpenseError:
            d["can_decide"] = False
        return d


def _visible_where(user):
    if user["role"] == "finance":
        return "1=1", []
    if user["role"] == "manager":
        return "(e.employee_id=? OR m.manager_id=?)", [user["id"], user["id"]]
    return "e.employee_id=?", [user["id"]]


def list_expenses(path, user, scope="visible", status=None, month=None):
    where, args = _visible_where(user)
    sql = "SELECT e.* FROM expenses e JOIN employees m ON m.id=e.employee_id WHERE " + where
    if scope == "mine":
        sql += " AND e.employee_id=?"; args.append(user["id"])
    if status in ("pending", "approved", "rejected"):
        sql += " AND e.status=?"; args.append(status)
    if month:
        _month(month)
        sql += " AND substr(e.expense_date,1,7)=?"; args.append(month)
    sql += " ORDER BY e.expense_date DESC, e.id DESC"
    out = []
    with db(path) as c:
        for row in c.execute(sql, args).fetchall():
            if scope == "approvals":
                try:
                    _check_can_decide(c, user, row)
                except ExpenseError:
                    continue
            out.append(_detail(c, row))
    return out


# ------------------------------------------------------------------ decide
def decide(path, user, expense_id, decision, comment=None, now=None):
    if decision not in ("approved", "rejected"):
        raise ExpenseError("Decision must be 'approved' or 'rejected'.")
    comment = _text(comment, "Comment", 500, required=False)
    with db(path, write=True) as c:
        row = c.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not row or not can_view(c, user, row):
            raise ExpenseError("Expense not found.", 404)
        role = _check_can_decide(c, user, row)
        c.execute("INSERT INTO decisions(expense_id,approver_id,role,decision,comment,decided_at) VALUES(?,?,?,?,?,?)",
                  (expense_id, user["id"], role, decision, comment or None, now or now_jst()))
        decs = c.execute("SELECT role, decision FROM decisions WHERE expense_id=?", (expense_id,)).fetchall()
        required = set(row["required_approvals"].split(","))
        if any(d["decision"] == "rejected" for d in decs):
            status = "rejected"
        elif required <= {d["role"] for d in decs if d["decision"] == "approved"}:
            status = "approved"
        else:
            status = "pending"
        c.execute("UPDATE expenses SET status=? WHERE id=?", (status, expense_id))
        return _detail(c, c.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone())


def decision_history(path, user, expense_id=None):
    where, args = _visible_where(user)
    sql = ("SELECT d.id, d.expense_id, d.role, d.decision, d.comment, d.decided_at, a.name AS approver_name, "
           "e.employee_id, m.name AS employee_name, e.category, e.amount_jpy, e.expense_date "
           "FROM decisions d JOIN expenses e ON e.id=d.expense_id JOIN employees m ON m.id=e.employee_id "
           "JOIN employees a ON a.id=d.approver_id WHERE " + where.replace("m.manager_id", "m.manager_id"))
    if expense_id is not None:
        sql += " AND d.expense_id=?"; args.append(expense_id)
    sql += " ORDER BY d.decided_at DESC, d.id DESC"
    with db(path) as c:
        return [dict(r) for r in c.execute(sql, args)]


# ------------------------------------------------------------------ reports
def _month(m):
    if not isinstance(m, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m):
        raise ExpenseError("Month must be in YYYY-MM format.")
    return m


def monthly_report(path, user, month):
    if user["role"] == "employee":
        raise ExpenseError("Reports are available to managers and finance only.", 403)
    _month(month)
    if user["role"] == "finance":
        where, args = "1=1", []
    else:
        where, args = "m.manager_id=?", [user["id"]]          # manager: direct reports
    with db(path) as c:
        rows = c.execute(
            "SELECT e.*, m.name AS employee_name FROM expenses e JOIN employees m ON m.id=e.employee_id "
            f"WHERE {where} AND substr(e.expense_date,1,7)=? ORDER BY m.name, e.category, e.expense_date, e.id",
            args + [month]).fetchall()
    detail, groups = [], {}
    for r in rows:
        excess, reimb = hotel_figures(r)
        detail.append({"id": r["id"], "employee": r["employee_name"], "expense_date": r["expense_date"],
                       "category": r["category"], "description": r["description"], "amount_jpy": r["amount_jpy"],
                       "status": r["status"], "receipt_ref": r["receipt_ref"] or "",
                       "cap_excess_jpy": excess, "reimbursable_jpy": reimb, "submitted_on": r["submitted_on"]})

    def acc(key):
        g = groups.setdefault(key, {"expenses": 0, "claimed_jpy": 0, "approved_jpy": 0, "pending_jpy": 0,
                                    "rejected_jpy": 0, "approved_reimbursable_jpy": 0})
        return g

    keyed = {"emp_cat": {}, "emp": {}, "cat": {}}
    for d in detail:
        for name, key in (("emp_cat", (d["employee"], d["category"])), ("emp", d["employee"]), ("cat", d["category"])):
            g = keyed[name].setdefault(key, {"expenses": 0, "claimed_jpy": 0, "approved_jpy": 0, "pending_jpy": 0,
                                             "rejected_jpy": 0, "approved_reimbursable_jpy": 0})
            g["expenses"] += 1
            g["claimed_jpy"] += d["amount_jpy"]
            g[d["status"] + "_jpy"] += d["amount_jpy"]
            if d["status"] == "approved":
                g["approved_reimbursable_jpy"] += d["reimbursable_jpy"]
    grand = {"expenses": len(detail), "claimed_jpy": 0, "approved_jpy": 0, "pending_jpy": 0, "rejected_jpy": 0,
             "approved_reimbursable_jpy": 0}
    for g in keyed["emp"].values():
        for k in grand:
            if k != "expenses":
                grand[k] += g[k]
    return {"month": month,
            "by_employee_category": [{"employee": k[0], "category": k[1], **v} for k, v in sorted(keyed["emp_cat"].items())],
            "by_employee": [{"employee": k, **v} for k, v in sorted(keyed["emp"].items())],
            "by_category": [{"category": k, **v} for k, v in sorted(keyed["cat"].items())],
            "grand_total": grand, "detail": detail}


def _safe(v):
    """Neutralise spreadsheet formula injection in user-entered text."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def report_csv(path, user, month, view="summary"):
    import csv, io
    rep = monthly_report(path, user, month)
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    money = ["expenses", "claimed_jpy", "approved_jpy", "pending_jpy", "rejected_jpy", "approved_reimbursable_jpy"]
    if view == "summary":
        w.writerow(["month", "employee", "category"] + money)
        for r in rep["by_employee_category"]:
            w.writerow([month, _safe(r["employee"]), _safe(r["category"])] + [r[k] for k in money])
    elif view == "by_employee":
        w.writerow(["month", "employee"] + money)
        for r in rep["by_employee"]:
            w.writerow([month, _safe(r["employee"])] + [r[k] for k in money])
    elif view == "by_category":
        w.writerow(["month", "category"] + money)
        for r in rep["by_category"]:
            w.writerow([month, _safe(r["category"])] + [r[k] for k in money])
    elif view == "detail":
        cols = ["id", "employee", "expense_date", "category", "description", "amount_jpy", "status",
                "receipt_ref", "cap_excess_jpy", "reimbursable_jpy", "submitted_on"]
        w.writerow(cols)
        for d in rep["detail"]:
            w.writerow([_safe(d[k]) if isinstance(d[k], str) else d[k] for k in cols])
    else:
        raise ExpenseError("view must be summary, by_employee, by_category or detail.")
    return "\ufeff" + out.getvalue()
