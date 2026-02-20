from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SlotState(Enum):
    READY = "ready"
    ON_COOLDOWN = "on_cooldown"
    CASTING = "casting"
    CHANNELING = "channeling"
    LOCKED = "locked"
    GCD = "gcd"
    UNKNOWN = "unknown"


@dataclass
class SlotConfig:
    """Static pixel layout for one slot within the capture region."""
    index: int
    x_offset: int = 0
    y_offset: int = 0
    width: int = 40
    height: int = 40


@dataclass
class SlotSnapshot:
    """Analyzed state of one slot at a point in time."""
    index: int
    state: SlotState = SlotState.UNKNOWN
    darkened_fraction: float = 0.0
    changed_fraction: float = 0.0
    timestamp: float = 0.0

    @property
    def is_ready(self) -> bool:
        return self.state == SlotState.READY

    @property
    def is_on_cooldown(self) -> bool:
        return self.state == SlotState.ON_COOLDOWN

    @property
    def is_casting(self) -> bool:
        return self.state in (SlotState.CASTING, SlotState.CHANNELING)
