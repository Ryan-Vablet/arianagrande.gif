"""WoW cast bar detection via HSV color analysis.

Detects whether the WoW cast bar is active (gate) and how far along
the cast has progressed (0.0 .. 1.0) by scanning for the characteristic
yellow/orange fill of the bar.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CastBarState:
    """Snapshot of cast bar detection state."""

    active: bool = False
    progress: float = 0.0
    channeling: bool = False
    timestamp: float = 0.0


class CastBarAnalyzer:
    """HSV-based WoW cast bar gate + progress detection."""

    def __init__(self) -> None:
        self._hue_min: int = 15
        self._hue_max: int = 45
        self._sat_min: int = 80
        self._val_min: int = 120
        self._active_fraction: float = 0.15
        self._confirm_frames: int = 2

        self._progress_rect = {"x": 0.02, "y": 0.15, "w": 0.96, "h": 0.7}

        self._candidate_frames: int = 0
        self._was_active: bool = False
        self._last_progress: float = 0.0
        self._active_since: float | None = None

    def update_config(self, cfg: dict) -> None:
        self._hue_min = int(cfg.get("bar_color_hue_min", self._hue_min))
        self._hue_max = int(cfg.get("bar_color_hue_max", self._hue_max))
        self._sat_min = int(cfg.get("bar_saturation_min", self._sat_min))
        self._val_min = int(cfg.get("bar_brightness_min", self._val_min))
        self._active_fraction = float(cfg.get("active_pixel_fraction", self._active_fraction))
        self._confirm_frames = int(cfg.get("confirm_frames", self._confirm_frames))
        pr = cfg.get("progress_sub_region", self._progress_rect)
        if isinstance(pr, dict):
            self._progress_rect = pr

    def reset(self) -> None:
        self._candidate_frames = 0
        self._was_active = False
        self._last_progress = 0.0
        self._active_since = None

    def analyze(self, frame: np.ndarray) -> CastBarState:
        """Analyze a cast bar region frame (BGR numpy array).

        Returns a CastBarState with gate and progress information.
        """
        now = time.time()
        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return CastBarState(timestamp=now)

        pr = self._progress_rect
        px = int(pr.get("x", 0) * w)
        py = int(pr.get("y", 0) * h)
        pw = int(pr.get("w", 1) * w)
        ph = int(pr.get("h", 1) * h)
        px = max(0, min(px, w - 1))
        py = max(0, min(py, h - 1))
        pw = max(1, min(pw, w - px))
        ph = max(1, min(ph, h - py))

        roi = frame[py : py + ph, px : px + pw]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        mask = self._build_mask(hsv)

        total_pixels = mask.size
        active_pixels = int(np.count_nonzero(mask))
        fraction = active_pixels / total_pixels if total_pixels > 0 else 0.0

        is_bar_present = fraction >= self._active_fraction

        if is_bar_present:
            self._candidate_frames += 1
        else:
            self._candidate_frames = 0

        confirmed = self._candidate_frames >= max(1, self._confirm_frames)

        progress = 0.0
        channeling = False
        if confirmed:
            progress = self._measure_progress(mask)
            if self._active_since is None:
                self._active_since = now

            if self._was_active and progress < self._last_progress - 0.05:
                channeling = True

        if not confirmed:
            self._active_since = None

        self._was_active = confirmed
        self._last_progress = progress if confirmed else 0.0

        return CastBarState(
            active=confirmed,
            progress=progress,
            channeling=channeling,
            timestamp=now,
        )

    def _build_mask(self, hsv: np.ndarray) -> np.ndarray:
        h_channel = hsv[:, :, 0]
        s_channel = hsv[:, :, 1]
        v_channel = hsv[:, :, 2]

        if self._hue_min <= self._hue_max:
            hue_ok = (h_channel >= self._hue_min) & (h_channel <= self._hue_max)
        else:
            hue_ok = (h_channel >= self._hue_min) | (h_channel <= self._hue_max)

        return (
            hue_ok
            & (s_channel >= self._sat_min)
            & (v_channel >= self._val_min)
        ).astype(np.uint8)

    @staticmethod
    def _measure_progress(mask: np.ndarray) -> float:
        """Measure how far the bar is filled left-to-right.

        Scans columns and finds the rightmost column with active pixels.
        Progress = rightmost_active_col / total_columns.
        """
        if mask.size == 0:
            return 0.0
        col_sums = mask.sum(axis=0)
        active_cols = np.where(col_sums > 0)[0]
        if len(active_cols) == 0:
            return 0.0
        rightmost = int(active_cols[-1])
        return (rightmost + 1) / mask.shape[1]

    @property
    def progress_rect(self) -> dict:
        return dict(self._progress_rect)
