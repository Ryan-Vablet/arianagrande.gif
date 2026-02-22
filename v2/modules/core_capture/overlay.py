from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from src.models import BoundingBox

logger = logging.getLogger(__name__)


class CaptureOverlay(QWidget):
    """Transparent overlay showing all registered capture regions."""

    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core = core
        self._key = module_key
        self._capture_active = False
        self._show_outline = False
        self._monitor_geometry = QRect(0, 0, 1920, 1080)
        self._error_regions: set[str] = set()

        self._setup_window()
        self._refresh_from_config()
        self._core.subscribe("config.changed", self._on_config_changed)
        self._core.subscribe("capture.region_error", self._on_region_error)
        self._core.subscribe("capture.region_frame", self._on_region_frame_ok)

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

    def _on_config_changed(self, namespace: str = "") -> None:
        if namespace == self._key:
            cfg = self._core.get_config(self._key)
            self._show_outline = cfg.get("overlay", {}).get("show_active_screen_outline", False)
        self.update()

    def _on_region_error(self, region_id: str = "", **_: Any) -> None:
        if region_id and region_id not in self._error_regions:
            self._error_regions.add(region_id)
            self.update()

    def _on_region_frame_ok(self, region_id: str = "", **_: Any) -> None:
        if region_id and region_id in self._error_regions:
            self._error_regions.discard(region_id)
            self.update()

    def set_capture_active(self, active: bool) -> None:
        self._capture_active = active
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._show_outline and self._capture_active:
            self._draw_screen_outline(painter)

        regions = self._core.capture_regions.get_all()
        for region in regions:
            bb_dict = self._core.capture_regions.get_bbox_dict(region.id)
            if not bb_dict:
                continue
            bbox = BoundingBox.from_dict(bb_dict)
            region_rect = QRect(bbox.left, bbox.top, bbox.width, bbox.height)
            is_error = region.id in self._error_regions

            if is_error:
                err_color = QColor("#CC3333")
                err_fill = QColor("#CC3333")
                err_fill.setAlpha(40)
                painter.setPen(QPen(err_color, 2, Qt.PenStyle.DashLine))
                painter.setBrush(err_fill)
                painter.drawRect(region_rect)

                painter.setPen(QColor("#FF6666"))
                font = QFont("monospace", 9)
                font.setBold(True)
                painter.setFont(font)
                text = f"✖ {region.label or region.id} — OUT OF BOUNDS"
                painter.drawText(
                    region_rect.adjusted(4, 2, -4, -2),
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )
            else:
                color = QColor(region.overlay_color)
                painter.setPen(QPen(color, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(region_rect)

                if region.label:
                    label_color = QColor(region.overlay_color)
                    label_color.setAlpha(200)
                    painter.setPen(label_color)
                    font = QFont("monospace", 8)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(
                        bbox.left + 4,
                        bbox.top - 4,
                        region.label,
                    )

                if region.overlay_draw is not None:
                    try:
                        region.overlay_draw(painter, region_rect)
                    except Exception as e:
                        logger.error(
                            "overlay_draw for region '%s' failed: %s",
                            region.id, e,
                        )

        painter.end()

    def _draw_screen_outline(self, painter: QPainter) -> None:
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        green = QColor("#00FF00")
        for inset, alpha in [(4, 35), (3, 60), (2, 100), (1, 160)]:
            green.setAlpha(alpha)
            painter.setPen(QPen(green, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(inset, inset, w - 1 - 2 * inset, h - 1 - 2 * inset)
        green.setAlpha(255)
        painter.setPen(QPen(green, 1))
        painter.drawRect(0, 0, w - 1, h - 1)
