"""Application configuration."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "housekeeping-hub-pro-super-secret-key-2026")
    JWT_SECRET = os.environ.get("JWT_SECRET", "housekeeping-hub-pro-jwt-secret-2026")
    JWT_EXP_MINUTES = int(os.environ.get("JWT_EXP_MINUTES", "60"))
    DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    DATABASE = os.path.join(BASE_DIR, "database", "housekeeping.db")
    SCHEMA = os.path.join(BASE_DIR, "database", "schema.sql")

    # If DATABASE_URL is set (e.g. a Neon/Postgres connection string), the app
    # uses PostgreSQL for persistent storage. Otherwise it falls back to the
    # local SQLite file above — convenient for local development, but NOT
    # persistent on platforms with ephemeral disks (e.g. Render free tier).
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "services")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload limit

    # If CLOUDINARY_URL is set, uploaded service images are stored on
    # Cloudinary (persistent, free tier available) instead of local disk.
    CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "").strip()

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@housekeepinghub.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

    ITEMS_PER_PAGE = 6
    ADMIN_ITEMS_PER_PAGE = 10

    VALID_STATUSES = ["Pending", "Confirmed", "Completed", "Cancelled"]

    DEFAULT_CATEGORIES = ["Residential", "Commercial", "Specialty"]

    DEFAULT_SERVICES = [
        ("Room Cleaning", "Residential",
         "Thorough cleaning of bedrooms, living rooms and common areas including dusting, "
         "vacuuming, mopping and sanitizing surfaces for a fresh, healthy living space.",
         499.00, "cleaning.jpg"),
        ("Laundry Service", "Residential",
         "Complete washing, drying, ironing and folding service for clothes, bedsheets and "
         "linens, handled with care and delivered on time.",
         299.00, "laundry.jpg"),
        ("Maintenance", "Commercial",
         "General household and office maintenance including minor plumbing, electrical "
         "fixture checks, fittings and repairs carried out by trained staff.",
         699.00, "maintenance.jpg"),
        ("Inventory Management", "Commercial",
         "Organized tracking and management of household or facility supplies, cleaning "
         "stock and consumables to ensure nothing runs out.",
         399.00, "inventory.jpg"),
        ("Deep Cleaning", "Specialty",
         "Intensive, detailed cleaning covering hard-to-reach areas, kitchen degreasing, "
         "bathroom descaling and complete sanitization.",
         999.00, "deepcleaning.jpg"),
    ]

    DEFAULT_SETTINGS = {
        "site_name": "Housekeeping Hub",
        "support_email": "support@housekeepinghub.com",
        "support_phone": "+91 98765 43210",
        "currency_symbol": "₹",
        "address": "123 Clean Street, Service City, 400001",
    }
