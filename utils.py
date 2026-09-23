"""Miscellaneous utility helpers: file uploads, pagination, exports."""
import csv
import io
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )


def save_uploaded_image(file_storage):
    """Save an uploaded image and return a value to store in the DB `image`
    column:
      - If CLOUDINARY_URL is configured, the file is uploaded to Cloudinary
        and the returned HTTPS URL is stored — this survives host restarts/
        redeploys on platforms with ephemeral disks (e.g. Render free tier).
      - Otherwise, it's saved to local disk under static/uploads/services/
        (fine for local dev, but NOT persistent on ephemeral hosts).
    Returns None if no valid file was provided.
    """
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None

    if current_app.config.get("CLOUDINARY_URL"):
        import cloudinary.uploader
        result = cloudinary.uploader.upload(file_storage, folder="housekeeping_hub/services")
        return result["secure_url"]

    ext = secure_filename(file_storage.filename).rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    file_storage.save(path)
    return f"uploads/services/{unique_name}"


class Pagination:
    """Simple pagination helper for server-rendered lists."""
    def __init__(self, page, per_page, total_count):
        self.page = max(1, page)
        self.per_page = per_page
        self.total_count = total_count
        self.total_pages = max(1, (total_count + per_page - 1) // per_page)
        self.page = min(self.page, self.total_pages)

    @property
    def offset(self):
        return (self.page - 1) * self.per_page

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.total_pages

    @property
    def pages(self):
        return range(1, self.total_pages + 1)


def bookings_to_csv(bookings):
    """Return an in-memory CSV file (string buffer) for a list of booking rows."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Booking ID", "Customer", "Email", "Phone", "Service", "Price",
                      "Date", "Status", "Created At"])
    for b in bookings:
        writer.writerow([
            b["id"], b["name"], b["email"], b["phone"], b["service_name"],
            b["service_price"], b["date"], b["status"], b["created_at"],
        ])
    output.seek(0)
    return output


def bookings_to_pdf(bookings, title="Bookings Report"):
    """Return an in-memory PDF file (BytesIO) summarizing bookings."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                             leftMargin=15 * mm, rightMargin=15 * mm,
                             topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>Housekeeping Hub — {title}</b>", styles["Title"]), Spacer(1, 10)]

    data = [["ID", "Customer", "Email", "Phone", "Service", "Price", "Date", "Status"]]
    for b in bookings:
        data.append([
            f"#{b['id']}", b["name"], b["email"], b["phone"], b["service_name"],
            f"{b['service_price']:.2f}", b["date"], b["status"],
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer
