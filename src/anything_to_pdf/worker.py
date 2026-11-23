"""
Worker thread for PDF generation, keeping the UI responsive.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal

from .pdf_engine import FileItem, GenerationError, generate_pdf

logger = logging.getLogger(__name__)


class PdfWorker(QThread):
    """Background thread that runs the PDF generation pipeline."""

    progress = Signal(int, int, str)      # current, total, label
    finished = Signal(str)                # output path
    failed = Signal(str)                  # user-facing error message

    def __init__(
        self,
        items: list[FileItem],
        destination: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._items = items
        self._destination = destination

    def run(self) -> None:
        try:
            generate_pdf(
                self._items,
                self._destination,
                progress_callback=lambda cur, tot, lbl: self.progress.emit(cur, tot, lbl),
            )
            self.finished.emit(str(self._destination))
        except GenerationError as exc:
            logger.warning("PDF generation failed: %s", exc)
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error in PdfWorker")
            self.failed.emit(
                "An unexpected error occurred.\n\n"
                "Please check that all files are valid and try again."
            )
