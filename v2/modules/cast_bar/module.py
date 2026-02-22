"""Cast bar detection module — WoW cast bar visual detection via separate capture region."""
from __future__ import annotations

import logging
from abc import ABCMeta
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen

from src.core.base_module import BaseModule

logger = logging.getLogger(__name__)


class _CombinedMeta(type(QObject), ABCMeta):
    pass


class CastBarModule(QObject, BaseModule, metaclass=_CombinedMeta):
    """Detects WoW cast bar activity from a dedicated capture region.

    Provides cast_gate_active (bool) and cast_progress (0..1) services
    consumed by cast_detection and automation modules.
    """

    name = "Cast Bar"
    key = "cast_bar"
    version = "1.0.0"
    description = "Detects WoW cast bar via a separate screen capture region"
    requires: list[str] = ["core_capture"]
    optional: list[str] = []
    provides_services = ["cast_gate_active", "cast_progress", "cast_bar_state"]
    hooks = ["cast_bar_updated"]

    cast_bar_updated_signal = pyqtSignal(object)

    def __init__(self) -> None:
        QObject.__init__(self)
        BaseModule.__init__(self)
        self._analyzer: Any = None
        self._latest_state: Any = None

    def setup(self, core: Any) -> None:
        super().setup(core)
        from modules.cast_bar.cast_bar_analyzer import CastBarAnalyzer

        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())

        self._analyzer = CastBarAnalyzer()
        self._sync_config()

        core.capture_regions.register(
            id="cast_bar",
            owner=self.key,
            config_namespace=self.key,
            config_key="capture_region",
            default_bbox={"top": 700, "left": 640, "width": 300, "height": 40},
            overlay_color="#FF8800",
            label="Cast Bar",
            callback=self._on_cast_bar_frame,
            overlay_draw=self._draw_cast_bar_overlay,
            order=10,
        )

        core.settings.register(
            path="calibrate/cast_bar_calibration",
            factory=self._build_calibration_settings,
            title="Cast Bar Calibration",
            owner=self.key,
            order=50,
        )

        core.settings.register(
            path="detection/cast_bar",
            factory=self._build_settings,
            title="Cast Bar",
            owner=self.key,
            order=36,
        )

        core.subscribe("config.changed", self._on_config_changed)

    def _default_config(self) -> dict:
        return {
            "enabled": True,
            "capture_region": {"top": 700, "left": 640, "width": 300, "height": 40},
            "bar_color_hue_min": 15,
            "bar_color_hue_max": 45,
            "bar_saturation_min": 80,
            "bar_brightness_min": 120,
            "active_pixel_fraction": 0.15,
            "confirm_frames": 2,
            "progress_sub_region": {"x": 0.02, "y": 0.15, "w": 0.96, "h": 0.7},
        }

    def _on_cast_bar_frame(self, frame: np.ndarray) -> None:
        if not self._analyzer:
            return
        cfg = self.core.get_config(self.key)
        if not cfg.get("enabled", True):
            return

        state = self._analyzer.analyze(frame)
        self._latest_state = state
        self.cast_bar_updated_signal.emit(state)
        self.core.emit(f"{self.key}.cast_bar_updated", state=state)

    def get_service(self, name: str) -> Any:
        if name == "cast_gate_active":
            if self._latest_state is None:
                return None
            return self._latest_state.active
        if name == "cast_progress":
            if self._latest_state is None:
                return 0.0
            return self._latest_state.progress
        if name == "cast_bar_state":
            return self._latest_state
        return None

    def _on_config_changed(self, namespace: str = "") -> None:
        if namespace == self.key:
            self._sync_config()

    def _sync_config(self) -> None:
        if not self._analyzer or not self.core:
            return
        cfg = self.core.get_config(self.key)
        self._analyzer.update_config(cfg)

    def _draw_cast_bar_overlay(self, painter: QPainter, region_rect: QRect) -> None:
        """Draw progress sub-region outline and live progress fill."""
        cfg = self.core.get_config(self.key)
        pr = cfg.get("progress_sub_region", {"x": 0.02, "y": 0.15, "w": 0.96, "h": 0.7})

        rw = region_rect.width()
        rh = region_rect.height()
        rx = region_rect.x()
        ry = region_rect.y()

        sub_x = rx + int(pr.get("x", 0) * rw)
        sub_y = ry + int(pr.get("y", 0) * rh)
        sub_w = int(pr.get("w", 1) * rw)
        sub_h = int(pr.get("h", 1) * rh)
        sub_rect = QRect(sub_x, sub_y, sub_w, sub_h)

        painter.setPen(QPen(QColor("#FFAA00"), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(sub_rect)

        if self._latest_state and self._latest_state.active:
            progress = max(0.0, min(1.0, self._latest_state.progress))
            fill_w = int(sub_w * progress)
            if fill_w > 0:
                fill_color = QColor("#FFAA00")
                fill_color.setAlpha(80)
                painter.fillRect(QRect(sub_x, sub_y, fill_w, sub_h), fill_color)

    def teardown(self) -> None:
        pass

    def _build_calibration_settings(self) -> Any:
        from modules.cast_bar.settings_widget import CastBarCalibrationSettings
        return CastBarCalibrationSettings(self.core, self.key, self)

    def _build_settings(self) -> Any:
        from modules.cast_bar.settings_widget import CastBarSettings
        return CastBarSettings(self.core, self.key, self)
