"""
Token-based JSON API layer.

This demonstrates JWT authentication and role-based access control for
programmatic consumers (mobile apps, external integrations), separate from
the session-based web app authentication used by the Jinja-rendered pages.
"""
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from models import get_db
from auth import generate_jwt, jwt_required

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user["is_active"]:
        return jsonify({"error": "Account is deactivated"}), 403

    token = generate_jwt(user)
    return jsonify({
        "token": token,
        "token_type": "Bearer",
        "expires_in_minutes": 60,
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]},
    })


@bp.route("/services", methods=["GET"])
def api_services():
    """Public endpoint - no token required, returns active services."""
    db = get_db()
    rows = db.execute(
        """SELECT services.id, services.name, services.description, services.price,
                  services.image, categories.name AS category
           FROM services LEFT JOIN categories ON services.category_id = categories.id
           WHERE services.is_active = 1 ORDER BY services.id"""
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/bookings", methods=["GET"])
@jwt_required(role="customer")
def api_my_bookings():
    """Protected endpoint - requires a valid customer JWT."""
    user_id = request.jwt_payload["sub"]
    db = get_db()
    rows = db.execute(
        """SELECT bookings.id, bookings.date, bookings.status, services.name AS service,
                  services.price
           FROM bookings JOIN services ON bookings.service_id = services.id
           WHERE bookings.user_id = ? ORDER BY bookings.created_at DESC""",
        (user_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/admin/stats", methods=["GET"])
@jwt_required(role="admin")
def api_admin_stats():
    """Protected endpoint - requires a valid admin JWT."""
    db = get_db()
    return jsonify({
        "total_users": db.execute("SELECT COUNT(*) AS c FROM users WHERE role='customer'").fetchone()["c"],
        "total_bookings": db.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()["c"],
        "total_services": db.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"],
    })
