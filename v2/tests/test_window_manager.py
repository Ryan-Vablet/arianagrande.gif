from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.config_manager import ConfigManager
from src.core.window_manager import WindowManager


@pytest.fixture
def wm(tmp_path: Path) -> WindowManager:
    cfg = ConfigManager(tmp_path / "config.json")
    cfg.load()
    cfg.set("app", {"window_geometry": {}})
    return WindowManager(cfg)


def _make_mock_widget(visible: bool = False):
    w = MagicMock()
    w.isVisible.return_value = visible
    w.geometry.return_value = MagicMock(x=lambda: 100, y=lambda: 200, width=lambda: 300, height=lambda: 400)
    return w


def test_register_and_list_menu_entries(wm):
    wm.register("w1", lambda: MagicMock(), title="Window 1", owner="mod")
    entries = wm.list_menu_entries()
    assert len(entries) == 1
    assert entries[0].title == "Window 1"


def test_show_in_menu_false_excluded(wm):
    wm.register("w1", lambda: MagicMock(), title="W1", owner="mod", show_in_menu=False)
    assert wm.list_menu_entries() == []


def test_show_creates_lazily(wm):
    factory = MagicMock(return_value=MagicMock())
    wm.register("w1", factory, title="W1", owner="mod")
    assert wm.get("w1") is None
    wm.show("w1")
    factory.assert_called_once()
    assert wm.get("w1") is not None


def test_show_singleton(wm):
    factory = MagicMock(return_value=MagicMock())
    wm.register("w1", factory, title="W1", owner="mod")
    wm.show("w1")
    wm.show("w1")
    factory.assert_called_once()


def test_hide(wm):
    widget = MagicMock()
    wm.register("w1", lambda: widget, title="W1", owner="mod")
    wm.show("w1")
    wm.hide("w1")
    widget.hide.assert_called()


def test_toggle(wm):
    widget = MagicMock()
    widget.isVisible.return_value = False
    wm.register("w1", lambda: widget, title="W1", owner="mod")
    wm.toggle("w1")
    widget.show.assert_called()

    widget.isVisible.return_value = True
    wm.toggle("w1")
    widget.hide.assert_called()


def test_is_visible(wm):
    assert wm.is_visible("nonexistent") is False
    widget = MagicMock()
    widget.isVisible.return_value = True
    wm.register("w1", lambda: widget, title="W1", owner="mod")
    wm.show("w1")
    assert wm.is_visible("w1") is True


def test_teardown_module(wm):
    widget = MagicMock()
    wm.register("a/w", lambda: widget, title="AW", owner="a")
    wm.register("b/w", lambda: MagicMock(), title="BW", owner="b")
    wm.show("a/w")
    wm.teardown_module("a")
    assert wm.get("a/w") is None
    widget.close.assert_called()
    assert len(wm.list_menu_entries()) == 1


def test_teardown_saves_and_closes(wm):
    widget = MagicMock()
    rect = MagicMock()
    rect.x.return_value = 10
    rect.y.return_value = 20
    rect.width.return_value = 300
    rect.height.return_value = 400
    widget.geometry.return_value = rect
    widget.isVisible.return_value = True
    wm.register("w1", lambda: widget, title="W1", owner="mod")
    wm.show("w1")
    wm.teardown()
    widget.close.assert_called()
