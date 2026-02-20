"""Tests for src/automation/binds.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.automation.binds import (
    format_bind_for_display,
    is_modifier_token,
    normalize_bind,
    normalize_bind_from_parts,
    normalize_key_token,
    parse_bind,
)


class TestNormalizeKeyToken:
    def test_left_ctrl(self):
        assert normalize_key_token("Left Ctrl") == "ctrl"

    def test_esc(self):
        assert normalize_key_token("esc") == "escape"

    def test_plain_key(self):
        assert normalize_key_token("A") == "a"

    def test_empty(self):
        assert normalize_key_token("") == ""


class TestIsModifierToken:
    def test_ctrl(self):
        assert is_modifier_token("ctrl") is True

    def test_a(self):
        assert is_modifier_token("a") is False


class TestNormalizeBind:
    def test_control_plus_1(self):
        assert normalize_bind("Control + 1") == "ctrl+1"

    def test_shift_f1(self):
        assert normalize_bind("Shift+F1") == "shift+f1"

    def test_canonical_order(self):
        assert normalize_bind("alt+ctrl+a") == "ctrl+alt+a"

    def test_empty(self):
        assert normalize_bind("") == ""

    def test_modifier_only(self):
        assert normalize_bind("ctrl") == ""

    def test_two_primaries(self):
        assert normalize_bind("a+b") == ""


class TestNormalizeBindFromParts:
    def test_with_mods(self):
        assert normalize_bind_from_parts({"alt", "ctrl"}, "a") == "ctrl+alt+a"

    def test_no_mods(self):
        assert normalize_bind_from_parts(set(), "f5") == "f5"

    def test_primary_is_modifier(self):
        assert normalize_bind_from_parts(set(), "ctrl") == ""


class TestParseBind:
    def test_ctrl_a(self):
        result = parse_bind("ctrl+a")
        assert result == (frozenset({"ctrl"}), "a")

    def test_simple_key(self):
        result = parse_bind("f5")
        assert result == (frozenset(), "f5")

    def test_invalid(self):
        assert parse_bind("") is None
        assert parse_bind("ctrl") is None


class TestFormatBindForDisplay:
    def test_ctrl_1(self):
        assert format_bind_for_display("ctrl+1") == "Ctrl+1"

    def test_f5(self):
        assert format_bind_for_display("f5") == "F5"

    def test_empty(self):
        assert format_bind_for_display("") == "Set"

    def test_mouse_buttons(self):
        assert format_bind_for_display("x1") == "Mouse 4"
        assert format_bind_for_display("x2") == "Mouse 5"

    def test_long_key(self):
        assert format_bind_for_display("escape") == "Escape"
