"""Tests for modules/automation/module.py"""
import sys, os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# keyboard is lazily imported — inject mock
sys.modules.setdefault("keyboard", MagicMock())

import pytest


@pytest.fixture
def core():
    """Minimal Core mock."""
    c = MagicMock()
    c._configs = {}

    def get_config(ns):
        return c._configs.get(ns, {}).copy()

    def save_config(ns, data):
        c._configs[ns] = data.copy()

    c.get_config = MagicMock(side_effect=get_config)
    c.save_config = MagicMock(side_effect=save_config)
    c.get_service = MagicMock(return_value=None)
    c.is_loaded = MagicMock(return_value=False)
    c.get_module = MagicMock(return_value=None)
    c.emit = MagicMock()
    c.subscribe = MagicMock()
    c.panels = MagicMock()
    c.settings = MagicMock()
    c.windows = MagicMock()
    return c


@pytest.fixture
def module(core):
    """AutomationModule wired up with mocked Core (no hotkey/queue listeners started)."""
    from modules.automation.module import AutomationModule

    m = AutomationModule()
    with patch.object(m, "_start_hotkey_listener"), patch.object(m, "_start_queue_listener"):
        m.setup(core)
    return m


class TestSetup:
    def test_panels_registered(self, core, module):
        panel_calls = core.panels.register.call_args_list
        panel_ids = [call.kwargs.get("id") or call[1].get("id") for call in panel_calls]
        assert "automation/controls" in panel_ids
        assert "automation/priority" in panel_ids

    def test_settings_registered(self, core, module):
        settings_calls = core.settings.register.call_args_list
        paths = [call.kwargs.get("path") or call[1].get("path") for call in settings_calls]
        assert "automation/general" in paths
        assert "automation/keybinds" in paths
        assert "automation/priority_lists" in paths
        assert "automation/queue" in paths

    def test_default_config_created(self, core, module):
        cfg = core._configs.get("automation", {})
        assert cfg.get("active_list_id") == "default"
        assert isinstance(cfg.get("priority_lists"), list)
        assert len(cfg["priority_lists"]) >= 1


class TestArmDisarm:
    def test_arm(self, module, core):
        module.arm()
        assert module.is_armed is True
        core.emit.assert_any_call("automation.armed_changed", armed=True)

    def test_disarm(self, module, core):
        module.arm()
        module.disarm()
        assert module.is_armed is False

    def test_toggle(self, module):
        module.toggle_armed()
        assert module.is_armed is True
        module.toggle_armed()
        assert module.is_armed is False

    def test_arm_idempotent(self, module, core):
        module.arm()
        core.emit.reset_mock()
        module.arm()
        core.emit.assert_not_called()


class TestListSwitching:
    def test_switch_to_list(self, module, core):
        cfg = core._configs["automation"]
        cfg["priority_lists"].append({
            "id": "aoe", "name": "AoE",
            "toggle_bind": "", "single_fire_bind": "",
            "priority_items": [], "manual_actions": [],
        })
        core._configs["automation"] = cfg

        module.switch_to_list("aoe")
        updated = core._configs["automation"]
        assert updated["active_list_id"] == "aoe"

    def test_switch_to_nonexistent_list(self, module, core):
        module.switch_to_list("nonexistent")
        cfg = core._configs["automation"]
        assert cfg["active_list_id"] == "default"


class TestServices:
    def test_armed_service(self, module):
        assert module.get_service("armed") is False
        module.arm()
        assert module.get_service("armed") is True

    def test_active_list_id_service(self, module):
        assert module.get_service("active_list_id") == "default"

    def test_last_action_service(self, module):
        assert module.get_service("last_action") is None

    def test_unknown_service(self, module):
        assert module.get_service("unknown") is None


class TestHotkeyTriggered:
    def test_toggle_bind_arms_and_switches(self, module, core):
        cfg = core._configs["automation"]
        cfg["priority_lists"][0]["toggle_bind"] = "f5"
        core._configs["automation"] = cfg

        module._on_hotkey_triggered("f5")
        assert module.is_armed is True

    def test_toggle_bind_disarms_when_active(self, module, core):
        cfg = core._configs["automation"]
        cfg["priority_lists"][0]["toggle_bind"] = "f5"
        core._configs["automation"] = cfg

        module._on_hotkey_triggered("f5")
        assert module.is_armed is True
        module._on_hotkey_triggered("f5")
        assert module.is_armed is False

    def test_single_fire_bind(self, module, core):
        cfg = core._configs["automation"]
        cfg["priority_lists"][0]["single_fire_bind"] = "f6"
        core._configs["automation"] = cfg

        module._on_hotkey_triggered("f6")
        assert module._key_sender.single_fire_pending is True


class TestOnFrame:
    def test_on_frame_armed_sends(self, module, core):
        import numpy as np
        module.arm()
        module._queue_listener = None

        core.get_service = MagicMock(side_effect=lambda mod, svc: (
            [{"index": 0, "state": "ready"}] if svc == "slot_states" else None
        ))

        cfg = core._configs["automation"]
        cfg["keybinds"] = ["1"]
        cfg["priority_lists"][0]["priority_items"] = [
            {"type": "slot", "slot_index": 0, "activation_rule": "always"}
        ]
        core._configs["automation"] = cfg

        frame = np.zeros((50, 400, 3), dtype=np.uint8)
        module.on_frame(frame)

        assert module._last_action is not None
        assert module._last_action["action"] == "sent"

    def test_on_frame_disarmed_no_send(self, module, core):
        import numpy as np
        module._queue_listener = None

        core.get_service = MagicMock(side_effect=lambda mod, svc: (
            [{"index": 0, "state": "ready"}] if svc == "slot_states" else None
        ))

        cfg = core._configs["automation"]
        cfg["keybinds"] = ["1"]
        cfg["priority_lists"][0]["priority_items"] = [
            {"type": "slot", "slot_index": 0, "activation_rule": "always"}
        ]
        core._configs["automation"] = cfg

        frame = np.zeros((50, 400, 3), dtype=np.uint8)
        module.on_frame(frame)
        assert module._last_action is None


class TestTeardown:
    def test_teardown_disarms(self, module):
        module.arm()
        module._hotkey_listener = MagicMock()
        module._queue_listener = MagicMock()
        module.teardown()
        assert module.is_armed is False
        module._hotkey_listener.stop.assert_called_once()
        module._queue_listener.stop.assert_called_once()
