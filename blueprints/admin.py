"""Admin panel routes: dashboard, users, services, categories, bookings, reports, settings."""
from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    get_db, log_activity, create_notification, get_settings, update_setting,
)
from auth import admin_required
from utils import save_uploaded_image, Pagination, bookings_to_csv, bookings_to_pdf

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------------
@bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("role") == "admin":
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        admin = db.execute(
            "SELECT * FROM users WHERE email = ? AND role = 'admin'", (email,)
        ).fetchone()

        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["user_id"] = admin["id"]
            session["user_name"] = admin["name"]
            session["role"] = "admin"
            log_activity(admin["id"], "Admin logged in")
            flash("Welcome to the Admin Dashboard.", "success")
            return redirect(url_for("admin.admin_dashboard"))

        flash("Invalid admin credentials.", "error")
        return render_template("auth/admin_login.html", form=request.form)

    return render_template("auth/admin_login.html", form={})


@bp.route("/logout")
def admin_logout():
    if session.get("user_id"):
        log_activity(session["user_id"], "Admin logged out")
    session.clear()
    flash("Admin logged out successfully.", "success")
    return redirect(url_for("admin.admin_login"))


# ---------------------------------------------------------------------------
# Dashboard & Analytics
# ---------------------------------------------------------------------------
@bp.route("")
@admin_required
def admin_dashboard():
    db = get_db()
    total_users = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'customer'"
    ).fetchone()["c"]
    total_services = db.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"]
    total_bookings = db.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()["c"]
    revenue = db.execute(
        """SELECT COALESCE(SUM(services.price), 0) AS total
           FROM bookings JOIN services ON bookings.service_id = services.id
           WHERE bookings.status = 'Completed'"""
    ).fetchone()["total"]

    status_counts = {}
    for status in current_app.config["VALID_STATUSES"]:
        status_counts[status] = db.execute(
            "SELECT COUNT(*) AS c FROM bookings WHERE status = ?", (status,)
        ).fetchone()["c"]

    recent_bookings = db.execute(
        """SELECT bookings.*, services.name AS service_name, services.price AS service_price
           FROM bookings JOIN services ON bookings.service_id = services.id
           ORDER BY bookings.created_at DESC LIMIT 5"""
    ).fetchall()

    recent_activity = db.execute(
        """SELECT activity_log.*, users.name AS user_name
           FROM activity_log LEFT JOIN users ON activity_log.user_id = users.id
           ORDER BY activity_log.created_at DESC LIMIT 8"""
    ).fetchall()

    # Bookings over the last 14 days, for the trend chart
    days = []
    counts = []
    if db.backend == "postgres":
        day_filter_sql = "SELECT COUNT(*) AS c FROM bookings WHERE created_at::date = ?::date"
    else:
        day_filter_sql = "SELECT COUNT(*) AS c FROM bookings WHERE date(created_at) = ?"
    for i in range(13, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        c = db.execute(day_filter_sql, (day,)).fetchone()["c"]
        days.append(datetime.strptime(day, "%Y-%m-%d").strftime("%b %d"))
        counts.append(c)

    top_services = db.execute(
        """SELECT services.name, COUNT(bookings.id) AS booking_count
           FROM services LEFT JOIN bookings ON bookings.service_id = services.id
           GROUP BY services.id ORDER BY booking_count DESC LIMIT 5"""
    ).fetchall()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users, total_services=total_services,
        total_bookings=total_bookings, revenue=revenue,
        status_counts=status_counts, recent_bookings=recent_bookings,
        recent_activity=recent_activity, chart_days=days, chart_counts=counts,
        top_services=top_services,
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
@bp.route("/users")
@admin_required
def users():
    db = get_db()
    search = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = "SELECT * FROM users WHERE role = 'customer'"
    params = []
    if search:
        query += " AND (name LIKE ? OR email LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]

    count_query = query.replace("*", "COUNT(*) AS c")
    total = db.execute(count_query, params).fetchone()["c"]

    per_page = current_app.config["ADMIN_ITEMS_PER_PAGE"]
    pagination = Pagination(page, per_page, total)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [per_page, pagination.offset]

    all_users = db.execute(query, params).fetchall()
    return render_template("admin/users.html", users=all_users, search=search, pagination=pagination)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ? AND role = 'customer'", (user_id,)).fetchone()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.users"))

    new_status = 0 if user["is_active"] else 1
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    db.commit()
    log_activity(session["user_id"], "Toggled user status", f"User #{user_id} -> {'active' if new_status else 'inactive'}")
    flash(f"{user['name']} has been {'activated' if new_status else 'deactivated'}.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# Category management
# ---------------------------------------------------------------------------
@bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "error")
        elif db.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone():
            flash("That category already exists.", "error")
        else:
            db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            db.commit()
            flash("Category added successfully.", "success")
        return redirect(url_for("admin.categories"))

    all_categories = db.execute(
        """SELECT categories.*, COUNT(services.id) AS service_count
           FROM categories LEFT JOIN services ON services.category_id = categories.id
           GROUP BY categories.id ORDER BY categories.name"""
    ).fetchall()
    return render_template("admin/categories.html", categories=all_categories)


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id):
    db = get_db()
    db.execute("UPDATE services SET category_id = NULL WHERE category_id = ?", (category_id,))
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("admin.categories"))


