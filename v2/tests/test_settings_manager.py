from __future__ import annotations

import pytest

from src.core.settings_manager import SettingsManager


def _factory():
    return "widget"


def test_register_top_level_tab():
    sm = SettingsManager()
    sm.register("foo", _factory, title="Foo", owner="mod")
    tabs = sm.get_tabs()
    assert len(tabs) == 1
    assert tabs[0]["path"] == "foo"
    assert tabs[0]["title"] == "Foo"
    assert tabs[0]["widget_factory"] is not None
    assert tabs[0]["children"] == []


def test_register_child_creates_tab_with_child():
    sm = SettingsManager()
    sm.register("foo/bar", _factory, title="Bar", owner="mod")
    tabs = sm.get_tabs()
    assert len(tabs) == 1
    assert tabs[0]["path"] == "foo"
    assert tabs[0]["widget_factory"] is None  # auto-created container
    assert len(tabs[0]["children"]) == 1
    assert tabs[0]["children"][0]["title"] == "Bar"


def test_tab_title_inferred_from_path():
    sm = SettingsManager()
    sm.register("my_settings/sub", _factory, title="Sub", owner="mod")
    tabs = sm.get_tabs()
    assert tabs[0]["title"] == "My Settings"


def test_auto_created_container_tab():
    sm = SettingsManager()
    sm.register("detection/brightness", _factory, title="Brightness", owner="a", order=10)
    sm.register("detection/glow", _factory, title="Glow", owner="b", order=20)
    tabs = sm.get_tabs()
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["path"] == "detection"
    assert tab["widget_factory"] is None
    assert len(tab["children"]) == 2


def test_tab_with_own_widget_and_children():
    sm = SettingsManager()
    sm.register("detection", _factory, title="Detection", owner="a", order=10)
    sm.register("detection/brightness", _factory, title="Brightness", owner="b", order=20)
    tabs = sm.get_tabs()
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["widget_factory"] is not None
    assert len(tab["children"]) == 1


def test_children_sorted_by_order():
    sm = SettingsManager()
    sm.register("tab/c", _factory, title="C", owner="mod", order=30)
    sm.register("tab/a", _factory, title="A", owner="mod", order=10)
    sm.register("tab/b", _factory, title="B", owner="mod", order=20)
    tabs = sm.get_tabs()
    titles = [c["title"] for c in tabs[0]["children"]]
    assert titles == ["A", "B", "C"]


def test_tabs_sorted_by_order():
    sm = SettingsManager()
    sm.register("z_tab", _factory, title="Z", owner="mod", order=99)
    sm.register("a_tab", _factory, title="A", owner="mod", order=1)
    tabs = sm.get_tabs()
    paths = [t["path"] for t in tabs]
    assert paths == ["a_tab", "z_tab"]


def test_teardown_module():
    sm = SettingsManager()
    sm.register("tab_a", _factory, title="A", owner="a")
    sm.register("tab_b", _factory, title="B", owner="b")
    sm.teardown_module("a")
    tabs = sm.get_tabs()
    assert len(tabs) == 1
    assert tabs[0]["path"] == "tab_b"
