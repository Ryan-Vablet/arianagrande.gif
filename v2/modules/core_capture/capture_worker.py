from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from src.models import BoundingBox

logger = logging.getLogger(__name__)


class CaptureWorker(QThread):
    """Capture loop: grab all registered regions, emit previews, distribute to modules."""

    region_frame_captured = pyqtSignal(str, QImage)

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

                    fps = max(1, min(120, int(new_cfg.get("polling_fps", 20))))
                    interval_ms = int(1000 / fps)

                    regions = self._core.capture_regions.get_all()
                    for region in regions:
                        bb_dict = self._core.capture_regions.get_bbox_dict(region.id)
                        if not bb_dict:
                            continue
                        bbox = BoundingBox.from_dict(bb_dict)
                        frame = self._capture.grab_region(bbox)

                        h, w, ch = frame.shape
                        rgb = frame[:, :, ::-1].copy()
                        qimg = QImage(
                            rgb.data, w, h, ch * w,
                            QImage.Format.Format_RGB888,
                        ).copy()
                        self.region_frame_captured.emit(region.id, qimg)

                        if region.callback is not None:
                            try:
                                region.callback(frame)
                            except Exception as e:
                                logger.error(
                                    "Region '%s' callback error: %s",
                                    region.id, e, exc_info=True,
                                )

                except Exception as e:
                    logger.error("Capture error: %s", e, exc_info=True)

                self.msleep(interval_ms)
        finally:
            if self._capture:
                self._capture.stop()

    def stop(self) -> None:
        self._running = False
        self.wait()