# ---------------------------------------------------------------------------
# Service management
# ---------------------------------------------------------------------------
@bp.route("/services")
@admin_required
def services():
    db = get_db()
    search = request.args.get("q", "").strip()
    query = """SELECT services.*, categories.name AS category_name
               FROM services LEFT JOIN categories ON services.category_id = categories.id
               WHERE 1=1"""
    params = []
    if search:
        query += " AND services.name LIKE ?"
        params.append(f"%{search}%")
    query += " ORDER BY services.id DESC"
    all_services = db.execute(query, params).fetchall()
    return render_template("admin/services.html", services=all_services, search=search)


@bp.route("/services/add", methods=["GET", "POST"])
@admin_required
def add_service():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", type=float)
        category_id = request.form.get("category_id", type=int)
        image_file = request.files.get("image")

        errors = []
        if not name:
            errors.append("Service name is required.")
        if not description:
            errors.append("Description is required.")
        if price is None or price < 0:
            errors.append("A valid price is required.")

        image_path = save_uploaded_image(image_file)
        if not image_path:
            errors.append("A valid service image (png/jpg/jpeg/webp/gif) is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/service_form.html", categories=categories, service=None, form=request.form)

        db.execute(
            "INSERT INTO services (name, description, price, image, category_id, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (name, description, price, image_path, category_id),
        )
        db.commit()
        log_activity(session["user_id"], "Added service", name)
        flash("Service added successfully.", "success")
        return redirect(url_for("admin.services"))

    return render_template("admin/service_form.html", categories=categories, service=None, form={})


@bp.route("/services/<int:service_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_service(service_id):
    db = get_db()
    service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if not service:
        flash("Service not found.", "error")
        return redirect(url_for("admin.services"))
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", type=float)
        category_id = request.form.get("category_id", type=int)
        image_file = request.files.get("image")

        errors = []
        if not name:
            errors.append("Service name is required.")
        if not description:
            errors.append("Description is required.")
        if price is None or price < 0:
            errors.append("A valid price is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/service_form.html", categories=categories, service=service, form=request.form)

        image_path = save_uploaded_image(image_file) or service["image"]

        db.execute(
            "UPDATE services SET name=?, description=?, price=?, image=?, category_id=? WHERE id=?",
            (name, description, price, image_path, category_id, service_id),
        )
        db.commit()
        log_activity(session["user_id"], "Edited service", name)
        flash("Service updated successfully.", "success")
        return redirect(url_for("admin.services"))

    return render_template("admin/service_form.html", categories=categories, service=service, form=dict(service))


@bp.route("/services/<int:service_id>/toggle", methods=["POST"])
@admin_required
def toggle_service(service_id):
    db = get_db()
    service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if not service:
        flash("Service not found.", "error")
        return redirect(url_for("admin.services"))
    new_status = 0 if service["is_active"] else 1
    db.execute("UPDATE services SET is_active = ? WHERE id = ?", (new_status, service_id))
    db.commit()
    flash(f"{service['name']} is now {'enabled' if new_status else 'disabled'}.", "success")
    return redirect(url_for("admin.services"))


@bp.route("/services/<int:service_id>/delete", methods=["POST"])
@admin_required
def delete_service(service_id):
    db = get_db()
    in_use = db.execute("SELECT COUNT(*) AS c FROM bookings WHERE service_id = ?", (service_id,)).fetchone()["c"]
    if in_use:
        flash("This service has existing bookings and cannot be deleted. Disable it instead.", "error")
        return redirect(url_for("admin.services"))
    db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    db.commit()
    flash("Service deleted.", "success")
    return redirect(url_for("admin.services"))


# ---------------------------------------------------------------------------
# Booking management
# ---------------------------------------------------------------------------
@bp.route("/bookings")
@admin_required
def bookings():
    db = get_db()
    status_filter = request.args.get("status", "")
    search = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = """SELECT bookings.*, services.name AS service_name, services.price AS service_price
               FROM bookings JOIN services ON bookings.service_id = services.id WHERE 1=1"""
    params = []
    if status_filter:
        query += " AND bookings.status = ?"
        params.append(status_filter)
    if search:
        query += " AND (bookings.name LIKE ? OR bookings.email LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]

    count_query = query.replace(
        "bookings.*, services.name AS service_name, services.price AS service_price", "COUNT(*) AS c"
    )
    total = db.execute(count_query, params).fetchone()["c"]

    per_page = current_app.config["ADMIN_ITEMS_PER_PAGE"]
    pagination = Pagination(page, per_page, total)
    query += " ORDER BY bookings.created_at DESC LIMIT ? OFFSET ?"
    params += [per_page, pagination.offset]

    all_bookings = db.execute(query, params).fetchall()
    return render_template(
        "admin/bookings.html", bookings=all_bookings, status_filter=status_filter, search=search,
        pagination=pagination, valid_statuses=current_app.config["VALID_STATUSES"],
    )


@bp.route("/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
def update_booking_status(booking_id):
    new_status = request.form.get("status", "")
    if new_status not in current_app.config["VALID_STATUSES"]:
        flash("Invalid status value.", "error")
        return redirect(url_for("admin.bookings"))

    db = get_db()
    booking_row = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking_row:
        flash("Booking not found.", "error")
        return redirect(url_for("admin.bookings"))

    db.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id))
    db.commit()
    log_activity(session["user_id"], "Updated booking status", f"Booking #{booking_id} -> {new_status}")

    if booking_row["user_id"]:
        create_notification(
            booking_row["user_id"], "Booking Status Updated",
            f"Your booking #{booking_id} status changed to {new_status}.",
        )

    flash(f"Booking #{booking_id} status updated to {new_status}.", "success")
    return redirect(request.referrer or url_for("admin.bookings"))


