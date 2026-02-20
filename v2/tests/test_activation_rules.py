"""Tests for src/core/activation_rules.py"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.activation_rules import ActivationRuleRegistry


class TestRegisterAndGet:
    def test_register_and_get(self):
        reg = ActivationRuleRegistry()
        reg.register(id="always", label="Always", group="general",
                     group_label="General", owner="automation", order=0)
        rule = reg.get("always")
        assert rule is not None
        assert rule.label == "Always"
        assert rule.group == "general"
        assert rule.owner == "automation"

    def test_get_missing_returns_none(self):
        reg = ActivationRuleRegistry()
        assert reg.get("nonexistent") is None


class TestListRules:
    def test_list_rules_sorted(self):
        reg = ActivationRuleRegistry()
        reg.register(id="b", label="B", group="z", group_label="Z", owner="m1", order=10)
        reg.register(id="a", label="A", group="a", group_label="A", owner="m1", order=5)
        reg.register(id="c", label="C", group="a", group_label="A", owner="m2", order=0)
        rules = reg.list_rules()
        assert [r.id for r in rules] == ["c", "a", "b"]


class TestListGrouped:
    def test_single_group(self):
        reg = ActivationRuleRegistry()
        reg.register(id="always", label="Always", group="general",
                     group_label="General", owner="automation")
        grouped = reg.list_grouped()
        assert "general" in grouped
        assert len(grouped) == 1
        assert grouped["general"][0].id == "always"

    def test_multiple_groups(self):
        reg = ActivationRuleRegistry()
        reg.register(id="always", label="Always", group="general",
                     group_label="General", owner="auto", order=0)
        reg.register(id="glow", label="Require Glow", group="glow",
                     group_label="Glow", owner="glow_mod", order=10)
        grouped = reg.list_grouped()
        assert len(grouped) == 2
        assert "general" in grouped
        assert "glow" in grouped


class TestGetLabel:
    def test_known_id(self):
        reg = ActivationRuleRegistry()
        reg.register(id="always", label="Always", group="g",
                     group_label="G", owner="o")
        assert reg.get_label("always") == "Always"

    def test_unknown_id_returns_id(self):
        reg = ActivationRuleRegistry()
        assert reg.get_label("dot_refresh") == "dot_refresh"


class TestTeardownModule:
    def test_removes_only_target_module(self):
        reg = ActivationRuleRegistry()
        reg.register(id="always", label="Always", group="g",
                     group_label="G", owner="automation")
        reg.register(id="glow", label="Glow", group="g",
                     group_label="G", owner="glow_mod")
        reg.teardown_module("glow_mod")
        assert reg.get("always") is not None
        assert reg.get("glow") is None

    def test_teardown_nonexistent_module_is_safe(self):
        reg = ActivationRuleRegistry()
        reg.register(id="always", label="Always", group="g",
                     group_label="G", owner="automation")
        reg.teardown_module("nonexistent")
        assert len(reg.list_rules()) == 1
