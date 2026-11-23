"""
Main application window for Anything to PDF.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .arrange_area import ArrangeArea
from .counter import FilenameCounter
from .pdf_engine import ConflictError, FileItem, GenerationError
from .worker import PdfWorker

logger = logging.getLogger(__name__)

APP_NAME = "Anything to PDF"
APP_VERSION = "1.0.0"


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self, counter: FilenameCounter | None = None):
        super().__init__()
        self._counter = counter or FilenameCounter()
        self._worker: PdfWorker | None = None
        self._last_output_path: Path | None = None

        self._setup_window()
        self._setup_ui()
        self._update_create_button()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 640)
        self.resize(1100, 700)

        # Clean, light background
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#F5F7FA"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_arrange_section(), stretch=1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet(
            """
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1A73E8, stop:1 #0D47A1
                );
            }
            """
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 18, 28, 18)

        icon_label = QLabel("📄")
        icon_label.setStyleSheet("font-size: 32px; background: transparent;")

        title_label = QLabel(APP_NAME)
        font = QFont()
        font.setPointSize(22)
        font.setWeight(QFont.Weight.DemiBold)
        title_label.setFont(font)
        title_label.setStyleSheet("color: white; background: transparent;")

        subtitle = QLabel("Combine images and PDFs into one document")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.75); font-size: 13px; background: transparent;")

        layout.addWidget(icon_label)
        layout.addSpacing(10)
        layout.addWidget(title_label)
        layout.addSpacing(16)
        layout.addWidget(subtitle)
        layout.addStretch()

        return header

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        # Add Files button
        self._add_btn = QPushButton("＋  Add Files")
        self._add_btn.setStyleSheet(self._primary_button_style())
        self._add_btn.setMinimumHeight(44)
        self._add_btn.setMinimumWidth(150)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.clicked.connect(self._on_add_files)
        layout.addWidget(self._add_btn)

        # Clear All button
        self._clear_btn = QPushButton("✕  Clear All")
        self._clear_btn.setStyleSheet(self._secondary_button_style())
        self._clear_btn.setMinimumHeight(44)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._on_clear_all)
        layout.addWidget(self._clear_btn)

        layout.addStretch()

        # File count info
        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #757575; font-size: 13px;")
        layout.addWidget(self._info_label)

        layout.addSpacing(16)

        # Create PDF button
        self._create_btn = QPushButton("🖨  Create PDF")
        self._create_btn.setStyleSheet(self._create_button_style())
        self._create_btn.setMinimumHeight(48)
        self._create_btn.setMinimumWidth(180)
        self._create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._create_btn.clicked.connect(self._on_create_pdf)
        layout.addWidget(self._create_btn)

        return toolbar

    def _build_arrange_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: #F5F7FA;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(24, 20, 24, 10)
        layout.setSpacing(10)

        instruction = QLabel(
            "Arrange files left to right — the leftmost file will appear first in your PDF."
        )
        instruction.setStyleSheet("color: #5F6368; font-size: 13px;")
        layout.addWidget(instruction)

        # Drop zone border frame
        self._drop_frame = QWidget()
        self._drop_frame.setStyleSheet(
            """
            QWidget {
                background: #FFFFFF;
                border: 2px dashed #BDBDBD;
                border-radius: 12px;
            }
            """
        )
        frame_layout = QVBoxLayout(self._drop_frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)

        self._arrange = ArrangeArea()
        self._arrange.files_changed.connect(self._on_files_changed)
        self._arrange.unsupported_dropped.connect(self._on_unsupported_files)
        frame_layout.addWidget(self._arrange)

        layout.addWidget(self._drop_frame, stretch=1)

        # Accept drops on the whole section
        section.setAcceptDrops(True)
        return section

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet("background: #FFFFFF; border-top: 1px solid #E0E0E0;")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 10, 24, 10)

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                background: #F5F5F5;
                height: 22px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1A73E8, stop:1 #0D47A1);
                border-radius: 6px;
            }
            """
        )
        layout.addWidget(self._progress_bar, stretch=1)

        self._status_label = QLabel(f"Next file: {self._counter.peek()}")
        self._status_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        layout.addWidget(self._status_label)

        return footer

    # ------------------------------------------------------------------
    # Button styles
    # ------------------------------------------------------------------

    def _primary_button_style(self) -> str:
        return """
            QPushButton {
                background: #1A73E8;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover { background: #1557B0; }
            QPushButton:pressed { background: #0D47A1; }
            QPushButton:disabled { background: #BDBDBD; }
        """

    def _secondary_button_style(self) -> str:
        return """
            QPushButton {
                background: #FFFFFF;
                color: #5F6368;
                border: 1px solid #DADCE0;
                border-radius: 8px;
                font-size: 14px;
                padding: 0 16px;
            }
            QPushButton:hover { background: #F8F9FA; border-color: #BDBDBD; }
            QPushButton:pressed { background: #E8F0FE; }
            QPushButton:disabled { color: #BDBDBD; border-color: #E8EAED; }
        """

    def _create_button_style(self) -> str:
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #34A853, stop:1 #1E8E3E);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 700;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2E9B4A, stop:1 #19772F);
            }
            QPushButton:pressed {
                background: #1B5E20;
            }
            QPushButton:disabled {
                background: #BDBDBD;
                color: #FFFFFF;
            }
        """

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images or PDF Files",
            str(Path.home()),
            "Supported Files (*.jpg *.jpeg *.png *.webp *.pdf);;"
            "Images (*.jpg *.jpeg *.png *.webp);;"
            "PDF Files (*.pdf);;"
            "All Files (*)",
        )
        if paths:
            self._arrange.add_files([Path(p) for p in paths])

    def _on_clear_all(self) -> None:
        if self._arrange.is_empty():
            return
        reply = QMessageBox.question(
            self,
            "Clear All Files",
            "Remove all files from the list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._arrange.remove_all()

    def _on_files_changed(self) -> None:
        count = len(self._arrange.file_items)
        if count == 0:
            self._info_label.setText("")
        elif count == 1:
            self._info_label.setText("1 file")
        else:
            self._info_label.setText(f"{count} files")
        self._update_create_button()

    def _on_unsupported_files(self, names: list[str]) -> None:
        if not names:
            return
        name_list = "\n".join(f"  • {n}" for n in names[:10])
        extra = f"\n  … and {len(names) - 10} more" if len(names) > 10 else ""
        QMessageBox.warning(
            self,
            "Unsupported Files",
            f"The following files are not supported and were not added:\n\n"
            f"{name_list}{extra}\n\n"
            "Supported formats: JPG, JPEG, PNG, WebP, PDF",
        )

    def _on_create_pdf(self) -> None:
        items = self._arrange.file_items
        if not items:
            QMessageBox.information(self, "No Files", "Please add at least one file first.")
            return

        suggested = self._counter.peek()
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF As",
            str(Path.home() / suggested),
            "PDF Files (*.pdf)",
        )
        if not save_path:
            return  # User cancelled

        destination = Path(save_path)
        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")

        # Conflict check (belt-and-suspenders; engine also checks)
        if destination.exists():
            reply = QMessageBox.warning(
                self,
                "File Already Exists",
                f'"{destination.name}" already exists in this folder.\n\n'
                "Do you want to replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            # Remove it so the engine won't raise ConflictError
            destination.unlink()

        self._start_generation(items, destination)

    def _start_generation(self, items: list[FileItem], destination: Path) -> None:
        self._set_ui_busy(True)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, len(items))
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Starting…")

        self._worker = PdfWorker(items, destination, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_generation_finished)
        self._worker.failed.connect(self._on_generation_failed)
        self._worker.start()

    def _on_progress(self, current: int, total: int, label: str) -> None:
        self._progress_bar.setValue(current)
        self._progress_bar.setFormat(label)

    def _on_generation_finished(self, output_path: str) -> None:
        self._last_output_path = Path(output_path)
        self._counter.advance()
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Next file: {self._counter.peek()}")

        self._show_success_dialog(self._last_output_path)

    def _on_generation_failed(self, message: str) -> None:
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)
        # Counter is NOT advanced on failure.
        QMessageBox.critical(self, "Could Not Create PDF", message)

    # ------------------------------------------------------------------
    # Success dialog
    # ------------------------------------------------------------------

    def _show_success_dialog(self, path: Path) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("PDF Created!")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        icon_lbl = QLabel("✅")
        icon_lbl.setStyleSheet("font-size: 36px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        msg_lbl = QLabel(f"<b>Your PDF was saved successfully!</b>")
        msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_lbl.setStyleSheet("font-size: 15px;")
        layout.addWidget(msg_lbl)

        path_lbl = QLabel(str(path))
        path_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path_lbl.setStyleSheet("color: #5F6368; font-size: 12px;")
        path_lbl.setWordWrap(True)
        layout.addWidget(path_lbl)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        open_pdf_btn = QPushButton("Open PDF")
        open_pdf_btn.setStyleSheet(self._primary_button_style())
        open_pdf_btn.setMinimumHeight(40)
        open_pdf_btn.clicked.connect(lambda: self._open_file(path))
        open_pdf_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(open_pdf_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setStyleSheet(self._secondary_button_style())
        open_folder_btn.setMinimumHeight(40)
        open_folder_btn.clicked.connect(lambda: self._open_folder(path.parent))
        open_folder_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(open_folder_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(self._secondary_button_style())
        close_btn.setMinimumHeight(40)
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        dialog.exec()

    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------

    def _set_ui_busy(self, busy: bool) -> None:
        self._add_btn.setEnabled(not busy)
        self._clear_btn.setEnabled(not busy)
        self._create_btn.setEnabled(not busy)
        self._create_btn.setText("Creating…" if busy else "🖨  Create PDF")

    def _update_create_button(self) -> None:
        has_files = not self._arrange.is_empty()
        self._create_btn.setEnabled(has_files)
        self._clear_btn.setEnabled(has_files)

    # ------------------------------------------------------------------
    # Open file / folder
    # ------------------------------------------------------------------

    @staticmethod
    def _open_file(path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            logger.warning("Could not open file: %s", exc)

    @staticmethod
    def _open_folder(path: Path) -> None:
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            logger.warning("Could not open folder: %s", exc)
