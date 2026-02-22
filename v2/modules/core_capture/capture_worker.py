from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from src.models import BoundingBox

logger = logging.getLogger(__name__)


class CaptureWorker(QThread):
    """Capture loop: grab frame, emit preview, distribute to modules."""

    frame_captured = pyqtSignal(QImage)

    def __init__(self, core: Any, module_manager: Any) -> None:
        super().__init__()
        self._core = core
        self._module_manager = module_manager
        self._running = False
        self._capture: Any = None

    def run(self) -> None:
        from src.capture.screen_capture import ScreenCapture

        self._running = True
        cfg = self._core.get_config("core_capture")
        monitor_index = int(cfg.get("monitor_index", 1))

        self._capture = ScreenCapture(monitor_index=monitor_index)
        self._capture.start()

        fps = max(1, min(120, int(cfg.get("polling_fps", 20))))
        interval_ms = int(1000 / fps)

        try:
            while self._running:
                try:
                    new_cfg = self._core.get_config("core_capture")
                    new_monitor = int(new_cfg.get("monitor_index", 1))
                    if new_monitor != monitor_index:
                        monitor_index = new_monitor
                        self._capture.stop()
                        self._capture = ScreenCapture(monitor_index=monitor_index)
                        self._capture.start()

                    new_fps = max(1, min(120, int(new_cfg.get("polling_fps", 20))))
                    if new_fps != fps:
                        fps = new_fps
                        interval_ms = int(1000 / fps)

                    bb_dict = new_cfg.get("bounding_box", {})
                    bbox = BoundingBox.from_dict(bb_dict)
                    frame = self._capture.grab_region(bbox)

                    h, w, ch = frame.shape
                    rgb = frame[:, :, ::-1].copy()
                    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                    self.frame_captured.emit(qimg)

                    self._module_manager.process_frame(frame)

                except Exception as e:
                    logger.error("Capture error: %s", e, exc_info=True)

                self.msleep(interval_ms)
        finally:
            if self._capture:
                self._capture.stop()

    def stop(self) -> None:
        self._running = False
        self.wait()
