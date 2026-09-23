"""Public-facing routes: home, services browsing, static info pages, contact, booking."""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app

from models import get_db, get_settings, log_activity, create_notification
from utils import Pagination

bp = Blueprint("public", __name__)


@bp.app_context_processor
def inject_globals():
    return {"site_settings": get_settings()}


@bp.route("/")
def index():
    db = get_db()
    services = db.execute(
        "SELECT * FROM services WHERE is_active = 1 ORDER BY id LIMIT 6"
    ).fetchall()
    stats = {
        "customers": db.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role = 'customer'"
        ).fetchone()["c"],
        "bookings": db.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()["c"],
        "services": db.execute(
            "SELECT COUNT(*) AS c FROM services WHERE is_active = 1"
        ).fetchone()["c"],
        "completed": db.execute(
            "SELECT COUNT(*) AS c FROM bookings WHERE status = 'Completed'"
        ).fetchone()["c"],
    }
    return render_template("index.html", services=services, stats=stats)


@bp.route("/services")
def services():
    db = get_db()
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    sort = request.args.get("sort", "default")
    page = request.args.get("page", 1, type=int)

    query = """SELECT services.*, categories.name AS category_name
               FROM services LEFT JOIN categories ON services.category_id = categories.id
               WHERE services.is_active = 1"""
    params = []
    if search:
        query += " AND (services.name LIKE ? OR services.description LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if category_id:
        query += " AND services.category_id = ?"
        params.append(category_id)

    sort_map = {
        "price_asc": " ORDER BY services.price ASC",
        "price_desc": " ORDER BY services.price DESC",
        "name": " ORDER BY services.name ASC",
        "default": " ORDER BY services.id ASC",
    }
    count_query = query.replace("services.*, categories.name AS category_name", "COUNT(*) AS c")
    total = db.execute(count_query, params).fetchone()["c"]

    per_page = current_app.config["ITEMS_PER_PAGE"]
    pagination = Pagination(page, per_page, total)
    query += sort_map.get(sort, sort_map["default"]) + " LIMIT ? OFFSET ?"
    params += [per_page, pagination.offset]

    all_services = db.execute(query, params).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    return render_template(
        "services.html", services=all_services, categories=categories,
        search=search, category_id=category_id, sort=sort, pagination=pagination,
    )


@bp.route("/services/<int:service_id>")
def service_detail(service_id):
    db = get_db()
    service = db.execute(
        """SELECT services.*, categories.name AS category_name
           FROM services LEFT JOIN categories ON services.category_id = categories.id
           WHERE services.id = ? AND services.is_active = 1""",
        (service_id,),
    ).fetchone()
    if not service:
        flash("That service is not available.", "error")
        return redirect(url_for("public.services"))
    related = db.execute(
        """SELECT * FROM services WHERE category_id = ? AND id != ? AND is_active = 1 LIMIT 3""",
        (service["category_id"], service_id),
    ).fetchall()
    return render_template("service_detail.html", service=service, related=related)


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/faq")
def faq():
    return render_template("faq.html")


@bp.route("/terms")
def terms():
    return render_template("terms.html")


@bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        message = request.form.get("message", "").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            errors.append("A valid email is required.")
        if not phone or len(phone) < 7:
            errors.append("A valid phone number is required.")
        if not message:
            errors.append("Message cannot be empty.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("contact.html", form=request.form)

        db = get_db()
        db.execute(
            "INSERT INTO contacts (name, email, phone, message) VALUES (?, ?, ?, ?)",
            (name, email, phone, message),
        )
        db.commit()
        flash("Thank you! Your message has been sent. We will get back to you soon.", "success")
        return redirect(url_for("public.contact"))

    return render_template("contact.html", form={})


@bp.route("/booking", methods=["GET", "POST"])
def booking():
    db = get_db()
    all_services = db.execute("SELECT * FROM services WHERE is_active = 1 ORDER BY id").fetchall()
    preselected_service = request.args.get("service_id", type=int)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        service_id = request.form.get("service_id", type=int)
        date = request.form.get("date", "").strip()
        notes = request.form.get("notes", "").strip()

        errors = []
        if not name:
            errors.append("Full name is required.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if not phone or len(phone) < 7:
            errors.append("A valid phone number is required.")
        service_row = None
        if not service_id:
            errors.append("Please select a service.")
        else:
            service_row = db.execute(
                "SELECT id FROM services WHERE id = ? AND is_active = 1", (service_id,)
            ).fetchone()
            if not service_row:
                errors.append("Selected service is invalid or unavailable.")
        if not date:
            errors.append("Preferred date is required.")
        else:
            try:
                chosen = datetime.strptime(date, "%Y-%m-%d").date()
                if chosen < datetime.now().date():
                    errors.append("Preferred date cannot be in the past.")
            except ValueError:
                errors.append("Invalid date format.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "booking.html", services=all_services, form=request.form,
                preselected_service=service_id,
            )

        user_id = session.get("user_id") if session.get("role") == "customer" else None
        cur = db.execute(
            """INSERT INTO bookings (user_id, name, email, phone, service_id, date, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')""",
            (user_id, name, email, phone, service_id, date, notes),
        )
        db.commit()
        booking_id = cur.lastrowid

        if user_id:
            create_notification(
                user_id, "Booking Received",
                f"Your booking #{booking_id} has been received and is Pending confirmation.",
            )
            log_activity(user_id, "Created booking", f"Booking #{booking_id}")

        flash(f"Booking confirmed! Your Booking ID is #{booking_id}.", "success")
        return redirect(url_for("public.booking_confirmation", booking_id=booking_id))

    return render_template(
        "booking.html", services=all_services, form={}, preselected_service=preselected_service,
    )


@bp.route("/booking/confirmation/<int:booking_id>")
def booking_confirmation(booking_id):
    db = get_db()
    booking_row = db.execute(
        """SELECT bookings.*, services.name AS service_name, services.price AS service_price
           FROM bookings JOIN services ON bookings.service_id = services.id
           WHERE bookings.id = ?""",
        (booking_id,),
    ).fetchone()
    if not booking_row:
        flash("Booking not found.", "error")
        return redirect(url_for("public.booking"))
    return render_template("booking_confirmation.html", booking=booking_row)
