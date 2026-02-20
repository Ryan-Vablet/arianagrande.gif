"""Tests for SlotState, SlotConfig, SlotSnapshot."""
from src.models.slot import SlotState, SlotConfig, SlotSnapshot


def test_slot_state_values():
    assert SlotState.READY.value == "ready"
    assert SlotState.ON_COOLDOWN.value == "on_cooldown"
    assert SlotState.CASTING.value == "casting"
    assert SlotState.CHANNELING.value == "channeling"
    assert SlotState.LOCKED.value == "locked"
    assert SlotState.GCD.value == "gcd"
    assert SlotState.UNKNOWN.value == "unknown"


def test_slot_config_defaults():
    cfg = SlotConfig(index=0)
    assert cfg.index == 0
    assert cfg.x_offset == 0
    assert cfg.y_offset == 0
    assert cfg.width == 40
    assert cfg.height == 40


def test_slot_config_custom():
    cfg = SlotConfig(index=3, x_offset=120, y_offset=5, width=36, height=50)
    assert cfg.index == 3
    assert cfg.x_offset == 120
    assert cfg.width == 36


def test_snapshot_default_is_unknown():
    snap = SlotSnapshot(index=0)
    assert snap.state == SlotState.UNKNOWN
    assert snap.darkened_fraction == 0.0
    assert snap.changed_fraction == 0.0
    assert snap.timestamp == 0.0


def test_snapshot_is_ready():
    snap = SlotSnapshot(index=0, state=SlotState.READY)
    assert snap.is_ready is True
    assert snap.is_on_cooldown is False
    assert snap.is_casting is False


def test_snapshot_is_on_cooldown():
    snap = SlotSnapshot(index=0, state=SlotState.ON_COOLDOWN)
    assert snap.is_ready is False
    assert snap.is_on_cooldown is True
    assert snap.is_casting is False


def test_snapshot_is_casting():
    snap = SlotSnapshot(index=0, state=SlotState.CASTING)
    assert snap.is_casting is True
    assert snap.is_ready is False


def test_snapshot_is_channeling():
    snap = SlotSnapshot(index=0, state=SlotState.CHANNELING)
    assert snap.is_casting is True
