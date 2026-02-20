from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.config_manager import ConfigManager
from src.core.core import Core
from src.core.module_manager import ModuleManager
from modules.core_capture.module import CoreCaptureModule


@pytest.fixture
def core(tmp_path):
    cfg = ConfigManager(tmp_path / "config.json")
    cfg.load()
    return Core(cfg)


def test_setup_registers_panels_settings_window(core):
    mod = CoreCaptureModule()
    mod.setup(core)

    assert len(core.panels.get_panels("primary")) == 2
    assert any(p.id == "core_capture/preview" for p in core.panels.get_panels("primary"))
    assert any(p.id == "core_capture/controls" for p in core.panels.get_panels("primary"))

    tabs = core.settings.get_tabs()
    assert any(t["path"] == "detection" for t in tabs)
    detection_tab = next(t for t in tabs if t["path"] == "detection")
    child_paths = [c["path"] for c in detection_tab["children"]]
    assert "detection/capture_region" in child_paths
    assert "detection/slot_layout" in child_paths
    assert "detection/overlay" in child_paths

    entries = core.windows.list_menu_entries()
    assert any(e.id == "core_capture/overlay" for e in entries)


def test_default_config_created_if_missing(core):
    assert core.get_config("core_capture") == {}
    mod = CoreCaptureModule()
    mod.setup(core)
    cfg = core.get_config("core_capture")
    assert "monitor_index" in cfg
    assert "bounding_box" in cfg


def test_get_service_capture_running(core):
    mod = CoreCaptureModule()
    mod.setup(core)
    assert mod.get_service("capture_running") is False


def test_get_service_bounding_box(core):
    mod = CoreCaptureModule()
    mod.setup(core)
    bb = mod.get_service("bounding_box")
    assert isinstance(bb, dict)
    assert "top" in bb


def test_teardown_stops_capture(core):
    mod = CoreCaptureModule()
    mod.setup(core)
    mod._is_running = True
    mock_worker = MagicMock()
    mod._worker = mock_worker
    mod.teardown()
    assert mod._is_running is False
    mock_worker.stop.assert_called_once()
