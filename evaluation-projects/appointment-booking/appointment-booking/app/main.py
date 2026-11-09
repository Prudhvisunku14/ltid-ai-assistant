"""Flask HTTP layer. Thin: parses requests, calls booking.py, returns JSON."""
import os
from flask import Flask, jsonify, request, send_from_directory
from . import booking

STATIC = os.path.join(os.path.dirname(__file__), "static")


def create_app(db_path=None, admin_token=None):
    app = Flask(__name__, static_folder=STATIC, static_url_path="/static")
    app.config["DB"] = db_path or os.environ.get("BOOKING_DB", "appointments.db")
    app.config["ADMIN_TOKEN"] = admin_token or os.environ.get("ADMIN_TOKEN", "admin123")
    booking.init_db(app.config["DB"])
    db = lambda: app.config["DB"]

    @app.errorhandler(booking.BookingError)
    def on_error(e):
        return jsonify(error=e.message), e.status

    def body():
        return request.get_json(silent=True) or {}

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/admin")
    def admin_page():
        return send_from_directory(STATIC, "admin.html")

    @app.get("/api/slots")
    def slots():
        return jsonify(date=request.args.get("date"),
                       slots=booking.slots_for_day(db(), request.args.get("date")))

    @app.post("/api/appointments")
    def create():
        b = body()
        return jsonify(booking.create(db(), b.get("name"), b.get("date"),
                                      b.get("time"), b.get("purpose"))), 201

    @app.get("/api/appointments/<code>")
    def view(code):
        return jsonify(booking.row_to_dict(booking.get(db(), code)))

    @app.put("/api/appointments/<code>")
    def modify(code):
        return jsonify(booking.modify(db(), code, body()))

    @app.delete("/api/appointments/<code>")
    def cancel(code):
        return jsonify(booking.cancel(db(), code))

    @app.get("/api/admin/appointments")
    def admin_list():
        if request.headers.get("X-Admin-Token") != app.config["ADMIN_TOKEN"]:
            return jsonify(error="Admin token required."), 401
        return jsonify(appointments=booking.list_range(
            db(), request.args.get("start"), request.args.get("end")))

    return app
