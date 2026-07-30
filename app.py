from datetime import date
import os
import sqlite3
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "trekking.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-before-submission"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def execute(sql, params=()):
    db = get_db()
    db.execute(sql, params)
    db.commit()


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


# Creates all required tables and seeds the default admin account.
def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'staff', 'user')),
            phone TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'pending', 'blacklisted')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS treks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            difficulty TEXT NOT NULL CHECK(difficulty IN ('Easy', 'Moderate', 'Hard')),
            duration_days INTEGER NOT NULL,
            available_slots INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open'
                CHECK(status IN ('Pending', 'Approved', 'Open', 'Closed', 'Completed')),
            assigned_staff_id INTEGER,
            description TEXT,
            FOREIGN KEY (assigned_staff_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trek_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            status TEXT NOT NULL DEFAULT 'Booked'
                CHECK(status IN ('Booked', 'Cancelled', 'Completed')),
            UNIQUE(user_id, trek_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (trek_id) REFERENCES treks(id)
        );
        """
    )
    admin = db.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()
    if admin is None:
        db.execute(
            """
            INSERT INTO users (name, email, password_hash, role, phone, status)
            VALUES (?, ?, ?, 'admin', ?, 'active')
            """,
            (
                "Admin",
                "admin@trek.com",
                hash_password("admin123"),
                "9999999999",
            ),
        )
    db.commit()


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database initialized. Admin login: admin@trek.com / admin123")


@app.before_request
def prepare_database():
    init_db()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_one("SELECT * FROM users WHERE id = ?", (user_id,))


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = current_user()
            if user is None:
                flash("Please login first.", "warning")
                return redirect(url_for("login"))
            if user["status"] == "blacklisted":
                session.clear()
                flash("Your account has been blacklisted.", "danger")
                return redirect(url_for("login"))
            if role and user["role"] != role:
                flash("You are not allowed to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    treks = query_all(
        "SELECT * FROM treks WHERE status = 'Open' ORDER BY start_date LIMIT 6"
    )
    return render_template("index.html", treks=treks)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        password = request.form["password"]
        role = request.form["role"]

        if role not in ("staff", "user"):
            flash("Only staff and trekkers can register.", "danger")
            return redirect(url_for("register"))

        status = "pending" if role == "staff" else "active"
        try:
            execute(
                """
                INSERT INTO users (name, email, password_hash, role, phone, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, email, hash_password(password), role, phone, status),
            )
            if role == "staff":
                flash("Registered successfully. Admin approval is required.", "info")
            else:
                flash("Registered successfully. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists.", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        if user and check_password_hash(user["password_hash"], password):
            if user["status"] == "blacklisted":
                flash("This account is blacklisted.", "danger")
                return redirect(url_for("login"))
            if user["role"] == "staff" and user["status"] == "pending":
                flash("Your staff account is waiting for admin approval.", "warning")
                return redirect(url_for("login"))
            session.clear()
            session["user_id"] = user["id"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required()
def dashboard():
    user = current_user()
    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    if user["role"] == "staff":
        return redirect(url_for("staff_dashboard"))
    return redirect(url_for("user_dashboard"))


@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    stats = {
        "treks": query_one("SELECT COUNT(*) AS count FROM treks")["count"],
        "users": query_one("SELECT COUNT(*) AS count FROM users WHERE role = 'user'")[
            "count"
        ],
        "staff": query_one("SELECT COUNT(*) AS count FROM users WHERE role = 'staff'")[
            "count"
        ],
        "bookings": query_one("SELECT COUNT(*) AS count FROM bookings")["count"],
    }
    recent_bookings = query_all(
        """
        SELECT b.*, u.name AS user_name, t.name AS trek_name
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN treks t ON b.trek_id = t.id
        ORDER BY b.id DESC LIMIT 5
        """
    )
    return render_template(
        "admin/dashboard.html", stats=stats, recent_bookings=recent_bookings
    )


@app.route("/admin/treks")
@login_required("admin")
def admin_treks():
    search = request.args.get("q", "").strip()
    if search:
        treks = query_all(
            """
            SELECT t.*, u.name AS staff_name
            FROM treks t LEFT JOIN users u ON t.assigned_staff_id = u.id
            WHERE t.name LIKE ? OR t.location LIKE ? OR CAST(t.id AS TEXT) = ?
            ORDER BY t.start_date
            """,
            (f"%{search}%", f"%{search}%", search),
        )
    else:
        treks = query_all(
            """
            SELECT t.*, u.name AS staff_name
            FROM treks t LEFT JOIN users u ON t.assigned_staff_id = u.id
            ORDER BY t.start_date
            """
        )
    return render_template("admin/treks.html", treks=treks, search=search)


@app.route("/admin/treks/new", methods=["GET", "POST"])
@login_required("admin")
def create_trek():
    if request.method == "POST":
        execute(
            """
            INSERT INTO treks
            (name, location, difficulty, duration_days, available_slots,
             start_date, end_date, status, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["name"].strip(),
                request.form["location"].strip(),
                request.form["difficulty"],
                int(request.form["duration_days"]),
                int(request.form["available_slots"]),
                request.form["start_date"],
                request.form["end_date"],
                request.form["status"],
                request.form["description"].strip(),
            ),
        )
        flash("Trek created.", "success")
        return redirect(url_for("admin_treks"))
    return render_template("admin/trek_form.html", trek=None)


@app.route("/admin/treks/<int:trek_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def edit_trek(trek_id):
    trek = query_one("SELECT * FROM treks WHERE id = ?", (trek_id,))
    if trek is None:
        flash("Trek not found.", "danger")
        return redirect(url_for("admin_treks"))
    if request.method == "POST":
        execute(
            """
            UPDATE treks
            SET name = ?, location = ?, difficulty = ?, duration_days = ?,
                available_slots = ?, start_date = ?, end_date = ?,
                status = ?, description = ?
            WHERE id = ?
            """,
            (
                request.form["name"].strip(),
                request.form["location"].strip(),
                request.form["difficulty"],
                int(request.form["duration_days"]),
                int(request.form["available_slots"]),
                request.form["start_date"],
                request.form["end_date"],
                request.form["status"],
                request.form["description"].strip(),
                trek_id,
            ),
        )
        flash("Trek updated.", "success")
        return redirect(url_for("admin_treks"))
    return render_template("admin/trek_form.html", trek=trek)


@app.post("/admin/treks/<int:trek_id>/delete")
@login_required("admin")
def delete_trek(trek_id):
    execute("DELETE FROM bookings WHERE trek_id = ?", (trek_id,))
    execute("DELETE FROM treks WHERE id = ?", (trek_id,))
    flash("Trek removed.", "info")
    return redirect(url_for("admin_treks"))


@app.route("/admin/staff")
@login_required("admin")
def admin_staff():
    search = request.args.get("q", "").strip()
    params = []
    where = "WHERE role = 'staff'"
    if search:
        where += " AND (name LIKE ? OR email LIKE ? OR CAST(id AS TEXT) = ?)"
        params = [f"%{search}%", f"%{search}%", search]
    staff = query_all(f"SELECT * FROM users {where} ORDER BY status, name", params)
    return render_template("admin/staff.html", staff=staff, search=search)


@app.post("/admin/users/<int:user_id>/status")
@login_required("admin")
def update_user_status(user_id):
    status = request.form["status"]
    if status not in ("active", "pending", "blacklisted"):
        flash("Invalid status.", "danger")
        return redirect(request.referrer or url_for("admin_dashboard"))
    execute("UPDATE users SET status = ? WHERE id = ? AND role != 'admin'", (status, user_id))
    flash("Account status updated.", "success")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/admin/users")
@login_required("admin")
def admin_users():
    search = request.args.get("q", "").strip()
    params = []
    where = "WHERE role = 'user'"
    if search:
        where += " AND (name LIKE ? OR email LIKE ? OR CAST(id AS TEXT) = ?)"
        params = [f"%{search}%", f"%{search}%", search]
    users = query_all(f"SELECT * FROM users {where} ORDER BY name", params)
    return render_template("admin/users.html", users=users, search=search)


@app.route("/admin/assign", methods=["GET", "POST"])
@login_required("admin")
def assign_staff():
    if request.method == "POST":
        execute(
            "UPDATE treks SET assigned_staff_id = ? WHERE id = ?",
            (request.form["staff_id"], request.form["trek_id"]),
        )
        flash("Staff assigned to trek.", "success")
        return redirect(url_for("assign_staff"))
    treks = query_all(
        """
        SELECT t.*, u.name AS staff_name
        FROM treks t LEFT JOIN users u ON t.assigned_staff_id = u.id
        ORDER BY t.start_date
        """
    )
    staff = query_all(
        "SELECT * FROM users WHERE role = 'staff' AND status = 'active' ORDER BY name"
    )
    return render_template("admin/assign.html", treks=treks, staff=staff)


@app.route("/admin/bookings")
@login_required("admin")
def admin_bookings():
    bookings = query_all(
        """
        SELECT b.*, u.name AS user_name, t.name AS trek_name
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN treks t ON b.trek_id = t.id
        ORDER BY b.booking_date DESC, b.id DESC
        """
    )
    return render_template("admin/bookings.html", bookings=bookings)


@app.route("/staff")
@login_required("staff")
def staff_dashboard():
    staff = current_user()
    treks = query_all(
        """
        SELECT t.*, COUNT(b.id) AS booked_count
        FROM treks t
        LEFT JOIN bookings b ON t.id = b.trek_id AND b.status = 'Booked'
        WHERE t.assigned_staff_id = ?
        GROUP BY t.id
        ORDER BY t.start_date
        """,
        (staff["id"],),
    )
    return render_template("staff/dashboard.html", treks=treks)


@app.route("/staff/treks/<int:trek_id>", methods=["GET", "POST"])
@login_required("staff")
def manage_assigned_trek(trek_id):
    staff = current_user()
    trek = query_one(
        "SELECT * FROM treks WHERE id = ? AND assigned_staff_id = ?",
        (trek_id, staff["id"]),
    )
    if trek is None:
        flash("You can manage only assigned treks.", "danger")
        return redirect(url_for("staff_dashboard"))
    if request.method == "POST":
        execute(
            "UPDATE treks SET available_slots = ?, status = ? WHERE id = ?",
            (int(request.form["available_slots"]), request.form["status"], trek_id),
        )
        flash("Trek details updated.", "success")
        return redirect(url_for("manage_assigned_trek", trek_id=trek_id))
    participants = query_all(
        """
        SELECT b.*, u.name, u.email, u.phone
        FROM bookings b JOIN users u ON b.user_id = u.id
        WHERE b.trek_id = ?
        ORDER BY b.booking_date
        """,
        (trek_id,),
    )
    return render_template(
        "staff/manage_trek.html", trek=trek, participants=participants
    )


@app.route("/user")
@login_required("user")
def user_dashboard():
    difficulty = request.args.get("difficulty", "")
    location = request.args.get("location", "").strip()
    sql = "SELECT * FROM treks WHERE status = 'Open'"
    params = []
    if difficulty:
        sql += " AND difficulty = ?"
        params.append(difficulty)
    if location:
        sql += " AND location LIKE ?"
        params.append(f"%{location}%")
    sql += " ORDER BY start_date"
    treks = query_all(sql, params)
    return render_template(
        "user/dashboard.html",
        treks=treks,
        difficulty=difficulty,
        location=location,
    )


@app.route("/user/bookings")
@login_required("user")
def user_bookings():
    bookings = query_all(
        """
        SELECT b.*, t.name AS trek_name, t.location, t.difficulty, t.duration_days,
               t.start_date, t.end_date, t.status AS trek_status
        FROM bookings b JOIN treks t ON b.trek_id = t.id
        WHERE b.user_id = ?
        ORDER BY b.booking_date DESC
        """,
        (current_user()["id"],),
    )
    return render_template("user/bookings.html", bookings=bookings)


@app.post("/user/book/<int:trek_id>")
@login_required("user")
def book_trek(trek_id):
    user = current_user()
    trek = query_one("SELECT * FROM treks WHERE id = ?", (trek_id,))
    if trek is None or trek["status"] != "Open":
        flash("This trek is not available for booking.", "danger")
        return redirect(url_for("user_dashboard"))
    if trek["available_slots"] <= 0:
        flash("No slots are available for this trek.", "warning")
        return redirect(url_for("user_dashboard"))
    existing = query_one(
        "SELECT * FROM bookings WHERE user_id = ? AND trek_id = ?",
        (user["id"], trek_id),
    )
    if existing and existing["status"] == "Booked":
        flash("You already have a booking record for this trek.", "warning")
        return redirect(url_for("user_dashboard"))
    if existing and existing["status"] == "Completed":
        flash("This trek is already present in your completed history.", "warning")
        return redirect(url_for("user_dashboard"))

    db = get_db()
    if existing:
        db.execute(
            """
            UPDATE bookings
            SET booking_date = ?, status = 'Booked'
            WHERE id = ?
            """,
            (date.today().isoformat(), existing["id"]),
        )
    else:
        db.execute(
            """
            INSERT INTO bookings (user_id, trek_id, booking_date, status)
            VALUES (?, ?, ?, 'Booked')
            """,
            (user["id"], trek_id, date.today().isoformat()),
        )
    db.execute(
        "UPDATE treks SET available_slots = available_slots - 1 WHERE id = ?",
        (trek_id,),
    )
    db.commit()
    flash("Trek booked successfully.", "success")
    return redirect(url_for("user_dashboard"))


@app.post("/user/bookings/<int:booking_id>/cancel")
@login_required("user")
def cancel_booking(booking_id):
    booking = query_one(
        """
        SELECT b.*, t.status AS trek_status
        FROM bookings b
        JOIN treks t ON b.trek_id = t.id
        WHERE b.id = ? AND b.user_id = ? AND b.status = 'Booked'
        """,
        (booking_id, current_user()["id"]),
    )
    if booking is None:
        flash("Only active bookings can be cancelled.", "warning")
        return redirect(url_for("user_bookings"))
    if booking["trek_status"] != "Open":
        flash("This booking cannot be cancelled because the trek is no longer open.", "warning")
        return redirect(url_for("user_bookings"))
    db = get_db()
    db.execute("UPDATE bookings SET status = 'Cancelled' WHERE id = ?", (booking_id,))
    db.execute(
        "UPDATE treks SET available_slots = available_slots + 1 WHERE id = ?",
        (booking["trek_id"],),
    )
    db.commit()
    flash("Booking cancelled.", "info")
    return redirect(url_for("user_bookings"))


@app.route("/profile", methods=["GET", "POST"])
@login_required()
def profile():
    user = current_user()
    if user["role"] == "admin":
        flash("Profile editing is available for staff and trekkers.", "info")
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password:
            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("profile"))
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "warning")
                return redirect(url_for("profile"))
            if new_password != confirm_password:
                flash("New password and confirmation do not match.", "warning")
                return redirect(url_for("profile"))
            execute(
                """
                UPDATE users
                SET name = ?, phone = ?, password_hash = ?
                WHERE id = ?
                """,
                (name, phone, hash_password(new_password), user["id"]),
            )
        else:
            execute(
                "UPDATE users SET name = ?, phone = ? WHERE id = ?",
                (name, phone, user["id"]),
            )
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)
