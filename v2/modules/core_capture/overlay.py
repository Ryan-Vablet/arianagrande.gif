from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from src.models import BoundingBox

logger = logging.getLogger(__name__)


class CaptureOverlay(QWidget):
    """Transparent overlay showing capture region and slot layout."""

    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core = core
        self._key = module_key
        self._capture_active = False

        self._bbox = BoundingBox()
        self._slot_count = 10
        self._slot_gap = 2
        self._slot_padding = 3
        self._show_outline = False
        self._monitor_geometry = QRect(0, 0, 1920, 1080)

        self._setup_window()
        self._refresh_from_config()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def _refresh_from_config(self) -> None:
        cfg = self._core.get_config(self._key)
        bb = cfg.get("bounding_box", {})
        self._bbox = BoundingBox.from_dict(bb)

        slots = cfg.get("slots", {})
        self._slot_count = int(slots.get("count", 10))
        self._slot_gap = int(slots.get("gap", 2))
        self._slot_padding = int(slots.get("padding", 3))
        self._show_outline = cfg.get("overlay", {}).get("show_active_screen_outline", False)

        self._update_monitor_geometry(cfg)
        self.update()

    def _update_monitor_geometry(self, cfg: dict) -> None:
        monitor_index = int(cfg.get("monitor_index", 1))
        try:
            from src.capture.screen_capture import ScreenCapture
            sc = ScreenCapture(monitor_index=monitor_index)
            sc.start()
            info = sc.monitor_info
            sc.stop()
            self._monitor_geometry = QRect(
                info["left"], info["top"], info["width"], info["height"]
            )
        except Exception as e:
            logger.warning("Could not get monitor geometry: %s", e)

        self.setGeometry(self._monitor_geometry)

    def set_capture_active(self, active: bool) -> None:
        self._capture_active = active
        self.update()

    def _slot_analyzed_rects(self) -> list[QRect]:
        total_width = self._bbox.width
        total_height = self._bbox.height
        gap = self._slot_gap
        count = self._slot_count
        padding = self._slot_padding

        slot_w = max(1, (total_width - (count - 1) * gap) // count)
        slot_h = total_height

        rects: list[QRect] = []
        for i in range(count):
            x = i * (slot_w + gap)
            inner_w = max(0, slot_w - 2 * padding)
            inner_h = max(0, slot_h - 2 * padding)
            rects.append(QRect(
                self._bbox.left + x + padding,
                self._bbox.top + padding,
                inner_w,
                inner_h,
            ))
        return rects

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._show_outline and self._capture_active:
            w, h = self.width(), self.height()
            if w > 0 and h > 0:
                green = QColor("#00FF00")
                for inset, alpha in [(4, 35), (3, 60), (2, 100), (1, 160)]:
                    green.setAlpha(alpha)
                    painter.setPen(QPen(green, 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(inset, inset, w - 1 - 2 * inset, h - 1 - 2 * inset)
                green.setAlpha(255)
                painter.setPen(QPen(green, 1))
                painter.drawRect(0, 0, w - 1, h - 1)

        # Green bounding box
        pen = QPen(QColor("#00FF00"), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(
            self._bbox.left,
            self._bbox.top,
            self._bbox.width,
            self._bbox.height,
        )

        # Magenta slot outlines
        slot_pen = QPen(QColor("#FF00FF"), 1)
        painter.setPen(slot_pen)
        for rect in self._slot_analyzed_rects():
            if rect.width() > 0 and rect.height() > 0:
                painter.drawRect(rect)

        painter.end()
