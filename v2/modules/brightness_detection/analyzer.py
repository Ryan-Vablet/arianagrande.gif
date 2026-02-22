"""Brightness-based per-slot cooldown detection.

Ported from v1 SlotAnalyzer — brightness detection only.
Glow, buff, and cast-bar ROI detection belong to future modules.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from src.models import SlotState, SlotConfig, SlotSnapshot

logger = logging.getLogger(__name__)


@dataclass
class _SlotRuntime:
    """Per-slot temporal memory for state transitions."""
    state: SlotState = SlotState.UNKNOWN
    cooldown_candidate_started_at: Optional[float] = None
    last_darkened_fraction: float = 0.0


class SlotAnalyzer:
    """Analyzes per-slot brightness to detect cooldown states."""

    def __init__(self) -> None:
        self._slot_configs: list[SlotConfig] = []
        self._baselines: dict[int, np.ndarray] = {}
        self._runtime: dict[int, _SlotRuntime] = {}
        self._frame_count: int = 0

        # Layout (from core_capture config)
        self._slot_count: int = 10
        self._slot_gap: int = 2
        self._slot_padding: int = 3
        self._bbox_width: int = 400
        self._bbox_height: int = 50

        # Brightness thresholds
        self._darken_threshold: int = 40
        self._trigger_fraction: float = 0.30
        self._change_fraction: float = 0.30
        self._change_ignore_slots: set[int] = set()
        self._detection_region: str = "top_left"
        self._detection_region_overrides: dict[int, str] = {}
        self._cooldown_min_ms: int = 2000
        self._release_factor: float = 0.5

        self._recompute_layout()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def update_config(self, cfg: dict) -> None:
        """Update analyser from a merged config dict.

        Clears baselines and runtime state when slot layout changes.
        """
        layout_changed = (
            cfg.get("slot_count", self._slot_count) != self._slot_count
            or cfg.get("slot_gap", self._slot_gap) != self._slot_gap
            or cfg.get("slot_padding", self._slot_padding) != self._slot_padding
            or cfg.get("bbox_width", self._bbox_width) != self._bbox_width
            or cfg.get("bbox_height", self._bbox_height) != self._bbox_height
        )

        self._slot_count = int(cfg.get("slot_count", self._slot_count))
        self._slot_gap = int(cfg.get("slot_gap", self._slot_gap))
        self._slot_padding = int(cfg.get("slot_padding", self._slot_padding))
        self._bbox_width = int(cfg.get("bbox_width", self._bbox_width))
        self._bbox_height = int(cfg.get("bbox_height", self._bbox_height))
        self._darken_threshold = int(cfg.get("darken_threshold", self._darken_threshold))
        self._trigger_fraction = float(cfg.get("trigger_fraction", self._trigger_fraction))
        self._change_fraction = float(cfg.get("change_fraction", self._change_fraction))
        self._change_ignore_slots = set(cfg.get("change_ignore_slots", []))
        self._detection_region = str(cfg.get("detection_region", self._detection_region))
        self._detection_region_overrides = dict(cfg.get("detection_region_overrides", {}))
        self._cooldown_min_ms = int(cfg.get("cooldown_min_ms", self._cooldown_min_ms))

        self._recompute_layout()
        if layout_changed:
            self._baselines.clear()
            self._runtime = {i: _SlotRuntime() for i in range(self._slot_count)}
            logger.info("Layout changed — baselines cleared, recalibrate required")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _recompute_layout(self) -> None:
        """Calculate pixel regions for each slot (port from v1)."""
        count = self._slot_count
        gap = self._slot_gap
        total_w = self._bbox_width
        total_h = self._bbox_height

        slot_w = max(1, (total_w - (count - 1) * gap) // count)
        slot_h = total_h

        self._slot_configs = []
        for i in range(count):
            x = i * (slot_w + gap)
            self._slot_configs.append(
                SlotConfig(index=i, x_offset=x, y_offset=0, width=slot_w, height=slot_h)
            )
            self._runtime.setdefault(i, _SlotRuntime())
        self._runtime = {i: self._runtime.get(i, _SlotRuntime()) for i in range(count)}

    @property
    def slot_configs(self) -> list[SlotConfig]:
        return list(self._slot_configs)

    # ------------------------------------------------------------------
    # Cropping & brightness
    # ------------------------------------------------------------------

    def crop_slot(self, frame: np.ndarray, slot: SlotConfig) -> np.ndarray:
        """Extract a single slot's padded image from frame."""
        if frame is None or frame.size == 0:
            return np.empty((0, 0, 3), dtype=np.uint8)
        pad = self._slot_padding
        x1 = slot.x_offset + pad
        y1 = slot.y_offset + pad
        w = max(1, slot.width - 2 * pad)
        h = max(1, slot.height - 2 * pad)
        x2 = min(frame.shape[1], x1 + w)
        y2 = min(frame.shape[0], y1 + h)
        return frame[y1:y2, x1:x2]

    @staticmethod
    def _get_brightness_channel(bgr_crop: np.ndarray) -> np.ndarray:
        """BGR → grayscale uint8 array."""
        if bgr_crop is None or bgr_crop.size == 0:
            return np.empty((0, 0), dtype=np.uint8)
        return cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY)

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def calibrate_baselines(self, frame: np.ndarray) -> None:
        """Calibrate all slot baselines from a single frame."""
        for slot_cfg in self._slot_configs:
            slot_img = self.crop_slot(frame, slot_cfg)
            gray = self._get_brightness_channel(slot_img)
            if gray.size == 0:
                logger.warning("Skipping baseline for slot %d: empty crop", slot_cfg.index)
                continue
            self._baselines[slot_cfg.index] = gray.copy()
            self._runtime[slot_cfg.index] = _SlotRuntime()
        logger.info("Calibrated brightness baselines for %d slots", len(self._baselines))

    def calibrate_single_slot(self, frame: np.ndarray, slot_index: int) -> None:
        """Recalibrate one slot's baseline."""
        if slot_index < 0 or slot_index >= len(self._slot_configs):
            logger.warning("calibrate_single_slot: invalid slot_index %d", slot_index)
            return
        slot_cfg = self._slot_configs[slot_index]
        slot_img = self.crop_slot(frame, slot_cfg)
        gray = self._get_brightness_channel(slot_img)
        if gray.size == 0:
            logger.warning("calibrate_single_slot: empty crop for slot %d", slot_index)
            return
        self._baselines[slot_index] = gray.copy()
        self._runtime[slot_index] = _SlotRuntime()
        logger.info("Calibrated baseline for slot %d", slot_index)

    def get_baselines(self) -> dict[int, np.ndarray]:
        return {k: v.copy() for k, v in self._baselines.items()}

    def set_baselines(self, baselines: dict[int, np.ndarray]) -> None:
        self._baselines = {k: v.copy() for k, v in baselines.items()}
        logger.info("Loaded %d slot baselines", len(self._baselines))

    @property
    def has_baselines(self) -> bool:
        return len(self._baselines) > 0

    # ------------------------------------------------------------------
    # Frame analysis
    # ------------------------------------------------------------------

    def analyze_frame(self, frame: np.ndarray) -> list[SlotSnapshot]:
        """Analyze all slots in a frame and return per-slot snapshots."""
        now = time.time()
        snapshots: list[SlotSnapshot] = []
        thresh = self._darken_threshold
        frac_thresh = self._trigger_fraction
        change_frac_thresh = self._change_fraction
        cooldown_min_sec = max(0.0, self._cooldown_min_ms / 1000.0)

        for slot_cfg in self._slot_configs:
            slot_img = self.crop_slot(frame, slot_cfg)
            baseline_bright = self._baselines.get(slot_cfg.index)

            region_mode = self._detection_region_overrides.get(
                slot_cfg.index, self._detection_region,
            )

            if region_mode == "top_left" and baseline_bright is not None:
                h, w = slot_img.shape[:2]
                slot_detect = slot_img[: max(1, h // 2), : max(1, w // 2)]
                baseline_detect = baseline_bright[: max(1, h // 2), : max(1, w // 2)]
                current_bright = self._get_brightness_channel(slot_detect)
                baseline_for_frac = baseline_detect
            else:
                current_bright = self._get_brightness_channel(slot_img)
                baseline_for_frac = baseline_bright

            if (
                current_bright.size == 0
                or baseline_for_frac is None
                or baseline_for_frac.shape != current_bright.shape
            ):
                snapshots.append(SlotSnapshot(
                    index=slot_cfg.index, state=SlotState.UNKNOWN, timestamp=now,
                ))
                continue

            drop = baseline_for_frac.astype(np.int16) - current_bright.astype(np.int16)
            total = current_bright.size
            darkened_fraction = float(np.sum(drop > thresh) / total) if total else 0.0

            abs_delta = np.abs(drop)
            changed_fraction = float(np.sum(abs_delta > thresh) / total) if total else 0.0

            ignore_change = slot_cfg.index in self._change_ignore_slots
            raw_dark_cd = darkened_fraction >= frac_thresh
            raw_changed_cd = (not ignore_change) and (changed_fraction >= change_frac_thresh)
            raw_cooldown = raw_dark_cd or raw_changed_cd

            # Hysteresis
            runtime = self._runtime.setdefault(slot_cfg.index, _SlotRuntime())
            if runtime.state == SlotState.ON_COOLDOWN:
                dark_release = frac_thresh * self._release_factor
                change_release = change_frac_thresh * self._release_factor
                hold_dark = darkened_fraction >= dark_release
                hold_change = (not ignore_change) and (changed_fraction >= change_release)
                raw_cooldown = raw_cooldown or hold_dark or hold_change

            # Cooldown min duration → GCD
            cooldown_pending = False
            if raw_cooldown:
                if runtime.cooldown_candidate_started_at is None:
                    runtime.cooldown_candidate_started_at = now
                if (
                    runtime.state != SlotState.ON_COOLDOWN
                    and cooldown_min_sec > 0.0
                    and (now - runtime.cooldown_candidate_started_at) < cooldown_min_sec
                ):
                    cooldown_pending = True
            else:
                runtime.cooldown_candidate_started_at = None

            if raw_cooldown and not cooldown_pending:
                state = SlotState.ON_COOLDOWN
            elif cooldown_pending:
                state = SlotState.GCD
            else:
                state = SlotState.READY

            runtime.state = state
            runtime.last_darkened_fraction = darkened_fraction

            snapshots.append(SlotSnapshot(
                index=slot_cfg.index,
                state=state,
                darkened_fraction=darkened_fraction,
                changed_fraction=changed_fraction,
                timestamp=now,
            ))

        self._frame_count += 1
        return snapshots
