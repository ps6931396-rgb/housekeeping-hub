"""
Authentication & authorization helpers.

- Web app (server-rendered pages) uses Flask's signed session cookies,
  which is the correct, secure mechanism for this architecture.
- A small JWT-protected API layer (see blueprints/api.py) is provided as
  a token-based auth demonstration for programmatic/API consumers.
"""
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import session, redirect, url_for, flash, request, jsonify, current_app


# ---------------------------------------------------------------------------
# Session-based decorators (web app)
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "customer":
            flash("Please log in to access this page.", "error")
            return redirect(url_for("customer.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            flash("Admin access required. Please log in as an administrator.", "error")
            return redirect(url_for("admin.admin_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Password reset tokens
# ---------------------------------------------------------------------------
def generate_reset_token():
    return secrets.token_urlsafe(32)


def token_expiry(minutes=30):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def is_token_valid(expiry_str):
    if not expiry_str:
        return False
    try:
        expiry = datetime.fromisoformat(expiry_str)
    except ValueError:
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < expiry


# ---------------------------------------------------------------------------
# JWT helpers (API layer)
# ---------------------------------------------------------------------------
def generate_jwt(user):
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=current_app.config["JWT_EXP_MINUTES"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_jwt(token):
    return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])


def jwt_required(role=None):
    """Decorator for API routes: validates a Bearer JWT and optionally a role."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401
            token = auth_header.split(" ", 1)[1]
            try:
                payload = decode_jwt(token)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            if role and payload.get("role") != role:
                return jsonify({"error": "Insufficient permissions"}), 403

            request.jwt_payload = payload
            return view(*args, **kwargs)
        return wrapped
    return decorator
