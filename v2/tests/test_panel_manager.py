from __future__ import annotations

import pytest

from src.core.panel_manager import PanelManager


def _factory():
    return "widget"


def test_register_and_get():
    pm = PanelManager()
    pm.register("mod/panel", "primary", _factory, title="Test", owner="mod")
    panels = pm.get_panels("primary")
    assert len(panels) == 1
    assert panels[0].id == "mod/panel"
    assert panels[0].title == "Test"


def test_panels_sorted_by_order():
    pm = PanelManager()
    pm.register("b", "primary", _factory, order=20, owner="mod")
    pm.register("a", "primary", _factory, order=10, owner="mod")
    pm.register("c", "primary", _factory, order=30, owner="mod")
    ids = [p.id for p in pm.get_panels("primary")]
    assert ids == ["a", "b", "c"]


def test_get_panels_filters_by_area():
    pm = PanelManager()
    pm.register("p1", "primary", _factory, owner="mod")
    pm.register("s1", "sidebar", _factory, owner="mod")
    assert len(pm.get_panels("primary")) == 1
    assert len(pm.get_panels("sidebar")) == 1
    assert pm.get_panels("primary")[0].id == "p1"
    assert pm.get_panels("sidebar")[0].id == "s1"


def test_hidden_panels_not_returned():
    pm = PanelManager()
    pm.register("p1", "primary", _factory, owner="mod")
    pm._panels["p1"].visible = False
    assert pm.get_panels("primary") == []


def test_teardown_module():
    pm = PanelManager()
    pm.register("a/p", "primary", _factory, owner="a")
    pm.register("b/p", "primary", _factory, owner="b")
    pm.teardown_module("a")
    panels = pm.get_panels("primary")
    assert len(panels) == 1
    assert panels[0].owner == "b"


def test_register_same_id_overwrites():
    pm = PanelManager()
    pm.register("p1", "primary", _factory, title="First", owner="mod")
    pm.register("p1", "primary", _factory, title="Second", owner="mod")
    panels = pm.get_panels("primary")
    assert len(panels) == 1
    assert panels[0].title == "Second"
