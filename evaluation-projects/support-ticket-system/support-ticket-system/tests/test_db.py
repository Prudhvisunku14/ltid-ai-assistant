from app.db import TicketRepository


def test_empty_stats_are_zero_filled(db_path):
    s = TicketRepository(db_path).stats()
    assert s["total"] == 0
    assert s["by_status"] == {"open": 0, "in_progress": 0, "resolved": 0}


def test_update_ignores_unknown_columns_and_missing_rows(db_path):
    repo = TicketRepository(db_path)
    t = repo.create({"title": "t", "description": "d", "category": "billing", "priority": "low",
                     "category_source": "manual", "priority_source": "manual"})
    same = repo.update(t["id"], {"title": "hacked"})  # title is not updatable
    assert same["title"] == "t"
    assert repo.update(12345, {"status": "resolved"}) is None


def test_sql_injection_in_text_is_harmless(db_path):
    repo = TicketRepository(db_path)
    evil = "x'); DROP TABLE tickets;--"
    t = repo.create({"title": evil, "description": evil, "category": "billing", "priority": "low",
                     "category_source": "manual", "priority_source": "manual"})
    assert repo.get(t["id"])["title"] == evil
    assert repo.stats()["total"] == 1
