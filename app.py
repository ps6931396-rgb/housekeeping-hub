"""
Housekeeping Hub PRO - Premium Housekeeping Management Platform
Full-stack Flask + SQLite application.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""
import os

from flask import Flask, render_template, session, url_for

import models
from config import Config


def service_image_url(service):
    """Resolve a service's image field to a displayable URL:
    - Cloudinary URL (starts with http) -> returned as-is
    - Admin-uploaded local file ('uploads/services/...') -> local static URL
    - Seeded default image ('cleaning.jpg') -> local static/images URL
    """
    image = service["image"] if hasattr(service, "keys") else service
    if not image:
        return url_for("static", filename="images/hero.jpg")
    if image.startswith("http://") or image.startswith("https://"):
        return image
    if image.startswith("uploads/"):
        return url_for("static", filename=image)
    return url_for("static", filename=f"images/{image}")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    models.init_app(app)

    from blueprints.public import bp as public_bp
    from blueprints.customer import bp as customer_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.api import bp as api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    app.jinja_env.globals["service_image_url"] = service_image_url

    @app.context_processor
    def inject_session_globals():
        return {
            "current_user_name": session.get("user_name"),
            "current_user_role": session.get("role"),
            "is_logged_in": "user_id" in session,
        }

    @app.context_processor
    def inject_notification_count():
        if session.get("role") == "customer":
            return {"unread_notifications": models.unread_notification_count(session["user_id"])}
        return {"unread_notifications": 0}

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    @app.errorhandler(413)
    def too_large(e):
        return render_template("500.html", message="Uploaded file is too large (max 5 MB)."), 413

    return app


app = create_app()

with app.app_context():
    models.setup_database(app)

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", True), host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
