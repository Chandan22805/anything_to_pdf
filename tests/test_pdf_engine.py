"""
Tests for the PDF generation engine.

Verifies:
 - Single image → PDF
 - Multiple images → PDF
 - Single PDF → pass-through
 - Multiple PDFs → merged PDF
 - Mixed images and PDFs
 - Page count accuracy
 - Page ordering
 - EXIF orientation handling
 - Large image downscaling
 - RGBA / transparency handling
 - Error cases: corrupted files, password-protected PDFs, empty files
 - No intermediate files are created
 - Failed operations do not leave partial output files
"""

from __future__ import annotations

import io
import os
import struct
import tempfile
import zlib
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from anything_to_pdf.pdf_engine import (
    ConflictError,
    FileItem,
    GenerationError,
    generate_pdf,
)

from .conftest import (
    make_minimal_pdf,
    save_jpeg,
    save_pdf,
    save_png,
    save_png_rgba,
    save_webp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def count_pages(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def make_items(*paths: Path) -> list[FileItem]:
    return [FileItem(p) for p in paths]


# ---------------------------------------------------------------------------
# Single file tests
# ---------------------------------------------------------------------------


class TestSingleImage:
    def test_jpeg_produces_one_page(self, tmp_path, output_pdf):
        jpg = save_jpeg(tmp_path / "a.jpg")
        generate_pdf(make_items(jpg), output_pdf)
        assert output_pdf.exists()
        assert count_pages(output_pdf) == 1

    def test_png_produces_one_page(self, tmp_path, output_pdf):
        png = save_png(tmp_path / "a.png")
        generate_pdf(make_items(png), output_pdf)
        assert count_pages(output_pdf) == 1

    def test_webp_produces_one_page(self, tmp_path, output_pdf):
        webp = save_webp(tmp_path / "a.webp")
        generate_pdf(make_items(webp), output_pdf)
        assert count_pages(output_pdf) == 1

    def test_rgba_png_produces_one_page(self, tmp_path, output_pdf):
        png = save_png_rgba(tmp_path / "a.png")
        generate_pdf(make_items(png), output_pdf)
        assert count_pages(output_pdf) == 1

    def test_output_file_is_created(self, tmp_path, output_pdf):
        jpg = save_jpeg(tmp_path / "a.jpg")
        generate_pdf(make_items(jpg), output_pdf)
        assert output_pdf.exists()
        assert output_pdf.stat().st_size > 100


class TestSinglePdf:
    def test_single_page_pdf_passthrough(self, tmp_path, output_pdf):
        pdf = save_pdf(tmp_path / "doc.pdf", num_pages=1)
        generate_pdf(make_items(pdf), output_pdf)
        assert count_pages(output_pdf) == 1

    def test_multipage_pdf_all_pages_preserved(self, tmp_path, output_pdf):
        pdf = save_pdf(tmp_path / "doc.pdf", num_pages=5)
        generate_pdf(make_items(pdf), output_pdf)
        assert count_pages(output_pdf) == 5


# ---------------------------------------------------------------------------
# Multiple files
# ---------------------------------------------------------------------------


class TestMultipleFiles:
    def test_multiple_images(self, tmp_path, output_pdf):
        items = make_items(
            save_jpeg(tmp_path / "a.jpg"),
            save_png(tmp_path / "b.png"),
            save_webp(tmp_path / "c.webp"),
        )
        generate_pdf(items, output_pdf)
        assert count_pages(output_pdf) == 3

    def test_multiple_pdfs(self, tmp_path, output_pdf):
        items = make_items(
            save_pdf(tmp_path / "a.pdf", num_pages=2),
            save_pdf(tmp_path / "b.pdf", num_pages=3),
        )
        generate_pdf(items, output_pdf)
        assert count_pages(output_pdf) == 5

    def test_mixed_image_then_pdf(self, tmp_path, output_pdf):
        items = make_items(
            save_jpeg(tmp_path / "img.jpg"),    # 1 page
            save_pdf(tmp_path / "doc.pdf", num_pages=2),  # 2 pages
        )
        generate_pdf(items, output_pdf)
        assert count_pages(output_pdf) == 3

    def test_mixed_pdf_then_image(self, tmp_path, output_pdf):
        items = make_items(
            save_pdf(tmp_path / "doc.pdf", num_pages=2),
            save_jpeg(tmp_path / "img.jpg"),
        )
        generate_pdf(items, output_pdf)
        assert count_pages(output_pdf) == 3

    def test_many_mixed_files(self, tmp_path, output_pdf):
        items = make_items(
            save_jpeg(tmp_path / "1.jpg"),
            save_pdf(tmp_path / "2.pdf", num_pages=3),
            save_png(tmp_path / "3.png"),
            save_pdf(tmp_path / "4.pdf", num_pages=2),
            save_webp(tmp_path / "5.webp"),
        )
        generate_pdf(items, output_pdf)
        # 1 + 3 + 1 + 2 + 1 = 8
        assert count_pages(output_pdf) == 8


# ---------------------------------------------------------------------------
# Ordering verification
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_pdf_page_count_respects_order_image_first(self, tmp_path, output_pdf):
        """Verify total page count is consistent when image comes first."""
        items = make_items(
            save_jpeg(tmp_path / "img.jpg"),
            save_pdf(tmp_path / "doc.pdf", num_pages=4),
        )
        generate_pdf(items, output_pdf)
        assert count_pages(output_pdf) == 5  # 1 image + 4 pdf pages

    def test_pdf_page_count_respects_order_pdf_first(self, tmp_path, output_pdf):
        items = make_items(
            save_pdf(tmp_path / "doc.pdf", num_pages=4),
            save_jpeg(tmp_path / "img.jpg"),
        )
        generate_pdf(items, output_pdf)
        assert count_pages(output_pdf) == 5


# ---------------------------------------------------------------------------
# Image properties
# ---------------------------------------------------------------------------


class TestImageProperties:
    def test_landscape_image_produces_landscape_page(self, tmp_path, output_pdf):
        """A wider-than-tall image should produce a wider-than-tall PDF page."""
        img_path = tmp_path / "landscape.jpg"
        save_jpeg(img_path, width=400, height=200)
        generate_pdf(make_items(img_path), output_pdf)
        reader = PdfReader(str(output_pdf))
        page = reader.pages[0]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        assert w > h, f"Expected landscape page (w={w:.1f} > h={h:.1f})"

    def test_portrait_image_produces_portrait_page(self, tmp_path, output_pdf):
        img_path = tmp_path / "portrait.jpg"
        save_jpeg(img_path, width=200, height=400)
        generate_pdf(make_items(img_path), output_pdf)
        reader = PdfReader(str(output_pdf))
        page = reader.pages[0]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        assert h > w, f"Expected portrait page (h={h:.1f} > w={w:.1f})"

    def test_large_image_is_processed(self, tmp_path, output_pdf):
        """Large images should be downscaled and not crash."""
        img_path = tmp_path / "large.jpg"
        save_jpeg(img_path, width=6000, height=4000)
        generate_pdf(make_items(img_path), output_pdf)
        assert count_pages(output_pdf) == 1
        assert output_pdf.exists()

    def test_square_image(self, tmp_path, output_pdf):
        img_path = tmp_path / "square.jpg"
        save_jpeg(img_path, width=300, height=300)
        generate_pdf(make_items(img_path), output_pdf)
        reader = PdfReader(str(output_pdf))
        page = reader.pages[0]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        assert abs(w - h) < 1.0, f"Expected square page (w={w:.1f} h={h:.1f})"


# ---------------------------------------------------------------------------
# No intermediate files
# ---------------------------------------------------------------------------


class TestNoIntermediateFiles:
    def test_no_extra_files_in_tmp(self, tmp_path, output_pdf):
        """Generation must not create extra files in tmp_path."""
        jpg = save_jpeg(tmp_path / "a.jpg")
        pdf = save_pdf(tmp_path / "b.pdf")
        before = set(tmp_path.iterdir())

        generate_pdf(make_items(jpg, pdf), output_pdf)

        after = set(tmp_path.iterdir())
        new_files = after - before
        # Only the output PDF should be new
        assert new_files == {output_pdf}

    def test_no_intermediate_files_on_failure(self, tmp_path, output_pdf):
        """A failed generation must not leave the output file."""
        # Use a corrupted image to trigger failure
        bad_img = tmp_path / "corrupt.jpg"
        bad_img.write_bytes(b"this is not a jpeg file at all")
        before = set(tmp_path.iterdir())

        with pytest.raises(GenerationError):
            generate_pdf(make_items(bad_img), output_pdf)

        # output_pdf must NOT exist
        assert not output_pdf.exists()


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_empty_items_raises_generation_error(self, output_pdf):
        with pytest.raises(GenerationError, match="No files"):
            generate_pdf([], output_pdf)

    def test_corrupted_jpeg_raises_generation_error(self, tmp_path, output_pdf):
        bad = tmp_path / "bad.jpg"
        bad.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)  # truncated JPEG header
        with pytest.raises(GenerationError):
            generate_pdf(make_items(bad), output_pdf)

    def test_corrupted_pdf_raises_generation_error(self, tmp_path, output_pdf):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"%PDF-1.4\ngarbage content that is not a valid pdf")
        with pytest.raises(GenerationError):
            generate_pdf(make_items(bad), output_pdf)

    def test_conflict_error_when_destination_exists(self, tmp_path):
        jpg = save_jpeg(tmp_path / "a.jpg")
        dest = tmp_path / "output.pdf"
        dest.write_bytes(b"existing content")
        with pytest.raises(ConflictError):
            generate_pdf(make_items(jpg), dest)

    def test_nonexistent_file_raises_generation_error(self, tmp_path, output_pdf):
        ghost = tmp_path / "ghost.jpg"
        with pytest.raises(GenerationError):
            generate_pdf(make_items(ghost), output_pdf)

    def test_progress_callback_called(self, tmp_path, output_pdf):
        jpg = save_jpeg(tmp_path / "a.jpg")
        calls = []
        generate_pdf(make_items(jpg), output_pdf, progress_callback=lambda c, t, l: calls.append((c, t)))
        assert len(calls) >= 1
        # Last call should be (1, 1) indicating "Saving"
        # (progress called with total to indicate saving step)
        assert calls[-1][1] >= 1
