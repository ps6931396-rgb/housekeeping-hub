"""
Production WSGI entry point.

Used by WSGI servers such as Gunicorn or uWSGI:
    gunicorn wsgi:app -b 0.0.0.0:8000 --workers 3
"""
from app import app

if __name__ == "__main__":
    app.run()
