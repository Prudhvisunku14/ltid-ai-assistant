# Expense Management & Approval System (Northstar Services, fictional demo)

Employees register expenses; managers (and finance, where required) approve or reject; every decision is kept in a history;
monthly totals by employee and category can be viewed and exported to CSV. Company rules come from the Drive document
`Policy_Expense_v2_Current.txt` (see `docs/POLICY_SOURCES.md`).

## Run
    pip install -r requirements.txt
    python run.py                  # http://127.0.0.1:5000, loads fictional demo data on first start (SEED_DEMO=0 for empty)
    python -m pytest -v            # 64 tests

Env: `EXPENSE_DB` (file, default expenses.db), `PORT`, `SEED_DEMO`.
In the UI pick a user at top right: Kenji Mori / Yui Tanaka / Mei Kobayashi / Ren Kimura (employees), Haruka Sato / Daichi Ito (managers),
Akari Fujita (finance), Naoki Yamada (executive manager). Demo report months: 2026-10 and 2026-11.
**Identity is a demo picker (X-User-Id header), not real authentication. Use SSO before real use.**

## Recommended tools (all free / open source) and why
| Tool | Why |
|---|---|
| Python 3 + Flask | Small, readable REST API; no build step. |
| SQLite | Zero-setup persistent file DB with foreign keys, CHECK and UNIQUE constraints that protect integrity (e.g. one decision per approver role). For many concurrent users move to PostgreSQL; the SQL is plain. |
| Vanilla HTML/JS | One static page, nothing to compile. |
| Python `csv` | Correct quoting, plus formula-injection protection for spreadsheet users. |
| pytest | Parametrised, readable tests with a frozen clock. |
| Git/GitHub | Version control (optional). |

## Architecture
    Browser (static/index.html, role-aware tabs)
        |  JSON over HTTP (+ X-User-Id header)
    app/main.py     thin Flask routes + error mapping
        |
    app/service.py  business rules, authorisation, reports, CSV  -- uses --> app/policy.py (rules + source citations)
        |
    SQLite: employees, expenses, decisions (append-only history)

* **Status tracking:** pending -> approved | rejected; each expense lists `required_approvals` and `awaiting`.
  International travel needs manager + finance (either order); any rejection is final.
* **History:** every decision stores approver, role, decision, comment, timestamp; rows are never updated or deleted.
  UNIQUE(expense, role) plus `BEGIN IMMEDIATE` makes simultaneous decisions safe (tested).
* **Reports:** grouped by expense month; per employee x category, per employee, per category, with claimed / approved / pending / rejected
  and approved reimbursable amounts. Four CSV views (UTF-8 with BOM for Excel). Managers see direct reports; finance sees all; employees none.
* **Demo data:** `seed.py`: 8 fictional staff, 12 expenses, loaded through the same business rules.

## API
`POST /api/expenses` | `GET /api/expenses[?scope=mine|approvals&status=&month=]` | `GET /api/expenses/<id>` |
`POST /api/expenses/<id>/decision` | `GET /api/decisions[?expense_id=]` | `GET /api/reports/monthly?month=YYYY-MM` |
`GET /api/reports/monthly.csv?month=&view=summary|by_employee|by_category|detail` | `GET /api/policy`
