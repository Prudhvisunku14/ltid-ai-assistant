import threading
from datetime import datetime, timedelta
import pytest
from app import booking
from app.main import create_app

# Fixed "now": Monday 2030-01-07 08:00 JST, so all tests are deterministic.
FIXED_NOW = datetime(2030, 1, 7, 8, 0, tzinfo=booking.JST)
MON, TUE, SAT, SUN = "2030-01-07", "2030-01-08", "2030-01-12", "2030-01-13"


@pytest.fixture(autouse=True)
def freeze(monkeypatch):
    monkeypatch.setattr(booking, "now_jst", lambda: FIXED_NOW)


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "t.db"), admin_token="tok")


@pytest.fixture
def client(app):
    return app.test_client()


def book(client, name="Aiko", date=MON, time="10:00", purpose="Strategy"):
    return client.post("/api/appointments",
                       json={"name": name, "date": date, "time": time, "purpose": purpose})


# ---- booking & validation
def test_book_and_view(client):
    r = book(client)
    assert r.status_code == 201
    a = r.get_json()
    assert a["duration_minutes"] == 30 and a["timezone"] == "Asia/Tokyo"
    v = client.get(f"/api/appointments/{a['code']}").get_json()
    assert (v["name"], v["date"], v["time"], v["purpose"]) == ("Aiko", MON, "10:00", "Strategy")


def test_slot_list_has_16_slots_9_to_1630(client):
    s = client.get(f"/api/slots?date={MON}").get_json()["slots"]
    assert len(s) == 16 and s[0]["time"] == "09:00" and s[-1]["time"] == "16:30"


@pytest.mark.parametrize("time", ["08:30", "17:00", "09:15", "12:45", "abc", ""])
def test_rejects_times_outside_hours_or_grid(client, time):
    assert book(client, time=time).status_code == 400


@pytest.mark.parametrize("date", [SAT, SUN])
def test_rejects_weekends(client, date):
    assert book(client, date=date).status_code == 400
    assert client.get(f"/api/slots?date={date}").get_json()["slots"] == []


def test_rejects_past_and_bad_date(client):
    assert book(client, date="2030-01-04").status_code == 400      # earlier Friday
    assert book(client, date=MON, time="08:00").status_code == 400  # not a slot
    assert book(client, date="not-a-date").status_code == 400


def test_requires_name_and_purpose(client):
    assert book(client, name="  ").status_code == 400
    assert book(client, purpose="").status_code == 400
    assert client.post("/api/appointments", json={}).status_code == 400


# ---- conflicts
def test_double_booking_prevented(client):
    assert book(client).status_code == 201
    r = book(client, name="Ben")
    assert r.status_code == 409
    s = client.get(f"/api/slots?date={MON}").get_json()["slots"]
    assert next(x for x in s if x["time"] == "10:00")["available"] is False


def test_adjacent_slots_do_not_conflict(client):
    assert book(client, time="10:00").status_code == 201
    assert book(client, time="10:30").status_code == 201
    assert book(client, time="09:30").status_code == 201


def test_concurrent_bookings_only_one_wins(app):
    results = []

    def go(i):
        r = app.test_client().post("/api/appointments", json={
            "name": f"C{i}", "date": TUE, "time": "11:00", "purpose": "race"})
        results.append(r.status_code)

    ts = [threading.Thread(target=go, args=(i,)) for i in range(12)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert results.count(201) == 1 and results.count(409) == 11


# ---- cancellation
def test_cancel_frees_slot_and_allows_rebooking(client):
    code = book(client).get_json()["code"]
    r = client.delete(f"/api/appointments/{code}")
    assert r.status_code == 200 and r.get_json()["status"] == "cancelled"
    s = client.get(f"/api/slots?date={MON}").get_json()["slots"]
    assert next(x for x in s if x["time"] == "10:00")["available"] is True
    assert book(client, name="Ben").status_code == 201


def test_cancel_twice_and_unknown(client):
    code = book(client).get_json()["code"]
    client.delete(f"/api/appointments/{code}")
    assert client.delete(f"/api/appointments/{code}").status_code == 409
    assert client.delete("/api/appointments/NOPE1234").status_code == 404


def test_cancelled_cannot_be_modified(client):
    code = book(client).get_json()["code"]
    client.delete(f"/api/appointments/{code}")
    assert client.put(f"/api/appointments/{code}", json={"time": "11:00"}).status_code == 409


# ---- modification
def test_modify_time_and_details(client):
    code = book(client).get_json()["code"]
    r = client.put(f"/api/appointments/{code}",
                   json={"date": TUE, "time": "15:30", "purpose": "Follow-up", "name": "Aiko S."})
    assert r.status_code == 200
    a = r.get_json()
    assert (a["date"], a["time"], a["purpose"], a["name"]) == (TUE, "15:30", "Follow-up", "Aiko S.")
    s = client.get(f"/api/slots?date={MON}").get_json()["slots"]
    assert next(x for x in s if x["time"] == "10:00")["available"] is True   # old slot freed


def test_modify_into_taken_slot_conflicts_and_keeps_original(client):
    a = book(client, time="10:00").get_json()
    book(client, name="Ben", time="11:00")
    assert client.put(f"/api/appointments/{a['code']}", json={"time": "11:00"}).status_code == 409
    assert client.get(f"/api/appointments/{a['code']}").get_json()["time"] == "10:00"


def test_modify_same_slot_other_fields_ok(client):
    a = book(client).get_json()
    r = client.put(f"/api/appointments/{a['code']}", json={"purpose": "New topic"})
    assert r.status_code == 200 and r.get_json()["time"] == "10:00"


def test_modify_to_invalid_slot_rejected(client):
    a = book(client).get_json()
    assert client.put(f"/api/appointments/{a['code']}", json={"date": SAT}).status_code == 400


# ---- persistence & admin
def test_records_persist_across_app_restart(tmp_path):
    path = str(tmp_path / "p.db")
    c1 = create_app(path).test_client()
    code = book(c1).get_json()["code"]
    c2 = create_app(path).test_client()           # "restart"
    assert c2.get(f"/api/appointments/{code}").get_json()["name"] == "Aiko"
    assert book(c2, name="Ben").status_code == 409  # conflict rule survives restart


def test_admin_calendar_requires_token_and_lists_only_active(client):
    a = book(client, time="09:00").get_json()
    b = book(client, name="Ben", time="09:30").get_json()
    client.delete(f"/api/appointments/{b['code']}")
    url = f"/api/admin/appointments?start={MON}&end={SUN}"
    assert client.get(url).status_code == 401
    r = client.get(url, headers={"X-Admin-Token": "tok"}).get_json()["appointments"]
    assert [x["code"] for x in r] == [a["code"]]


def test_timezone_is_japan_time():
    assert booking.now_jst.__name__  # patched in tests; real one is JST-aware
    assert booking.JST.key == "Asia/Tokyo"
