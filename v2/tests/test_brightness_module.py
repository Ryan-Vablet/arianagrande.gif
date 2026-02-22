"""Tests for BrightnessDetectionModule."""
import base64

import numpy as np
import pytest

from modules.brightness_detection.module import BrightnessDetectionModule
from src.core.config_manager import ConfigManager
from src.core.core import Core


class _FakeConfigManager:
    def __init__(self):
        self._store = {}

    def get(self, ns):
        import copy
        return copy.deepcopy(self._store.get(ns, {}))

    def set(self, ns, data):
        import copy
        self._store[ns] = copy.deepcopy(data)

    def update(self, ns, updates):
        d = self.get(ns)
        d.update(updates)
        self.set(ns, d)


@pytest.fixture
def core():
    cfg = _FakeConfigManager()
    cfg.set("core_capture", {
        "monitor_index": 1,
        "polling_fps": 20,
        "bounding_box": {"top": 0, "left": 0, "width": 100, "height": 40},
        "slots": {"count": 4, "gap": 2, "padding": 0},
    })
    c = Core.__new__(Core)
    c._config = cfg
    c._modules = {}
    c._hooks = {}
    from src.core.panel_manager import PanelManager
    from src.core.settings_manager import SettingsManager
    from src.core.window_manager import WindowManager
    c.panels = PanelManager()
    c.settings = SettingsManager()
    c.windows = WindowManager(cfg)
    c.windows.on_visibility_changed(c._on_window_visibility_changed)
    return c


@pytest.fixture
def module(core):
    mod = BrightnessDetectionModule()
    core.register_module(mod.key, mod)
    mod.setup(core)
    return mod


def test_setup_registers_panels_and_settings(core, module):
    panel_ids = [p.id for p in core.panels.get_panels("primary")]
    assert "brightness_detection/slot_status" in panel_ids

    tabs = core.settings.get_tabs()
    detection_tab = next((t for t in tabs if t["path"] == "detection"), None)
    assert detection_tab is not None
    child_paths = [c["path"] for c in detection_tab.get("children", [])]
    assert "detection/brightness" in child_paths
    assert "detection/calibration" in child_paths


def test_default_config_created(core, module):
    cfg = core.get_config("brightness_detection")
    assert cfg.get("darken_threshold") == 40
    assert cfg.get("trigger_fraction") == 0.30
    assert cfg.get("cooldown_min_ms") == 2000


def test_get_service_slot_states(module):
    states = module.get_service("slot_states")
    assert states == []


def test_get_service_baselines_calibrated(module):
    assert module.get_service("baselines_calibrated") is False


def test_encode_decode_baselines_roundtrip():
    baselines = {
        0: np.full((20, 24), 128, dtype=np.uint8),
        1: np.full((20, 24), 200, dtype=np.uint8),
    }
    encoded = BrightnessDetectionModule._encode_baselines(baselines)
    decoded = BrightnessDetectionModule._decode_baselines(encoded)
    assert set(decoded.keys()) == {0, 1}
    for idx in baselines:
        assert np.array_equal(decoded[idx], baselines[idx])


def test_sync_config_merges_core_capture_and_brightness(core, module):
    module._sync_config_to_analyzer()
    analyzer = module._analyzer
    assert analyzer._slot_count == 4
    assert analyzer._bbox_width == 100
    assert analyzer._darken_threshold == 40


def test_on_frame_updates_latest_states(core, module):
    frame = np.full((40, 100, 3), 180, dtype=np.uint8)
    module.on_frame(frame)
    states = module.get_service("slot_states")
    assert len(states) == 4
    for s in states:
        assert s["state"] == "unknown"