@bp.route("/bookings/export/csv")
@admin_required
def export_bookings_csv():
    db = get_db()
    all_bookings = db.execute(
        """SELECT bookings.*, services.name AS service_name, services.price AS service_price
           FROM bookings JOIN services ON bookings.service_id = services.id
           ORDER BY bookings.created_at DESC"""
    ).fetchall()
    csv_buffer = bookings_to_csv(all_bookings)
    return send_file(
        io_bytes(csv_buffer), mimetype="text/csv", as_attachment=True,
        download_name="bookings_export.csv",
    )


@bp.route("/bookings/export/pdf")
@admin_required
def export_bookings_pdf():
    db = get_db()
    all_bookings = db.execute(
        """SELECT bookings.*, services.name AS service_name, services.price AS service_price
           FROM bookings JOIN services ON bookings.service_id = services.id
           ORDER BY bookings.created_at DESC"""
    ).fetchall()
    pdf_buffer = bookings_to_pdf(all_bookings, title="Bookings Report")
    return send_file(
        pdf_buffer, mimetype="application/pdf", as_attachment=True,
        download_name="bookings_report.pdf",
    )


def io_bytes(string_buffer):
    """Convert a text StringIO (from csv writer) into a BytesIO for send_file."""
    import io
    data = string_buffer.getvalue().encode("utf-8")
    return io.BytesIO(data)


# ---------------------------------------------------------------------------
# Contact messages
# ---------------------------------------------------------------------------
@bp.route("/contacts")
@admin_required
def contacts():
    db = get_db()
    messages = db.execute("SELECT * FROM contacts ORDER BY created_at DESC").fetchall()
    return render_template("admin/contacts.html", contacts=messages)


# ---------------------------------------------------------------------------
# Reports & Analytics
# ---------------------------------------------------------------------------
@bp.route("/reports")
@admin_required
def reports():
    db = get_db()
    revenue_by_service = db.execute(
        """SELECT services.name, COALESCE(SUM(services.price), 0) AS revenue, COUNT(bookings.id) AS bookings
           FROM services LEFT JOIN bookings ON bookings.service_id = services.id AND bookings.status = 'Completed'
           GROUP BY services.id ORDER BY revenue DESC"""
    ).fetchall()

    status_counts = {}
    for status in current_app.config["VALID_STATUSES"]:
        status_counts[status] = db.execute(
            "SELECT COUNT(*) AS c FROM bookings WHERE status = ?", (status,)
        ).fetchone()["c"]

    if db.backend == "postgres":
        month_expr = "to_char(bookings.created_at, 'YYYY-MM')"
    else:
        month_expr = "strftime('%Y-%m', bookings.created_at)"

    monthly_revenue = db.execute(
        f"""SELECT {month_expr} AS month,
                  COALESCE(SUM(services.price), 0) AS revenue
           FROM bookings JOIN services ON bookings.service_id = services.id
           WHERE bookings.status = 'Completed'
           GROUP BY month ORDER BY month DESC LIMIT 6"""
    ).fetchall()

    return render_template(
        "admin/reports.html", revenue_by_service=revenue_by_service,
        status_counts=status_counts, monthly_revenue=list(reversed(monthly_revenue)),
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        for key in ["site_name", "support_email", "support_phone", "currency_symbol", "address"]:
            value = request.form.get(key, "").strip()
            if value:
                update_setting(key, value)
        log_activity(session["user_id"], "Updated site settings")
        flash("Settings updated successfully.", "success")
        return redirect(url_for("admin.settings"))

    current_settings = get_settings()
    return render_template("admin/settings.html", settings=current_settings)


@bp.route("/settings/change-password", methods=["POST"])
@admin_required
def admin_change_password():
    db = get_db()
    admin = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not check_password_hash(admin["password"], current):
        flash("Current password is incorrect.", "error")
    elif not new_password or len(new_password) < 6:
        flash("New password must be at least 6 characters long.", "error")
    elif new_password != confirm:
        flash("New passwords do not match.", "error")
    else:
        db.execute("UPDATE users SET password = ? WHERE id = ?",
                   (generate_password_hash(new_password), admin["id"]))
        db.commit()
        log_activity(admin["id"], "Admin changed password")
        flash("Password changed successfully.", "success")

    return redirect(url_for("admin.settings"))
