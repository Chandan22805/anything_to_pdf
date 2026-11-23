"""
FileCard widget — represents a single file in the horizontal arrangement area.

Each card shows:
 - A thumbnail (image preview or PDF icon)
 - The filename (truncated if necessary)
 - A remove (×) button
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QDrag,
    QFont,
    QFontMetrics,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .pdf_engine import FileItem
from .thumbnails import THUMB_SIZE, make_thumbnail

logger = logging.getLogger(__name__)

CARD_WIDTH = 160
CARD_HEIGHT = 210


class FileCard(QFrame):
    """A draggable card representing one file in the arrange area."""

    remove_requested = Signal(object)   # emits self
    drag_started = Signal(object)       # emits self

    def __init__(self, item: FileItem, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self._drag_start: QPoint | None = None
        self._is_drag_target = False

        self._setup_ui()
        self._load_thumbnail()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self._update_style(highlighted=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(4)

        # Remove button (top-right)
        btn_row_widget = QWidget()
        from PySide6.QtWidgets import QHBoxLayout
        btn_row = QHBoxLayout(btn_row_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        self._remove_btn = QPushButton("✕")
        self._remove_btn.setFixedSize(22, 22)
        self._remove_btn.setToolTip("Remove this file")
        self._remove_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._remove_btn.setStyleSheet(
            """
            QPushButton {
                background: #E53935;
                color: white;
                border: none;
                border-radius: 11px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #C62828; }
            QPushButton:pressed { background: #B71C1C; }
            """
        )
        self._remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        btn_row.addWidget(self._remove_btn)
        layout.addWidget(btn_row_widget)

        # Thumbnail
        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setStyleSheet("border: 1px solid #E0E0E0; border-radius: 4px; background: #FAFAFA;")
        layout.addWidget(self._thumb_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Filename label
        self._name_label = QLabel()
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setWordWrap(False)
        self._name_label.setFixedWidth(CARD_WIDTH - 16)
        font = QFont()
        font.setPointSize(9)
        self._name_label.setFont(font)
        self._name_label.setStyleSheet("color: #333333;")

        # Elide filename to fit
        fm = QFontMetrics(font)
        elided = fm.elidedText(self.item.display_name, Qt.TextElideMode.ElideMiddle, CARD_WIDTH - 16)
        self._name_label.setText(elided)
        self._name_label.setToolTip(self.item.display_name)
        layout.addWidget(self._name_label)

    def _load_thumbnail(self) -> None:
        pixmap = make_thumbnail(self.item.path, self.item.is_pdf)
        self._thumb_label.setPixmap(
            pixmap.scaled(THUMB_SIZE, THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    # ------------------------------------------------------------------
    # Styling helpers
    # ------------------------------------------------------------------

    def _update_style(self, highlighted: bool) -> None:
        if highlighted:
            self.setStyleSheet(
                """
                FileCard {
                    background: #E3F2FD;
                    border: 2px solid #1976D2;
                    border-radius: 10px;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                FileCard {
                    background: #FFFFFF;
                    border: 1px solid #DDDDDD;
                    border-radius: 10px;
                }
                FileCard:hover {
                    border: 1px solid #90CAF9;
                    background: #F8FBFF;
                }
                """
            )

    def set_drop_target(self, active: bool) -> None:
        self._is_drag_target = active
        self._update_style(active)

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta = event.pos() - self._drag_start
            if delta.manhattanLength() > 10:
                self._start_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def _start_drag(self) -> None:
        """Initiate a Qt drag operation for this card."""
        self.drag_started.emit(self)
        drag = QDrag(self)
        mime = QMimeData()
        # Store a reference via a custom format using the card's id
        mime.setData("application/x-filecardid", str(id(self)).encode())
        drag.setMimeData(mime)

        # Render the card as the drag pixmap (semi-transparent)
        pixmap = self.grab()
        from PySide6.QtGui import QPainter as _P
        result = QPixmap(pixmap.size())
        result.fill(Qt.GlobalColor.transparent)
        p = _P(result)
        p.setOpacity(0.75)
        p.drawPixmap(0, 0, pixmap)
        p.end()
        drag.setPixmap(result)
        drag.setHotSpot(QPoint(CARD_WIDTH // 2, CARD_HEIGHT // 2))

        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        drag.exec(Qt.DropAction.MoveAction)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
