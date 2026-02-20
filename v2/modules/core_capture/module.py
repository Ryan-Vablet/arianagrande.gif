from __future__ import annotations

import logging
from typing import Any

from src.core.base_module import BaseModule

logger = logging.getLogger(__name__)


class CoreCaptureModule(BaseModule):
    name = "Core Capture"
    key = "core_capture"
    version = "1.0.0"
    description = "Screen capture, live preview, calibration overlay"
    requires: list[str] = []
    optional: list[str] = []
    provides_services = ["monitor_info", "capture_running", "bounding_box"]
    hooks = ["capture_started", "capture_stopped"]

    def setup(self, core: Any) -> None:
        super().setup(core)
        self._worker: Any = None
        self._is_running = False
        self._preview_widget: Any = None
        self._btn_capture: Any = None
        self._capture_status: Any = None

        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())

        core.panels.register(
            id=f"{self.key}/preview",
            area="primary",
            factory=self._build_preview_widget,
            title="Live Preview",
            owner=self.key,
            order=0,
        )

        core.panels.register(
            id=f"{self.key}/controls",
            area="primary",
            factory=self._build_controls_widget,
            title="Capture Controls",
            owner=self.key,
            order=1,
        )

        core.settings.register(
            path="detection/capture_region",
            factory=self._build_capture_region_settings,
            title="Capture Region",
            owner=self.key,
            order=10,
        )

        core.settings.register(
            path="detection/slot_layout",
            factory=self._build_slot_layout_settings,
            title="Slot Layout",
            owner=self.key,
            order=20,
        )

        core.settings.register(
            path="detection/overlay",
            factory=self._build_overlay_settings,
            title="Overlay & Display",
            owner=self.key,
            order=30,
        )

        core.windows.register(
            id=f"{self.key}/overlay",
            factory=self._build_overlay,
            title="Capture Overlay",
            window_type="overlay",
            owner=self.key,
            default_visible=False,
            show_in_menu=True,
            remember_geometry=False,
        )

    def _default_config(self) -> dict:
        return {
            "monitor_index": 1,
            "polling_fps": 20,
            "bounding_box": {"top": 900, "left": 500, "width": 400, "height": 50},
            "slots": {"count": 10, "gap": 2, "padding": 3},
            "overlay": {"enabled": False, "show_active_screen_outline": False},
            "display": {"always_on_top": False},
        }

    def get_service(self, name: str) -> Any:
        if name == "capture_running":
            return self._is_running
        if name == "bounding_box":
            cfg = self.core.get_config(self.key)
            return cfg.get("bounding_box", {})
        if name == "monitor_info":
            return None
        return None

    def start_capture(self) -> None:
        if self._is_running:
            return
        from modules.core_capture.capture_worker import CaptureWorker

        module_manager = getattr(self.core, "_module_manager", None)
        if module_manager is None:
            logger.error("Cannot start capture: module_manager not set on core")
            return

        self._worker = CaptureWorker(self.core, module_manager)

        if self._preview_widget is not None:
            from PyQt6.QtCore import Qt
            self._worker.frame_captured.connect(
                self._preview_widget.update_preview, Qt.ConnectionType.QueuedConnection
            )

        self._worker.start()
        self._is_running = True
        self.core.emit(f"{self.key}.capture_started")

        cfg = self.core.get_config(self.key)
        if cfg.get("overlay", {}).get("enabled", False):
            self.core.windows.show(f"{self.key}/overlay")

    def stop_capture(self) -> None:
        if not self._is_running:
            return
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._is_running = False
        self.core.emit(f"{self.key}.capture_stopped")

    def toggle_capture(self) -> None:
        if self._is_running:
            self.stop_capture()
        else:
            self.start_capture()

    def teardown(self) -> None:
        self.stop_capture()

    # --- Widget builders ---

    def _build_preview_widget(self) -> Any:
        from modules.core_capture.preview_widget import PreviewWidget
        self._preview_widget = PreviewWidget()
        return self._preview_widget

    def _build_controls_widget(self) -> Any:
        from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self._btn_capture = QPushButton("▶ Start Capture")
        self._btn_capture.clicked.connect(self._on_capture_toggle)
        layout.addWidget(self._btn_capture)

        self._capture_status = QLabel("Stopped")
        self._capture_status.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self._capture_status)
        layout.addStretch()
        return w

    def _on_capture_toggle(self) -> None:
        self.toggle_capture()
        if self._is_running:
            self._btn_capture.setText("⏹ Stop Capture")
            self._capture_status.setText("Running")
            self._capture_status.setStyleSheet("color: #88ff88; font-size: 11px;")
        else:
            self._btn_capture.setText("▶ Start Capture")
            self._capture_status.setText("Stopped")
            self._capture_status.setStyleSheet("color: #999; font-size: 11px;")

    def _build_capture_region_settings(self) -> Any:
        from modules.core_capture.settings_widget import CaptureRegionSettings
        return CaptureRegionSettings(self._core_ref(), self.key)

    def _build_slot_layout_settings(self) -> Any:
        from modules.core_capture.settings_widget import SlotLayoutSettings
        return SlotLayoutSettings(self._core_ref(), self.key)

    def _build_overlay_settings(self) -> Any:
        from modules.core_capture.settings_widget import OverlayDisplaySettings
        return OverlayDisplaySettings(self._core_ref(), self.key)

    def _build_overlay(self) -> Any:
        from modules.core_capture.overlay import CaptureOverlay
        return CaptureOverlay(self._core_ref(), self.key)

    def _core_ref(self) -> Any:
        return self.core
