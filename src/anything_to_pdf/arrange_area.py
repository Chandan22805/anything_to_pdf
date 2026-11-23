"""
ArrangeArea — horizontal scrollable area for file cards with drag-and-drop reordering.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .file_card import CARD_HEIGHT, CARD_WIDTH, FileCard
from .pdf_engine import FileItem

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


class ArrangeArea(QWidget):
    """
    Contains a horizontal scrollable list of FileCards.
    Supports:
     - OS-level file drop (from file manager)
     - Internal card drag-and-drop for reordering
    """

    files_changed = Signal()  # emitted whenever the list changes
    unsupported_dropped = Signal(list)  # list[str] of rejected filenames

    def __init__(self, parent: QWidget | None = None):
        super(__class__, self).__init__(parent)
        self._cards: list[FileCard] = []
        self._dragged_card: FileCard | None = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(CARD_HEIGHT + 40)
        self._scroll.setStyleSheet(
            """
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal {
                height: 10px;
                background: #F5F5F5;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #BDBDBD;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover { background: #9E9E9E; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
            """
        )

        # Inner container that holds the cards
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._cards_layout = QHBoxLayout(self._container)
        self._cards_layout.setContentsMargins(16, 12, 16, 12)
        self._cards_layout.setSpacing(14)
        self._cards_layout.addStretch()   # pushes cards left-to-right naturally

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

        # Drop-zone overlay shown when list is empty
        self._drop_hint = QLabel(
            "📂  Drop files here, or click  Add Files  above"
        )
        self._drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint.setStyleSheet(
            """
            color: #9E9E9E;
            font-size: 15px;
            padding: 20px;
            """
        )
        outer.addWidget(self._drop_hint)

        self._update_hint_visibility()

        # Accept drops
        self.setAcceptDrops(True)
        self._scroll.setAcceptDrops(True)
        self._container.setAcceptDrops(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def file_items(self) -> list[FileItem]:
        return [c.item for c in self._cards]

    def add_files(self, paths: list[Path]) -> None:
        """Add *paths* to the arrangement area, skipping duplicates."""
        existing = {c.item.path for c in self._cards}
        rejected: list[str] = []
        added = False
        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                rejected.append(path.name)
                continue
            if path in existing:
                continue
            existing.add(path)
            self._add_card(FileItem(path))
            added = True
        if rejected:
            self.unsupported_dropped.emit(rejected)
        if added:
            self.files_changed.emit()

    def remove_all(self) -> None:
        """Remove all cards."""
        for card in list(self._cards):
            self._remove_card(card)
        self.files_changed.emit()

    def is_empty(self) -> bool:
        return len(self._cards) == 0

    # ------------------------------------------------------------------
    # Card management
    # ------------------------------------------------------------------

    def _add_card(self, item: FileItem) -> FileCard:
        card = FileCard(item, self._container)
        card.remove_requested.connect(self._on_remove_requested)
        card.drag_started.connect(self._on_drag_started)

        # Insert before the trailing stretch
        stretch_index = self._cards_layout.count() - 1
        self._cards_layout.insertWidget(stretch_index, card)
        self._cards.append(card)
        self._update_hint_visibility()
        return card

    def _remove_card(self, card: FileCard) -> None:
        if card in self._cards:
            self._cards.remove(card)
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._update_hint_visibility()

    def _update_hint_visibility(self) -> None:
        self._drop_hint.setVisible(len(self._cards) == 0)

    def _on_remove_requested(self, card: FileCard) -> None:
        self._remove_card(card)
        self.files_changed.emit()

    def _on_drag_started(self, card: FileCard) -> None:
        self._dragged_card = card

    # ------------------------------------------------------------------
    # OS-level file drag-and-drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-filecardid"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._highlight_drop_position(event.position().toPoint())
        elif event.mimeData().hasFormat("application/x-filecardid"):
            event.acceptProposedAction()
            self._highlight_drop_position(event.position().toPoint())
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._clear_highlights()

    def dropEvent(self, event: QDropEvent) -> None:
        self._clear_highlights()
        mime = event.mimeData()

        if mime.hasUrls():
            # Files dropped from OS file manager
            paths = [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]
            self.add_files(paths)
            event.acceptProposedAction()

        elif mime.hasFormat("application/x-filecardid") and self._dragged_card:
            # Card being reordered
            drop_pos = event.position().toPoint()
            target_index = self._card_index_at(drop_pos)
            source_index = self._cards.index(self._dragged_card)

            if target_index != source_index and target_index >= 0:
                self._reorder(source_index, target_index)
                self.files_changed.emit()

            self._dragged_card = None
            event.acceptProposedAction()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Reorder helpers
    # ------------------------------------------------------------------

    def _card_index_at(self, pos: QPoint) -> int:
        """
        Return the index where a card should be inserted given a drop position
        in this widget's coordinate space.
        """
        # Map to container coordinates
        container_pos = self._container.mapFrom(self, pos)
        x = container_pos.x()

        # Find the card whose centre is closest
        best_idx = len(self._cards)
        for i, card in enumerate(self._cards):
            card_x = card.x() + CARD_WIDTH // 2
            if x < card_x:
                return i
        return best_idx

    def _reorder(self, from_idx: int, to_idx: int) -> None:
        card = self._cards.pop(from_idx)
        # Adjust target index after removal
        if to_idx > from_idx:
            to_idx -= 1
        self._cards.insert(to_idx, card)

        # Rebuild layout order
        for c in self._cards:
            self._cards_layout.removeWidget(c)
        stretch_index = self._cards_layout.count() - 1
        for i, c in enumerate(self._cards):
            self._cards_layout.insertWidget(stretch_index + i, c)

    def _highlight_drop_position(self, pos: QPoint) -> None:
        """Visually indicate which card is the current drop target."""
        self._clear_highlights()
        idx = self._card_index_at(pos)
        if 0 <= idx < len(self._cards):
            self._cards[idx].set_drop_target(True)

    def _clear_highlights(self) -> None:
        for card in self._cards:
            card.set_drop_target(False)
