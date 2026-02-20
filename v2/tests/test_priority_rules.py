"""Tests for src/automation/priority_rules.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.automation.priority_rules import (
    dot_refresh_eligible,
    manual_item_is_eligible,
    normalize_activation_rule,
    normalize_ready_source,
    slot_item_is_eligible_for_state_dict,
)


class TestNormalizeActivationRule:
    def test_always(self):
        assert normalize_activation_rule("always") == "always"

    def test_dot_refresh(self):
        assert normalize_activation_rule("dot_refresh") == "dot_refresh"

    def test_require_glow(self):
        assert normalize_activation_rule("require_glow") == "require_glow"

    def test_garbage(self):
        assert normalize_activation_rule("garbage") == "always"

    def test_none(self):
        assert normalize_activation_rule(None) == "always"


class TestNormalizeReadySource:
    def test_slot_default(self):
        assert normalize_ready_source("", "slot") == "slot"

    def test_manual_default(self):
        assert normalize_ready_source("", "manual") == "always"

    def test_valid_sources(self):
        assert normalize_ready_source("slot", "slot") == "slot"
        assert normalize_ready_source("always", "slot") == "always"
        assert normalize_ready_source("buff_present", "slot") == "buff_present"
        assert normalize_ready_source("buff_missing", "slot") == "buff_missing"


class TestDotRefreshEligible:
    def test_no_glow(self):
        assert dot_refresh_eligible(False, False) is True

    def test_yellow_only(self):
        assert dot_refresh_eligible(True, False) is False

    def test_red_glow(self):
        assert dot_refresh_eligible(False, True) is True

    def test_both_glows(self):
        assert dot_refresh_eligible(True, True) is True


class TestSlotItemEligibility:
    def test_ready_slot(self):
        item = {"type": "slot", "slot_index": 0, "activation_rule": "always"}
        state = {"state": "ready", "index": 0}
        assert slot_item_is_eligible_for_state_dict(item, state) is True

    def test_cooldown_slot(self):
        item = {"type": "slot", "slot_index": 0, "activation_rule": "always"}
        state = {"state": "on_cooldown", "index": 0}
        assert slot_item_is_eligible_for_state_dict(item, state) is False

    def test_require_glow_no_glow(self):
        item = {"type": "slot", "slot_index": 0, "activation_rule": "require_glow"}
        state = {"state": "ready", "index": 0, "glow_ready": False}
        assert slot_item_is_eligible_for_state_dict(item, state) is False

    def test_require_glow_with_glow(self):
        item = {"type": "slot", "slot_index": 0, "activation_rule": "require_glow"}
        state = {"state": "ready", "index": 0, "glow_ready": True}
        assert slot_item_is_eligible_for_state_dict(item, state) is True

    def test_none_state(self):
        item = {"type": "slot", "slot_index": 0}
        assert slot_item_is_eligible_for_state_dict(item, None) is False


class TestManualItemEligibility:
    def test_always_ready(self):
        item = {"type": "manual", "action_id": "trinket"}
        assert manual_item_is_eligible(item) is True

    def test_buff_present_no_buff_data(self):
        item = {"type": "manual", "ready_source": "buff_present", "buff_roi_id": "foo"}
        assert manual_item_is_eligible(item, buff_states=None) is False

    def test_buff_present_with_data(self):
        item = {"type": "manual", "ready_source": "buff_present", "buff_roi_id": "foo"}
        buffs = {"foo": {"calibrated": True, "present": True, "status": "ok"}}
        assert manual_item_is_eligible(item, buff_states=buffs) is True

    def test_buff_missing_with_present(self):
        item = {"type": "manual", "ready_source": "buff_missing", "buff_roi_id": "foo"}
        buffs = {"foo": {"calibrated": True, "present": True, "status": "ok"}}
        assert manual_item_is_eligible(item, buff_states=buffs) is False
