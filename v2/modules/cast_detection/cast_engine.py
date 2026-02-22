"""Cast detection state machine — post-processes brightness slot states.

Receives per-slot brightness data (darkened_fraction) from brightness_detection
and determines if slots are in CASTING or CHANNELING state based on temporal
analysis of intermediate darkened fractions.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from src.models import SlotState

logger = logging.getLogger(__name__)


@dataclass
class _CastRuntime:
    """Per-slot temporal memory for cast state transitions."""
    state: SlotState = SlotState.READY
    cast_candidate_frames: int = 0
    cast_started_at: Optional[float] = None
    cast_ends_at: Optional[float] = None
    last_cast_start_at: Optional[float] = None
    last_cast_success_at: Optional[float] = None


class CastEngine:
    """Detects CASTING/CHANNELING by analyzing intermediate darkened fractions."""

    def __init__(self) -> None:
        self._runtime: dict[int, _CastRuntime] = {}

        self._enabled: bool = True
        self._min_fraction: float = 0.05
        self._max_fraction: float = 0.22
        self._confirm_frames: int = 2
        self._min_ms: int = 150
        self._max_ms: int = 3000
        self._cancel_grace_ms: int = 120
        self._channeling_enabled: bool = True

    def update_config(self, cfg: dict) -> None:
        self._enabled = bool(cfg.get("cast_detection_enabled", True))
        self._min_fraction = float(cfg.get("cast_min_fraction", self._min_fraction))
        self._max_fraction = float(cfg.get("cast_max_fraction", self._max_fraction))
        self._confirm_frames = int(cfg.get("cast_confirm_frames", self._confirm_frames))
        self._min_ms = int(cfg.get("cast_min_ms", self._min_ms))
        self._max_ms = int(cfg.get("cast_max_ms", self._max_ms))
        self._cancel_grace_ms = int(cfg.get("cast_cancel_grace_ms", self._cancel_grace_ms))
        self._channeling_enabled = bool(cfg.get("channeling_enabled", True))

    def reset(self) -> None:
        self._runtime.clear()

    def process_states(
        self,
        raw_states: list[dict],
        cast_gate_active: bool = True,
    ) -> list[dict]:
        """Post-process brightness states with cast detection.

        Takes the raw state dicts emitted by brightness_detection and returns
        a new list with CASTING/CHANNELING states overlaid where applicable.
        """
        if not self._enabled:
            return raw_states

        now = time.time()
        result: list[dict] = []

        for sd in raw_states:
            idx = sd.get("index", -1)
            raw_state = sd.get("state", "unknown")
            darkened_fraction = sd.get("darkened_fraction", 0.0)

            new_state = self._determine_cast_state(
                idx, raw_state, darkened_fraction, now, cast_gate_active,
            )

            entry = dict(sd)
            entry["state"] = new_state
            result.append(entry)

        return result

    def _determine_cast_state(
        self,
        slot_index: int,
        raw_state: str,
        darkened_fraction: float,
        now: float,
        cast_gate_active: bool,
    ) -> str:
        """State machine for one slot's cast detection."""
        runtime = self._runtime.setdefault(slot_index, _CastRuntime())

        min_frac = self._min_fraction
        max_frac = self._max_fraction
        confirm_frames = max(1, self._confirm_frames)
        cast_min_sec = max(0.05, self._min_ms / 1000.0)
        cast_max_sec = max(cast_min_sec, self._max_ms / 1000.0)
        cancel_grace_sec = max(0.0, self._cancel_grace_ms / 1000.0)

        is_on_cooldown = raw_state in ("on_cooldown", "gcd")
        cast_candidate = min_frac <= darkened_fraction < max_frac

        # Cooldown overrides any cast state
        if is_on_cooldown:
            if runtime.cast_started_at is not None:
                runtime.last_cast_success_at = now
            runtime.cast_candidate_frames = 0
            runtime.cast_started_at = None
            runtime.cast_ends_at = None
            runtime.state = SlotState.READY
            return raw_state

        # Currently casting/channeling
        if runtime.state in (SlotState.CASTING, SlotState.CHANNELING):
            cast_started_at = runtime.cast_started_at or now
            elapsed = now - cast_started_at

            if cast_candidate:
                if (
                    self._channeling_enabled
                    and runtime.state == SlotState.CASTING
                    and elapsed >= cast_max_sec
                ):
                    runtime.state = SlotState.CHANNELING
                    runtime.cast_ends_at = None
                return runtime.state.value

            if elapsed < (cast_min_sec + cancel_grace_sec):
                return runtime.state.value

            # Cast ended
            runtime.state = SlotState.READY
            runtime.cast_started_at = None
            runtime.cast_ends_at = None
            runtime.cast_candidate_frames = 0
            return raw_state

        # Potential new cast
        if cast_candidate:
            if not cast_gate_active:
                runtime.cast_candidate_frames = 0
                runtime.state = SlotState.READY
                runtime.cast_started_at = None
                runtime.cast_ends_at = None
                return raw_state

            runtime.cast_candidate_frames += 1
            if runtime.cast_candidate_frames >= confirm_frames:
                runtime.state = SlotState.CASTING
                runtime.cast_started_at = now
                runtime.last_cast_start_at = now
                runtime.cast_ends_at = now + cast_max_sec
                return SlotState.CASTING.value

            return raw_state

        # Default: reset cast tracking, pass through
        runtime.cast_candidate_frames = 0
        runtime.state = SlotState.READY
        runtime.cast_started_at = None
        runtime.cast_ends_at = None
        return raw_state
