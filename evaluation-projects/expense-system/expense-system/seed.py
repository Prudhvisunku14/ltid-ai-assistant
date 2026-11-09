"""Fictional demo data (Northstar Services is a fictional company). Goes through the real
business rules, with explicit submission/decision dates so the history looks realistic."""
from datetime import date
from app import service as S

EMPLOYEES = [
    (1, "Haruka Sato", "Sales", "manager", 8), (2, "Kenji Mori", "Sales", "employee", 1),
    (3, "Yui Tanaka", "Sales", "employee", 1), (4, "Daichi Ito", "Engineering", "manager", 8),
    (5, "Mei Kobayashi", "Engineering", "employee", 4), (6, "Ren Kimura", "Engineering", "employee", 4),
    (7, "Akari Fujita", "Finance", "finance", 8), (8, "Naoki Yamada", "Executive", "manager", None)]

# (user, submitted_on, data, [(approver, decision, comment, decided_at)])
EXPENSES = [
    (2, "2026-10-06", dict(expense_date="2026-10-05", amount_jpy=1800, category="Meals", description="Client lunch, Shibuya"),
     [(1, "approved", "OK", "2026-10-07T10:00:00+09:00")]),
    (2, "2026-10-13", dict(expense_date="2026-10-12", amount_jpy=28400, category="Travel - Domestic", description="Shinkansen Tokyo-Osaka return",
                           receipt_ref="R-1012-shinkansen.pdf", trip_start="2026-10-12", pre_approval_date="2026-10-09"),
     [(1, "approved", "Pre-approved on 10/09", "2026-10-14T09:30:00+09:00")]),
    (3, "2026-10-21", dict(expense_date="2026-10-20", amount_jpy=19800, tax_jpy=1800, nights=1, category="Hotel - Domestic",
                           description="Hotel Nagoya, 1 night", receipt_ref="R-1020-hotel.pdf"),
     [(1, "approved", "Approved; amount above the cap is not reimbursable", "2026-10-22T11:00:00+09:00")]),
    (3, "2026-10-30", dict(expense_date="2026-10-28", amount_jpy=6500, category="Office Supplies", description="Printer paper and toner",
                           receipt_ref="R-1028-supplies.png"),
     [(1, "rejected", "Duplicate of an existing order", "2026-10-31T15:20:00+09:00")]),
    (5, "2026-10-16", dict(expense_date="2026-10-15", amount_jpy=12000, category="Software & Subscriptions", description="Monthly IDE licence",
                           receipt_ref="INV-4471"), [(4, "approved", None, "2026-10-17T09:00:00+09:00")]),
    (5, "2026-10-23", dict(expense_date="2026-10-22", amount_jpy=240000, category="Travel - International", description="Flight to Singapore customer workshop",
                           receipt_ref="E-TKT-88231"),
     [(4, "approved", "Manager OK", "2026-10-24T09:00:00+09:00"), (7, "approved", "Finance OK", "2026-10-25T13:00:00+09:00")]),
    (5, "2026-11-05", dict(expense_date="2026-11-03", amount_jpy=185000, category="Travel - International", description="Flight to Seoul partner meeting",
                           receipt_ref="E-TKT-90017"), [(4, "approved", "Manager OK", "2026-11-06T09:30:00+09:00")]),
    (6, "2026-11-05", dict(expense_date="2026-11-04", amount_jpy=3200, category="Meals", description="Team dinner", receipt_ref="R-1104-dinner.jpg"), []),
    (6, "2026-11-08", dict(expense_date="2026-11-07", amount_jpy=31500, tax_jpy=2500, nights=2, category="Hotel - Domestic",
                           description="Hotel Fukuoka, 2 nights", receipt_ref="R-1107-hotel.pdf"), []),
    (2, "2026-11-09", dict(expense_date="2026-11-06", amount_jpy=950, category="Other", description="Courier fee"), []),
    (1, "2026-11-04", dict(expense_date="2026-11-02", amount_jpy=2400, category="Meals", description="Partner coffee meeting", receipt_ref="R-1102-cafe.jpg"),
     [(8, "approved", None, "2026-11-05T10:00:00+09:00")]),
    (3, "2026-11-09", dict(expense_date="2026-11-08", amount_jpy=12300, category="Travel - Domestic", description="Train to Kyoto client visit",
                           receipt_ref="R-1108-train.pdf", trip_start="2026-11-08", pre_approval_date="2026-11-05"), []),
]


def seed_employees(path):
    with S.db(path, write=True) as c:
        for e in sorted(EMPLOYEES, key=lambda e: e[4] is not None):   # managers' managers first (FK)
            c.execute("INSERT OR IGNORE INTO employees(id,name,department,role,manager_id) VALUES(?,?,?,?,?)", e)


def seed_all(path):
    seed_employees(path)
    with S.db(path) as c:
        if c.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]:
            return
    for uid, submitted, data, decs in EXPENSES:
        user = S.get_employee(path, uid)
        e = S.submit_expense(path, user, data, today=date.fromisoformat(submitted))
        for aid, dec, comment, when in decs:
            S.decide(path, S.get_employee(path, aid), e["id"], dec, comment, now=when)
