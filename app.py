import os
import re
import sqlite3
from pathlib import Path
from datetime import date
from functools import wraps
from contextlib import contextmanager

from flask import Flask, jsonify, request, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "turfbook.db"

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this-secret-before-deploying"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)

ADMIN_PASSWORD = os.environ.get("TURFBOOK_ADMIN_PASSWORD", "ChangeMe123!")

TURFS = {
    1: {"name": "Green Arena Turf", "price": 800},
    2: {"name": "Champions Turf", "price": 1000},
    3: {"name": "Football Zone", "price": 700},
}
SLOTS = [
    "09:00 AM - 10:00 AM",
    "10:00 AM - 11:00 AM",
    "11:00 AM - 12:00 PM",
    "12:00 PM - 01:00 PM",
    "04:00 PM - 05:00 PM",
    "05:00 PM - 06:00 PM",
    "06:00 PM - 07:00 PM",
    "07:00 PM - 08:00 PM",
    "08:00 PM - 09:00 PM",
]


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                mobile TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                turf_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                slot TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Confirmed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS unique_confirmed_slot
            ON bookings(turf_id, date, slot)
            WHERE status = 'Confirmed'
        """)


# Initialize the SQLite schema when the application starts (local or hosted).
init_db()


def user_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Please log in to continue."), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify(error="Admin login required."), 401
        return fn(*args, **kwargs)
    return wrapper


def booking_dict(row):
    return {
        "bookingId": row["booking_id"],
        "userId": row["user_id"],
        "name": row["name"],
        "mobile": row["mobile"],
        "turfId": row["turf_id"],
        "date": row["date"],
        "slot": row["slot"],
        "amount": row["amount"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify(ok=True, service="TurfBook")


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    mobile = str(data.get("mobile", "")).strip()
    password = str(data.get("password", ""))
    if not name or len(name) > 100 or not re.fullmatch(r"\d{10}", mobile) or len(password) < 6:
        return jsonify(error="Enter a name, valid 10-digit mobile number and password of at least 6 characters."), 400
    try:
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO users(name, mobile, password_hash) VALUES (?, ?, ?)",
                (name, mobile, generate_password_hash(password)),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error="This mobile number is already registered. Please log in."), 409
    session["user_id"] = user_id
    session.permanent = True
    return jsonify(id=user_id, name=name, mobile=mobile), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    mobile = str(data.get("mobile", "")).strip()
    password = str(data.get("password", ""))
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE mobile = ?", (mobile,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Invalid mobile number or password."), 401
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify(id=user["id"], name=user["name"], mobile=user["mobile"])


@app.post("/api/logout")
def logout():
    session.pop("user_id", None)
    return jsonify(message="Logged out")


@app.get("/api/me")
@user_required
def me():
    with db() as conn:
        user = conn.execute("SELECT id, name, mobile FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not user:
        session.pop("user_id", None)
        return jsonify(error="Account not found."), 401
    return jsonify(dict(user))


@app.get("/api/availability")
def availability():
    turf_id = request.args.get("turfId", type=int)
    booking_date = request.args.get("date", "")
    if turf_id not in TURFS or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", booking_date):
        return jsonify(error="Invalid turf or date."), 400
    try:
        date.fromisoformat(booking_date)
    except ValueError:
        return jsonify(error="Invalid date."), 400
    with db() as conn:
        rows = conn.execute(
            "SELECT slot FROM bookings WHERE turf_id=? AND date=? AND status='Confirmed'",
            (turf_id, booking_date),
        ).fetchall()
    return jsonify(bookedSlots=[r["slot"] for r in rows])


@app.post("/api/bookings")
@user_required
def create_booking():
    data = request.get_json(silent=True) or {}
    try:
        turf_id = int(data.get("turfId"))
    except (TypeError, ValueError):
        return jsonify(error="Invalid turf."), 400
    booking_date = str(data.get("date", ""))
    slot = str(data.get("slot", ""))
    if turf_id not in TURFS or slot not in SLOTS:
        return jsonify(error="Invalid turf or time slot."), 400
    try:
        parsed_date = date.fromisoformat(booking_date)
        if parsed_date < date.today():
            return jsonify(error="Booking date cannot be in the past."), 400
    except ValueError:
        return jsonify(error="Invalid booking date."), 400
    with db() as conn:
        user = conn.execute("SELECT id, name, mobile FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if not user:
            return jsonify(error="Please log in again."), 401
        booking_id = str(data.get("bookingId") or "")
        if not re.fullmatch(r"TB[A-Z0-9]{4,30}", booking_id):
            return jsonify(error="Invalid booking reference. Please try again."), 400
        try:
            conn.execute("""
                INSERT INTO bookings
                (booking_id, user_id, name, mobile, turf_id, date, slot, amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed')
            """, (booking_id, user["id"], user["name"], user["mobile"], turf_id,
                  booking_date, slot, TURFS[turf_id]["price"]))
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower():
                return jsonify(error="This slot is already booked. Please choose another slot."), 409
            return jsonify(error="Could not save booking. Please try again."), 409
        row = conn.execute("SELECT * FROM bookings WHERE booking_id=?", (booking_id,)).fetchone()
    return jsonify(message="Booking confirmed", booking=booking_dict(row)), 201


@app.get("/api/my-bookings")
@user_required
def my_bookings():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE user_id=? ORDER BY created_at DESC, rowid DESC",
            (session["user_id"],),
        ).fetchall()
    return jsonify([booking_dict(row) for row in rows])


@app.patch("/api/my-bookings/<booking_id>/cancel")
@user_required
def cancel_my_booking(booking_id):
    with db() as conn:
        cur = conn.execute("""
            UPDATE bookings SET status='Cancelled'
            WHERE booking_id=? AND user_id=? AND status='Confirmed'
        """, (booking_id, session["user_id"]))
    if cur.rowcount == 0:
        return jsonify(error="Booking not found or already cancelled."), 404
    return jsonify(message="Booking cancelled")


@app.post("/api/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    if not ADMIN_PASSWORD or str(data.get("password", "")) != ADMIN_PASSWORD:
        return jsonify(error="Incorrect admin password."), 401
    session["is_admin"] = True
    session.permanent = True
    return jsonify(message="Admin login successful")


@app.get("/api/admin/session")
@admin_required
def admin_session():
    return jsonify(isAdmin=True)


@app.post("/api/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return jsonify(message="Admin logged out")


@app.get("/api/admin/bookings")
@admin_required
def admin_bookings():
    with db() as conn:
        rows = conn.execute("SELECT * FROM bookings ORDER BY created_at DESC, rowid DESC").fetchall()
    return jsonify([booking_dict(row) for row in rows])


@app.patch("/api/admin/bookings/<booking_id>/cancel")
@admin_required
def admin_cancel_booking(booking_id):
    with db() as conn:
        cur = conn.execute(
            "UPDATE bookings SET status='Cancelled' WHERE booking_id=? AND status='Confirmed'",
            (booking_id,),
        )
    if cur.rowcount == 0:
        return jsonify(error="Booking not found or already cancelled."), 404
    return jsonify(message="Booking cancelled")


@app.get("/api/admin/users")
@admin_required
def admin_users():
    with db() as conn:
        rows = conn.execute("SELECT id, name, mobile, created_at FROM users ORDER BY id DESC").fetchall()
    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    init_db()
    print("TurfBook is starting at http://127.0.0.1:5000")
    if ADMIN_PASSWORD == "ChangeMe123!":
        print("WARNING: Change the default admin password before public deployment.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
