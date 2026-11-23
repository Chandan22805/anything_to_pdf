"""
Thumbnail generation utilities.

Generates QPixmap thumbnails for images and placeholder icons for PDFs.
All work is done in memory; no temporary files are written.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap

logger = logging.getLogger(__name__)

THUMB_SIZE = 140  # Width and height of thumbnail in pixels


def make_thumbnail(path: Path, is_pdf: bool) -> QPixmap:
    """Return a *THUMB_SIZE × THUMB_SIZE* QPixmap for *path*."""
    if is_pdf:
        return _make_pdf_icon()
    return _make_image_thumbnail(path)


def _make_image_thumbnail(path: Path) -> QPixmap:
    """Load image, correct orientation, return square-ish thumbnail."""
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)

        # Convert to RGBA for safe compositing.
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Fit inside a square, preserving aspect ratio.
        img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)

        # Create white background and centre the thumbnail.
        bg = Image.new("RGBA", (THUMB_SIZE, THUMB_SIZE), (255, 255, 255, 255))
        offset_x = (THUMB_SIZE - img.width) // 2
        offset_y = (THUMB_SIZE - img.height) // 2
        bg.paste(img, (offset_x, offset_y), img)
        bg = bg.convert("RGB")

        # Convert PIL → QPixmap via raw bytes.
        buf = io.BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)
        qimage = QImage.fromData(buf.getvalue())
        return QPixmap.fromImage(qimage)
    except Exception as exc:
        logger.warning("Could not generate thumbnail for %s: %s", path, exc)
        return _make_error_icon()


def _make_pdf_icon() -> QPixmap:
    """Draw a simple PDF file icon using Qt."""
    pixmap = QPixmap(THUMB_SIZE, THUMB_SIZE)
    pixmap.fill(QColor("#FFFFFF"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # File body
    body_color = QColor("#E8F0FE")
    painter.setBrush(body_color)
    painter.setPen(QColor("#4285F4"))
    from PySide6.QtCore import QRect
    painter.drawRoundedRect(QRect(20, 15, 100, 110), 8, 8)

    # Folded corner
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QPolygon
    fold = QPolygon([
        QPoint(90, 15),
        QPoint(120, 45),
        QPoint(90, 45),
    ])
    painter.setBrush(QColor("#4285F4"))
    painter.drawPolygon(fold)

    # "PDF" label
    font = QFont("Arial", 20, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#EA4335"))
    painter.drawText(QRect(20, 60, 100, 40), Qt.AlignmentFlag.AlignCenter, "PDF")

    painter.end()
    return pixmap


def _make_error_icon() -> QPixmap:
    """Draw a simple error placeholder icon."""
    pixmap = QPixmap(THUMB_SIZE, THUMB_SIZE)
    pixmap.fill(QColor("#FFF3E0"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Arial", 11)
    painter.setFont(font)
    painter.setPen(QColor("#E65100"))
    from PySide6.QtCore import QRect
    painter.drawText(
        QRect(0, 0, THUMB_SIZE, THUMB_SIZE),
        Qt.AlignmentFlag.AlignCenter,
        "⚠\nCannot\npreview",
    )
    painter.end()
    return pixmap
