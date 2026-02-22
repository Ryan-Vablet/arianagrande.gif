"""Tests for CastEngine — cast/channeling detection post-processor."""
import time

import pytest

from modules.cast_detection.cast_engine import CastEngine


@pytest.fixture
def engine():
    e = CastEngine()
    e.update_config({
        "cast_detection_enabled": True,
        "cast_min_fraction": 0.05,
        "cast_max_fraction": 0.25,
        "cast_confirm_frames": 1,
        "cast_min_ms": 150,
        "cast_max_ms": 3000,
        "cast_cancel_grace_ms": 120,
        "channeling_enabled": True,
    })
    return e


def _make_state(index: int, state: str = "ready", darkened_fraction: float = 0.0) -> dict:
    return {
        "index": index,
        "state": state,
        "darkened_fraction": darkened_fraction,
        "changed_fraction": 0.0,
        "timestamp": time.time(),
    }


class TestBasicPassthrough:
    def test_ready_passthrough(self, engine):
        states = [_make_state(0, "ready", 0.0)]
        result = engine.process_states(states)
        assert result[0]["state"] == "ready"

    def test_cooldown_passthrough(self, engine):
        states = [_make_state(0, "on_cooldown", 0.5)]
        result = engine.process_states(states)
        assert result[0]["state"] == "on_cooldown"

    def test_gcd_passthrough(self, engine):
        states = [_make_state(0, "gcd", 0.4)]
        result = engine.process_states(states)
        assert result[0]["state"] == "gcd"

    def test_unknown_passthrough(self, engine):
        states = [_make_state(0, "unknown", 0.0)]
        result = engine.process_states(states)
        assert result[0]["state"] == "unknown"


class TestCastDetection:
    def test_intermediate_fraction_triggers_casting(self, engine):
        states = [_make_state(0, "ready", 0.15)]
        result = engine.process_states(states)
        assert result[0]["state"] == "casting"

    def test_below_min_fraction_stays_ready(self, engine):
        states = [_make_state(0, "ready", 0.03)]
        result = engine.process_states(states)
        assert result[0]["state"] == "ready"

    def test_above_max_fraction_stays_ready(self, engine):
        states = [_make_state(0, "ready", 0.28)]
        result = engine.process_states(states)
        assert result[0]["state"] == "ready"

    def test_cooldown_overrides_cast(self, engine):
        engine.process_states([_make_state(0, "ready", 0.15)])
        states = [_make_state(0, "on_cooldown", 0.5)]
        result = engine.process_states(states)
        assert result[0]["state"] == "on_cooldown"

    def test_confirm_frames_delays_casting(self):
        e = CastEngine()
        e.update_config({
            "cast_detection_enabled": True,
            "cast_min_fraction": 0.05,
            "cast_max_fraction": 0.25,
            "cast_confirm_frames": 3,
            "cast_min_ms": 150,
            "cast_max_ms": 3000,
            "cast_cancel_grace_ms": 120,
        })
        states = [_make_state(0, "ready", 0.15)]
        assert e.process_states(states)[0]["state"] == "ready"
        assert e.process_states(states)[0]["state"] == "ready"
        assert e.process_states(states)[0]["state"] == "casting"

    def test_multiple_slots_independent(self, engine):
        states = [
            _make_state(0, "ready", 0.15),
            _make_state(1, "ready", 0.0),
            _make_state(2, "on_cooldown", 0.5),
        ]
        result = engine.process_states(states)
        assert result[0]["state"] == "casting"
        assert result[1]["state"] == "ready"
        assert result[2]["state"] == "on_cooldown"


class TestCastGate:
    def test_gate_false_suppresses_casting(self, engine):
        states = [_make_state(0, "ready", 0.15)]
        result = engine.process_states(states, cast_gate_active=False)
        assert result[0]["state"] == "ready"

    def test_gate_true_allows_casting(self, engine):
        states = [_make_state(0, "ready", 0.15)]
        result = engine.process_states(states, cast_gate_active=True)
        assert result[0]["state"] == "casting"


class TestDisabled:
    def test_disabled_passes_through(self):
        e = CastEngine()
        e.update_config({"cast_detection_enabled": False})
        states = [_make_state(0, "ready", 0.15)]
        result = e.process_states(states)
        assert result[0]["state"] == "ready"


class TestChanneling:
    def test_channeling_after_max_duration(self, engine):
        engine.update_config({
            "cast_detection_enabled": True,
            "cast_min_fraction": 0.05,
            "cast_max_fraction": 0.25,
            "cast_confirm_frames": 1,
            "cast_min_ms": 50,
            "cast_max_ms": 100,
            "cast_cancel_grace_ms": 0,
            "channeling_enabled": True,
        })
        states = [_make_state(0, "ready", 0.15)]
        result = engine.process_states(states)
        assert result[0]["state"] == "casting"

        time.sleep(0.15)
        result = engine.process_states(states)
        assert result[0]["state"] == "channeling"

    def test_channeling_disabled_stays_casting(self):
        e = CastEngine()
        e.update_config({
            "cast_detection_enabled": True,
            "cast_min_fraction": 0.05,
            "cast_max_fraction": 0.25,
            "cast_confirm_frames": 1,
            "cast_min_ms": 50,
            "cast_max_ms": 100,
            "cast_cancel_grace_ms": 0,
            "channeling_enabled": False,
        })
        states = [_make_state(0, "ready", 0.15)]
        e.process_states(states)

        time.sleep(0.15)
        result = e.process_states(states)
        assert result[0]["state"] == "casting"


class TestReset:
    def test_reset_clears_state(self, engine):
        engine.process_states([_make_state(0, "ready", 0.15)])
        engine.reset()
        states = [_make_state(0, "ready", 0.0)]
        result = engine.process_states(states)
        assert result[0]["state"] == "ready"


class TestOriginalData:
    def test_original_dict_not_mutated(self, engine):
        original = _make_state(0, "ready", 0.15)
        original_copy = dict(original)
        engine.process_states([original])
        assert original == original_copy
