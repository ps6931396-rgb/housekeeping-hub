"""Customer authentication and dashboard routes."""
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    get_db, log_activity, get_notifications, unread_notification_count,
    mark_notifications_read,
)
from auth import login_required, generate_reset_token, token_expiry, is_token_valid

bp = Blueprint("customer", __name__)


# ---------------------------------------------------------------------------
# Registration / Login / Logout
# ---------------------------------------------------------------------------
@bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("role") == "customer":
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not name or len(name) < 2:
            errors.append("Please enter your full name.")
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Please enter a valid email address.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        db = get_db()
        if not errors and db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("An account with this email already exists. Please log in instead.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html", form=request.form)

        hashed = generate_password_hash(password)
        verification_token = generate_reset_token()
        cur = db.execute(
            "INSERT INTO users (name, email, password, phone, role, verification_token) "
            "VALUES (?, ?, ?, ?, 'customer', ?)",
            (name, email, hashed, phone, verification_token),
        )
        db.commit()
        log_activity(cur.lastrowid, "Registered", "New customer account created")
        verify_link = url_for("customer.verify_email", token=verification_token, _external=True)
        flash("Registration successful! You can now log in.", "success")
        return render_template("auth/verify_sent.html", verify_link=verify_link)

    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("role") == "customer":
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND role = 'customer'", (email,)
        ).fetchone()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", form=request.form)

        if not user["is_active"]:
            flash("Your account has been deactivated. Please contact support.", "error")
            return render_template("auth/login.html", form=request.form)

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["role"] = "customer"
        log_activity(user["id"], "Logged in")
        flash(f"Welcome back, {user['name']}!", "success")
        next_page = request.args.get("next")
        return redirect(next_page or url_for("customer.dashboard"))

    return render_template("auth/login.html", form={})


@bp.route("/logout")
def logout():
    if session.get("user_id"):
        log_activity(session["user_id"], "Logged out")
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("public.index"))


@bp.route("/verify-email/<token>")
def verify_email(token):
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE verification_token = ? AND role = 'customer'", (token,)
    ).fetchone()

    if not user:
        flash("Invalid or already-used verification link.", "error")
        return redirect(url_for("customer.login"))

    db.execute(
        "UPDATE users SET is_verified = 1, verification_token = NULL WHERE id = ?", (user["id"],)
    )
    db.commit()
    log_activity(user["id"], "Verified email")
    flash("Your email has been verified successfully!", "success")
    return redirect(url_for("customer.login"))


@bp.route("/resend-verification", methods=["POST"])
@login_required
def resend_verification():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if user["is_verified"]:
        flash("Your email is already verified.", "success")
        return redirect(url_for("customer.profile"))

    token = generate_reset_token()
    db.execute("UPDATE users SET verification_token = ? WHERE id = ?", (token, user["id"]))
    db.commit()
    verify_link = url_for("customer.verify_email", token=token, _external=True)
    return render_template("auth/verify_sent.html", verify_link=verify_link)


# ---------------------------------------------------------------------------
# Forgot / Reset password
# ---------------------------------------------------------------------------
@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    reset_link = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND role = 'customer'", (email,)
        ).fetchone()

        # Always show the same generic message, whether or not the account
        # exists, to avoid leaking which emails are registered.
        flash(
            "If an account exists for that email, a password reset link has been generated.",
            "success",
        )
        if user:
            token = generate_reset_token()
            expiry = token_expiry(minutes=30)
            db.execute(
                "UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
                (token, expiry.isoformat(), user["id"]),
            )
            db.commit()
            reset_link = url_for("customer.reset_password", token=token, _external=True)

        return render_template("auth/forgot_password.html", reset_link=reset_link)

    return render_template("auth/forgot_password.html", reset_link=None)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE reset_token = ?", (token,)).fetchone()

    if not user or not is_token_valid(user["reset_token_expiry"]):
        flash("This password reset link is invalid or has expired.", "error")
        return redirect(url_for("customer.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/reset_password.html", token=token)

        db.execute(
            "UPDATE users SET password = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?",
            (generate_password_hash(password), user["id"]),
        )
        db.commit()
        log_activity(user["id"], "Reset password")
        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("customer.login"))

    return render_template("auth/reset_password.html", token=token)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    bookings = db.execute(
        """SELECT bookings.*, services.name AS service_name, services.price AS service_price,
                  services.image AS service_image
           FROM bookings JOIN services ON bookings.service_id = services.id
           WHERE bookings.user_id = ?
           ORDER BY bookings.created_at DESC""",
        (user["id"],),
    ).fetchall()

    stats = {
        "total": len(bookings),
        "pending": sum(1 for b in bookings if b["status"] == "Pending"),
        "confirmed": sum(1 for b in bookings if b["status"] == "Confirmed"),
        "completed": sum(1 for b in bookings if b["status"] == "Completed"),
    }

    notifications = get_notifications(user["id"], limit=5)
    recent_activity = db.execute(
        "SELECT * FROM activity_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 6",
        (user["id"],),
    ).fetchall()

    return render_template(
        "customer/dashboard.html", user=user, bookings=bookings[:5], stats=stats,
        notifications=notifications, recent_activity=recent_activity,
    )


@bp.route("/dashboard/bookings")
@login_required
def my_bookings():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = """SELECT bookings.*, services.name AS service_name, services.price AS service_price
               FROM bookings JOIN services ON bookings.service_id = services.id
               WHERE bookings.user_id = ?"""
    params = [session["user_id"]]
    if status_filter:
        query += " AND bookings.status = ?"
        params.append(status_filter)
    query += " ORDER BY bookings.created_at DESC"
    bookings = db.execute(query, params).fetchall()
    return render_template(
        "customer/bookings.html", bookings=bookings, status_filter=status_filter,
        valid_statuses=current_app.config["VALID_STATUSES"],
    )


@bp.route("/dashboard/notifications")
@login_required
def notifications():
    db = get_db()
    items = get_notifications(session["user_id"], limit=100)
    mark_notifications_read(session["user_id"])
    return render_template("customer/notifications.html", notifications=items)


@bp.route("/dashboard/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        errors = []
        if not name or len(name) < 2:
            errors.append("Please enter a valid name.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db.execute("UPDATE users SET name = ?, phone = ? WHERE id = ?",
                       (name, phone, user["id"]))
            db.commit()
            session["user_name"] = name
            log_activity(user["id"], "Updated profile")
            flash("Profile updated successfully.", "success")
            return redirect(url_for("customer.profile"))

    return render_template("customer/profile.html", user=user)


@bp.route("/dashboard/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        current = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not check_password_hash(user["password"], current):
            errors.append("Current password is incorrect.")
        if not new_password or len(new_password) < 6:
            errors.append("New password must be at least 6 characters long.")
        if new_password != confirm:
            errors.append("New passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db.execute("UPDATE users SET password = ? WHERE id = ?",
                       (generate_password_hash(new_password), user["id"]))
            db.commit()
            log_activity(user["id"], "Changed password")
            flash("Password changed successfully.", "success")
            return redirect(url_for("customer.profile"))

    return render_template("customer/change_password.html")
