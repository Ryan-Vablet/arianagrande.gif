"""Tests for modules/automation/key_sender.py"""
import sys, os, time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

# keyboard is lazily imported inside key_sender — inject a mock into sys.modules
_mock_keyboard = MagicMock()
sys.modules["keyboard"] = _mock_keyboard

from modules.automation.key_sender import KeySender


@pytest.fixture(autouse=True)
def reset_keyboard_mock():
    _mock_keyboard.reset_mock()
    yield


def _ready_state(index: int = 0) -> dict:
    return {"index": index, "state": "ready"}


def _cd_state(index: int = 0) -> dict:
    return {"index": index, "state": "on_cooldown"}


def _casting_state(index: int = 0) -> dict:
    return {"index": index, "state": "casting"}


def _slot_item(index: int, rule: str = "always") -> dict:
    return {"type": "slot", "slot_index": index, "activation_rule": rule}


def _manual_item(action_id: str) -> dict:
    return {"type": "manual", "action_id": action_id}


class TestKeySenderBasic:
    def test_not_armed_no_single_fire_returns_none(self):
        ks = KeySender()
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=False,
        )
        assert result is None

    def test_armed_no_ready_slots(self):
        ks = KeySender()
        result = ks.evaluate_and_send(
            slot_states=[_cd_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
        )
        assert result is None

    def test_armed_ready_slot_sends(self):
        ks = KeySender()
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
        )
        assert result is not None
        assert result["action"] == "sent"
        assert result["keybind"] == "1"
        _mock_keyboard.send.assert_called_once_with("1")


class TestPriorityOrder:
    def test_higher_priority_fires_first(self):
        ks = KeySender()
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0), _ready_state(1)],
            priority_items=[_slot_item(1), _slot_item(0)],
            keybinds=["1", "2"],
            manual_actions=[],
            armed=True,
        )
        assert result is not None
        assert result["keybind"] == "2"
        assert result["slot_index"] == 1


class TestThrottling:
    def test_min_interval_throttles(self):
        ks = KeySender()
        ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
        )
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
            min_interval_ms=5000,
        )
        assert result is None


class TestCastBlocking:
    def test_blocking_cast_returns_blocked(self):
        ks = KeySender()
        result = ks.evaluate_and_send(
            slot_states=[_casting_state(0), _ready_state(1)],
            priority_items=[_slot_item(1)],
            keybinds=["1", "2"],
            manual_actions=[],
            armed=True,
        )
        assert result is not None
        assert result["action"] == "blocked"
        assert result["reason"] == "casting"


class TestWindowBlocking:
    @patch("modules.automation.key_sender.is_target_window_active", return_value=False)
    def test_wrong_window_blocks(self, mock_win):
        ks = KeySender()
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
            target_window_title="World of Warcraft",
        )
        assert result is not None
        assert result["action"] == "blocked"
        assert result["reason"] == "window"


class TestSingleFire:
    def test_single_fire_sends_once(self):
        ks = KeySender()
        ks.request_single_fire()
        assert ks.single_fire_pending is True

        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=False,
        )
        assert result is not None
        assert result["action"] == "sent"
        assert ks.single_fire_pending is False

    def test_single_fire_bypasses_armed(self):
        ks = KeySender()
        ks.request_single_fire()
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=False,
        )
        assert result is not None
        assert result["action"] == "sent"


class TestQueuedOverride:
    @patch("modules.automation.key_sender.time")
    def test_queued_whitelist_sends(self, mock_time):
        mock_time.time.return_value = 1000.0
        mock_time.sleep = MagicMock()
        ks = KeySender()
        on_sent = MagicMock()
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
            queued_override={"key": "5", "source": "whitelist"},
            on_queued_sent=on_sent,
        )
        assert result is not None
        assert result["action"] == "sent"
        assert result["queued"] is True
        assert result["keybind"] == "5"
        on_sent.assert_called_once()


class TestManualAction:
    def test_manual_action_sends(self):
        ks = KeySender()
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_manual_item("trinket")],
            keybinds=["1"],
            manual_actions=[{"id": "trinket", "name": "Trinket", "keybind": "f1"}],
            armed=True,
        )
        assert result is not None
        assert result["action"] == "sent"
        assert result["keybind"] == "f1"


class TestSuppressPriority:
    @patch("modules.automation.key_sender.time")
    def test_suppress_after_queued(self, mock_time):
        mock_time.time.return_value = 1000.0
        mock_time.sleep = MagicMock()
        ks = KeySender()
        ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
            queued_override={"key": "5", "source": "whitelist"},
            on_queued_sent=MagicMock(),
        )
        mock_time.time.return_value = 1000.5
        result = ks.evaluate_and_send(
            slot_states=[_ready_state(0)],
            priority_items=[_slot_item(0)],
            keybinds=["1"],
            manual_actions=[],
            armed=True,
        )
        assert result is None
