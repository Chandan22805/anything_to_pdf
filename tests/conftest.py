"""
Shared pytest fixtures and helpers for the test suite.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Helpers to create test files in memory / on disk
# ---------------------------------------------------------------------------


def make_rgb_image(width: int = 200, height: int = 150, color=(100, 150, 200)) -> Image.Image:
    """Return a simple solid-color PIL Image."""
    return Image.new("RGB", (width, height), color)


def save_jpeg(path: Path, width=200, height=150, color=(100, 150, 200)) -> Path:
    img = make_rgb_image(width, height, color)
    img.save(path, format="JPEG")
    return path


def save_png(path: Path, width=200, height=150, color=(200, 100, 100)) -> Path:
    img = make_rgb_image(width, height, color)
    img.save(path, format="PNG")
    return path


def save_webp(path: Path, width=200, height=150, color=(100, 200, 100)) -> Path:
    img = make_rgb_image(width, height, color)
    img.save(path, format="WEBP")
    return path


def save_png_rgba(path: Path, width=200, height=150) -> Path:
    """PNG with transparency channel."""
    img = Image.new("RGBA", (width, height), (100, 100, 200, 180))
    img.save(path, format="PNG")
    return path


def make_minimal_pdf(num_pages: int = 1) -> bytes:
    """
    Create a minimal valid PDF in memory using pypdf.
    """
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def save_pdf(path: Path, num_pages: int = 1) -> Path:
    path.write_bytes(make_minimal_pdf(num_pages))
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp(tmp_path):
    """Alias for tmp_path for convenience."""
    return tmp_path


@pytest.fixture
def jpeg_file(tmp_path):
    return save_jpeg(tmp_path / "photo.jpg")


@pytest.fixture
def png_file(tmp_path):
    return save_png(tmp_path / "image.png")


@pytest.fixture
def webp_file(tmp_path):
    return save_webp(tmp_path / "image.webp")


@pytest.fixture
def pdf_file(tmp_path):
    return save_pdf(tmp_path / "document.pdf", num_pages=1)


@pytest.fixture
def multipage_pdf(tmp_path):
    return save_pdf(tmp_path / "multi.pdf", num_pages=3)


@pytest.fixture
def output_pdf(tmp_path):
    return tmp_path / "output.pdf"
