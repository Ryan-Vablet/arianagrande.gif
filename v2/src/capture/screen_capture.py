from __future__ import annotations

import logging
from typing import Optional

import mss
import numpy as np

from src.models.geometry import BoundingBox

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Captures a screen region using mss."""

    def __init__(self, monitor_index: int = 1) -> None:
        self._sct: Optional[mss.mss] = None
        self._monitor_index = monitor_index

    def start(self) -> None:
        self._sct = mss.mss()
        monitors = self._sct.monitors
        logger.info("Available monitors: %d (indices 1..%d)", len(monitors) - 1, len(monitors) - 1)
        if self._monitor_index >= len(monitors):
            logger.warning("Monitor %d not found, falling back to monitor 1", self._monitor_index)
            self._monitor_index = 1

    def stop(self) -> None:
        if self._sct:
            self._sct.close()
            self._sct = None

    @property
    def monitor_info(self) -> dict:
        if not self._sct:
            raise RuntimeError("Capture not started. Call start() first.")
        return self._sct.monitors[self._monitor_index]

    def grab_region(self, bbox: BoundingBox) -> np.ndarray:
        if not self._sct:
            raise RuntimeError("Capture not started. Call start() first.")

        monitor = self._sct.monitors[self._monitor_index]
        region = bbox.as_mss_region(
            monitor_offset_x=monitor["left"],
            monitor_offset_y=monitor["top"],
        )

        raw = self._sct.grab(region)
        frame = np.array(raw, dtype=np.uint8)
        return frame[:, :, :3]

    def list_monitors(self) -> list[dict]:
        if not self._sct:
            raise RuntimeError("Capture not started. Call start() first.")
        return self._sct.monitors[1:]
