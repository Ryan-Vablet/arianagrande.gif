from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy

PREVIEW_PADDING = 12


class PreviewWidget(QLabel):
    """Displays the latest captured frame. Updated via QueuedConnection from capture thread."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setText("No capture running")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(300, 42)
        self.setStyleSheet(
            "background: #111; border-radius: 3px; color: #666; font-size: 11px;"
        )
        self.setScaledContents(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def update_preview(self, qimg: QImage) -> None:
        if qimg.isNull():
            return
        pixmap = QPixmap.fromImage(qimg)
        max_w = max(50, self.width() - 2 * PREVIEW_PADDING)
        max_h = max(20, self.height() - 2 * PREVIEW_PADDING)
        scaled = pixmap.scaled(
            max_w, max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setText("")
        self.setPixmap(scaled)
