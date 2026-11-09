"""Business logic: validation, availability, and persistence (SQLite)."""
import secrets
import sqlite3
from datetime import datetime, date as date_cls, time as time_cls, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
OPEN_HOUR, CLOSE_HOUR, SLOT_MINUTES = 9, 17, 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT NOT NULL UNIQUE,
    name      TEXT NOT NULL,
    date      TEXT NOT NULL,            -- YYYY-MM-DD (JST)
    time      TEXT NOT NULL,            -- HH:MM (JST), slot start
    purpose   TEXT NOT NULL,
    status    TEXT NOT NULL DEFAULT 'booked',   -- booked | cancelled
    created_at TEXT NOT NULL
);
-- The database itself enforces "no double booking": only one ACTIVE
-- appointment may exist per slot. Cancelled rows do not block the slot.
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_slot
    ON appointments(date, time) WHERE status = 'booked';
"""


class BookingError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def now_jst():
    return datetime.now(JST)


def all_slot_times():
    out, t = [], datetime(2000, 1, 1, OPEN_HOUR)
    end = datetime(2000, 1, 1, CLOSE_HOUR)
    while t < end:
        out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=SLOT_MINUTES)
    return out


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path):
    c = connect(path)
    try:
        c.executescript(SCHEMA)
        c.commit()
    finally:
        c.close()


def parse_date(s):
    try:
        return date_cls.fromisoformat(s)
    except (TypeError, ValueError):
        raise BookingError("Date must be in YYYY-MM-DD format.")


def validate_slot(date_str, time_str):
    d = parse_date(date_str)
    if time_str not in all_slot_times():
        raise BookingError(
            "Time must be a 30-minute slot between 09:00 and 16:30 (JST), e.g. 09:00 or 09:30.")
    if d.weekday() >= 5:
        raise BookingError("Appointments are available Monday to Friday only.")
    start = datetime.combine(d, time_cls.fromisoformat(time_str), tzinfo=JST)
    if start <= now_jst():
        raise BookingError("That time has already passed (Japan time).")


def clean_text(value, field, max_len):
    value = (value or "").strip() if isinstance(value, (str, type(None))) else ""
    if not value:
        raise BookingError(f"{field} is required.")
    if len(value) > max_len:
        raise BookingError(f"{field} must be at most {max_len} characters.")
    return value


def row_to_dict(r):
    d = {k: r[k] for k in ("id", "code", "name", "date", "time", "purpose", "status")}
    d["duration_minutes"] = SLOT_MINUTES
    d["timezone"] = "Asia/Tokyo"
    return d


def _one(c, sql, args):
    return c.execute(sql, args).fetchone()


def slots_for_day(path, date_str):
    d = parse_date(date_str)
    if d.weekday() >= 5:
        return []
    c = connect(path)
    try:
        taken = {r["time"] for r in c.execute(
            "SELECT time FROM appointments WHERE date=? AND status='booked'", (date_str,))}
    finally:
        c.close()
    now = now_jst()
    res = []
    for t in all_slot_times():
        start = datetime.combine(d, time_cls.fromisoformat(t), tzinfo=JST)
        res.append({"time": t, "available": t not in taken and start > now})
    return res


def create(path, name, date_str, time_str, purpose):
    name = clean_text(name, "Name", 100)
    purpose = clean_text(purpose, "Purpose", 500)
    validate_slot(date_str, time_str)
    code = secrets.token_hex(4).upper()
    c = connect(path)
    try:
        cur = c.execute(
            "INSERT INTO appointments(code,name,date,time,purpose,created_at) VALUES(?,?,?,?,?,?)",
            (code, name, date_str, time_str, purpose, now_jst().isoformat()))
        c.commit()
        return row_to_dict(_one(c, "SELECT * FROM appointments WHERE id=?", (cur.lastrowid,)))
    except sqlite3.IntegrityError:
        raise BookingError("That slot is already booked. Please choose another time.", 409)
    finally:
        c.close()


def get(path, code):
    c = connect(path)
    try:
        row = _one(c, "SELECT * FROM appointments WHERE code=?", ((code or "").strip().upper(),))
    finally:
        c.close()
    if not row:
        raise BookingError("Appointment not found.", 404)
    return row


def modify(path, code, data):
    row = get(path, code)
    if row["status"] != "booked":
        raise BookingError("A cancelled appointment cannot be modified.", 409)
    name = clean_text(data.get("name", row["name"]), "Name", 100)
    purpose = clean_text(data.get("purpose", row["purpose"]), "Purpose", 500)
    date_str = data.get("date", row["date"])
    time_str = data.get("time", row["time"])
    if (date_str, time_str) != (row["date"], row["time"]):
        validate_slot(date_str, time_str)
    c = connect(path)
    try:
        c.execute("UPDATE appointments SET name=?,purpose=?,date=?,time=? WHERE id=?",
                  (name, purpose, date_str, time_str, row["id"]))
        c.commit()
        return row_to_dict(_one(c, "SELECT * FROM appointments WHERE id=?", (row["id"],)))
    except sqlite3.IntegrityError:
        raise BookingError("That slot is already booked. Please choose another time.", 409)
    finally:
        c.close()


def cancel(path, code):
    row = get(path, code)
    if row["status"] == "cancelled":
        raise BookingError("Appointment is already cancelled.", 409)
    c = connect(path)
    try:
        c.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (row["id"],))
        c.commit()
        return row_to_dict(_one(c, "SELECT * FROM appointments WHERE id=?", (row["id"],)))
    finally:
        c.close()


def list_range(path, start, end):
    parse_date(start), parse_date(end)
    c = connect(path)
    try:
        rows = c.execute(
            "SELECT * FROM appointments WHERE date BETWEEN ? AND ? AND status='booked' "
            "ORDER BY date,time", (start, end)).fetchall()
    finally:
        c.close()
    return [row_to_dict(r) for r in rows]
