"""SQLite persistence layer (standard library only)."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Optional

from .models import Category, Priority, Status


def _enum_check(enum_cls) -> str:
    return ",".join(f"'{e.value}'" for e in enum_cls)


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS tickets (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    title              TEXT NOT NULL,
    description        TEXT NOT NULL,
    category           TEXT NOT NULL CHECK (category IN ({_enum_check(Category)})),
    priority           TEXT NOT NULL CHECK (priority IN ({_enum_check(Priority)})),
    priority_reasoning TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'open' CHECK (status IN ({_enum_check(Status)})),
    category_source    TEXT NOT NULL,
    priority_source    TEXT NOT NULL,
    ai_category        TEXT,
    ai_priority        TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
"""

INSERT_COLUMNS = (
    "title", "description", "category", "priority", "priority_reasoning", "status",
    "category_source", "priority_source", "ai_category", "ai_priority",
)
UPDATABLE_COLUMNS = {"category", "priority", "status", "category_source", "priority_source"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TicketRepository:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, data: dict) -> dict:
        values = {col: data.get(col) for col in INSERT_COLUMNS}
        values["status"] = values["status"] or "open"
        values["priority_reasoning"] = values["priority_reasoning"] or ""
        now = _now()
        cols = ",".join(INSERT_COLUMNS) + ",created_at,updated_at"
        marks = ",".join("?" * (len(INSERT_COLUMNS) + 2))
        params = [values[c] for c in INSERT_COLUMNS] + [now, now]
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(f"INSERT INTO tickets ({cols}) VALUES ({marks})", params)
            ticket_id = cur.lastrowid
        return self.get(ticket_id)

    def get(self, ticket_id: int) -> Optional[dict]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None

    def list(self, status=None, category=None, priority=None) -> list:
        clauses, params = [], []
        for column, value in (("status", status), ("category", category), ("priority", priority)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(getattr(value, "value", value))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM tickets {where} ORDER BY created_at DESC, id DESC", params
            ).fetchall()
        return [dict(r) for r in rows]

    def update(self, ticket_id: int, changes: dict) -> Optional[dict]:
        changes = {k: v for k, v in changes.items() if k in UPDATABLE_COLUMNS}
        if not changes:
            return self.get(ticket_id)
        sets = ", ".join(f"{k} = ?" for k in changes) + ", updated_at = ?"
        params = list(changes.values()) + [_now(), ticket_id]
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(f"UPDATE tickets SET {sets} WHERE id = ?", params)
            if cur.rowcount == 0:
                return None
        return self.get(ticket_id)

    def stats(self) -> dict:
        def counts(column: str, enum_cls) -> dict:
            assert column in {"status", "category", "priority"}
            result = {e.value: 0 for e in enum_cls}
            with closing(self._connect()) as conn:
                for row in conn.execute(f"SELECT {column} AS k, COUNT(*) AS n FROM tickets GROUP BY {column}"):
                    result[row["k"]] = row["n"]
            return result

        with closing(self._connect()) as conn:
            total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            corrected = conn.execute(
                "SELECT COUNT(*) FROM tickets WHERE "
                "(ai_category IS NOT NULL AND ai_category != category) OR "
                "(ai_priority IS NOT NULL AND ai_priority != priority)"
            ).fetchone()[0]
        return {
            "total": total,
            "by_status": counts("status", Status),
            "by_category": counts("category", Category),
            "by_priority": counts("priority", Priority),
            "manually_corrected": corrected,
        }
