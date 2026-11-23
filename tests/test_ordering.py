"""
Tests for the ArrangeArea widget (file ordering, adding, removing).

These tests use a minimal QApplication so PySide6 widgets can be constructed
without displaying a window on screen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from .conftest import save_jpeg, save_pdf, save_png, save_webp


# ---------------------------------------------------------------------------
# PySide6 application fixture (session-scoped — only one QApplication needed)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qt_app():
    """Create a headless QApplication for the session."""
    # Must set QT_QPA_PLATFORM before importing PySide6 widgets
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


# ---------------------------------------------------------------------------
# ArrangeArea tests
# ---------------------------------------------------------------------------


class TestArrangeAreaOrdering:

    def test_add_single_file(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        jpg = save_jpeg(tmp_path / "a.jpg")
        area.add_files([jpg])
        items = area.file_items
        assert len(items) == 1
        assert items[0].path == jpg

    def test_add_multiple_files_preserves_order(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        paths = [
            save_jpeg(tmp_path / "a.jpg"),
            save_png(tmp_path / "b.png"),
            save_pdf(tmp_path / "c.pdf"),
        ]
        area.add_files(paths)
        items = area.file_items
        assert [i.path for i in items] == paths

    def test_duplicate_files_are_skipped(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        jpg = save_jpeg(tmp_path / "a.jpg")
        area.add_files([jpg])
        area.add_files([jpg])  # Duplicate
        assert len(area.file_items) == 1

    def test_unsupported_file_emits_signal(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        txt = tmp_path / "file.txt"
        txt.write_text("hello")
        rejected = []
        area.unsupported_dropped.connect(lambda names: rejected.extend(names))
        area.add_files([txt])
        assert len(rejected) == 1
        assert "file.txt" in rejected
        assert area.is_empty()

    def test_remove_all(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        area.add_files([
            save_jpeg(tmp_path / "a.jpg"),
            save_png(tmp_path / "b.png"),
        ])
        assert not area.is_empty()
        area.remove_all()
        assert area.is_empty()

    def test_is_empty_initially(self, qt_app):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        assert area.is_empty()

    def test_mixed_image_pdf_order(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        jpg = save_jpeg(tmp_path / "img.jpg")
        pdf = save_pdf(tmp_path / "doc.pdf")
        area.add_files([jpg, pdf])
        items = area.file_items
        assert items[0].is_pdf is False
        assert items[1].is_pdf is True

    def test_pdf_then_image_order(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        pdf = save_pdf(tmp_path / "doc.pdf")
        jpg = save_jpeg(tmp_path / "img.jpg")
        area.add_files([pdf, jpg])
        items = area.file_items
        assert items[0].is_pdf is True
        assert items[1].is_pdf is False

    def test_add_files_after_initial_load(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        jpg = save_jpeg(tmp_path / "a.jpg")
        area.add_files([jpg])
        png = save_png(tmp_path / "b.png")
        area.add_files([png])
        items = area.file_items
        assert len(items) == 2
        assert items[0].path == jpg
        assert items[1].path == png

    def test_files_changed_signal_emitted_on_add(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        changed_count = [0]
        area.files_changed.connect(lambda: changed_count.__setitem__(0, changed_count[0] + 1))
        area.add_files([save_jpeg(tmp_path / "a.jpg")])
        assert changed_count[0] == 1

    def test_files_changed_signal_emitted_on_remove_all(self, qt_app, tmp_path):
        from anything_to_pdf.arrange_area import ArrangeArea
        area = ArrangeArea()
        area.add_files([save_jpeg(tmp_path / "a.jpg")])
        changed_count = [0]
        area.files_changed.connect(lambda: changed_count.__setitem__(0, changed_count[0] + 1))
        area.remove_all()
        assert changed_count[0] == 1


# ---------------------------------------------------------------------------
# FileItem tests
# ---------------------------------------------------------------------------


class TestFileItem:

    def test_pdf_item_identified_correctly(self, tmp_path):
        from anything_to_pdf.pdf_engine import FileItem
        pdf = save_pdf(tmp_path / "doc.pdf")
        item = FileItem(pdf)
        assert item.is_pdf is True

    def test_image_item_identified_correctly(self, tmp_path):
        from anything_to_pdf.pdf_engine import FileItem
        jpg = save_jpeg(tmp_path / "photo.jpg")
        item = FileItem(jpg)
        assert item.is_pdf is False

    def test_display_name_is_filename(self, tmp_path):
        from anything_to_pdf.pdf_engine import FileItem
        jpg = save_jpeg(tmp_path / "my_photo.jpg")
        item = FileItem(jpg)
        assert item.display_name == "my_photo.jpg"
