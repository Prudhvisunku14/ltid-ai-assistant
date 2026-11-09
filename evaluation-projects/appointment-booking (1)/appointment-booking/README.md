# Kaizen Consulting — Appointment Booking System

Customers book, view, modify and cancel 30-minute appointments (Mon–Fri, 09:00–17:00 JST).
Admins get a weekly calendar. Records persist in SQLite.

## Run
    pip install -r requirements.txt
    python run.py                 # http://127.0.0.1:5000  (admin: /admin)
    python -m pytest -v           # run the test suite

Env vars: `BOOKING_DB` (db file, default appointments.db), `ADMIN_TOKEN` (default `admin123` — change it), `PORT`.

## Tool choices (all free / open source)
| Tool | Why |
|---|---|
| Python 3 + Flask (BSD) | Small, readable, no build step; ideal for a compact REST API. |
| SQLite (public domain, built into Python) | Zero-setup persistent file DB. Its partial UNIQUE index gives atomic double-booking protection. |
| Vanilla HTML/CSS/JS | No framework or bundler to install; the UI is two static pages. |
| `zoneinfo` (stdlib) | Correct Asia/Tokyo handling regardless of server timezone. |
| pytest (MIT) | Concise tests, fixtures, parametrization; clock frozen for determinism. |
| Git/GitHub (free) | Version control and hosting if you want to publish it. |

## Architecture
    Browser (index.html, admin.html)  --JSON/HTTP-->  app/main.py (Flask routes, thin)
                                                          |
                                                    app/booking.py (rules + SQL)
                                                          |
                                                   SQLite file (appointments table)

* **booking.py** holds all rules: slot grid (16 slots, 09:00–16:30 start), weekday check, no past times, input validation, create/get/modify/cancel/list.
* **Double-booking prevention** is enforced by the database: `UNIQUE(date,time) WHERE status='booked'`. Even simultaneous requests cannot both succeed (the loser gets HTTP 409). The UI also greys out taken slots as a convenience, not as the safeguard.
* **Cancellation** is a soft delete (`status='cancelled'`): history is kept and the slot is freed immediately.
* **Modify** re-validates the new slot; on conflict the original booking is left untouched.
* **Customer access**: each booking returns a random 8-character code needed to view/modify/cancel it (no accounts). **Admin** API requires the `X-Admin-Token` header.
* All times are stored and interpreted as JST.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/slots?date=YYYY-MM-DD` | Slot availability for a day |
| POST | `/api/appointments` | Book `{name,date,time,purpose}` → 201 + code |
| GET/PUT/DELETE | `/api/appointments/<code>` | View / modify / cancel |
| GET | `/api/admin/appointments?start=&end=` | Admin calendar data (token) |
