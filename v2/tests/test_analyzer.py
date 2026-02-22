"""Tests for SlotAnalyzer — brightness-based cooldown detection."""
import time

import numpy as np
import pytest

from modules.brightness_detection.analyzer import SlotAnalyzer
from src.models.slot import SlotState


@pytest.fixture
def analyzer():
    a = SlotAnalyzer()
    a.update_config({
        "slot_count": 4,
        "slot_gap": 2,
        "slot_padding": 0,
        "bbox_width": 170,
        "bbox_height": 40,
        "darken_threshold": 30,
        "trigger_fraction": 0.30,
        "change_fraction": 0.30,
        "cooldown_min_ms": 0,
        "cast_detection_enabled": False,
        "detection_region": "full",
    })
    return a


def _solid_frame(w: int, h: int, brightness: int) -> np.ndarray:
    """Create a uniform BGR frame."""
    return np.full((h, w, 3), brightness, dtype=np.uint8)


def _slot_darkened_frame(
    base_brightness: int, dark_brightness: int,
    slot_index: int, analyzer: SlotAnalyzer,
) -> np.ndarray:
    """Frame where one slot is darkened, rest match baseline."""
    configs = analyzer.slot_configs
    h = 40
    w = 170
    frame = np.full((h, w, 3), base_brightness, dtype=np.uint8)
    sc = configs[slot_index]
    frame[sc.y_offset:sc.y_offset + sc.height, sc.x_offset:sc.x_offset + sc.width] = dark_brightness
    return frame


# --- Layout ---

def test_layout_computes_correct_slot_count(analyzer):
    assert len(analyzer.slot_configs) == 4


def test_layout_slot_widths(analyzer):
    configs = analyzer.slot_configs
    for sc in configs:
        assert sc.width == (170 - 3 * 2) // 4  # 41


def test_layout_slot_offsets(analyzer):
    configs = analyzer.slot_configs
    slot_w = configs[0].width
    gap = 2
    for i, sc in enumerate(configs):
        assert sc.x_offset == i * (slot_w + gap)


def test_layout_change_clears_baselines(analyzer):
    frame = _solid_frame(170, 40, 180)
    analyzer.calibrate_baselines(frame)
    assert analyzer.has_baselines

    analyzer.update_config({
        "slot_count": 5,
        "slot_gap": 2,
        "slot_padding": 0,
        "bbox_width": 170,
        "bbox_height": 40,
    })
    assert not analyzer.has_baselines


# --- Cropping ---

def test_crop_slot_extracts_correct_region(analyzer):
    frame = np.zeros((40, 170, 3), dtype=np.uint8)
    sc = analyzer.slot_configs[1]
    frame[sc.y_offset:sc.y_offset + sc.height, sc.x_offset:sc.x_offset + sc.width] = 200
    crop = analyzer.crop_slot(frame, sc)
    assert crop.shape[0] == sc.height
    assert crop.shape[1] == sc.width
    assert np.all(crop == 200)


def test_crop_slot_with_padding():
    a = SlotAnalyzer()
    a.update_config({
        "slot_count": 2,
        "slot_gap": 0,
        "slot_padding": 5,
        "bbox_width": 100,
        "bbox_height": 40,
    })
    frame = np.full((40, 100, 3), 128, dtype=np.uint8)
    sc = a.slot_configs[0]
    crop = a.crop_slot(frame, sc)
    assert crop.shape[1] == sc.width - 2 * 5
    assert crop.shape[0] == sc.height - 2 * 5


# --- Brightness ---

def test_brightness_channel_is_grayscale(analyzer):
    bgr = np.full((10, 10, 3), 128, dtype=np.uint8)
    gray = analyzer._get_brightness_channel(bgr)
    assert gray.ndim == 2
    assert gray.dtype == np.uint8


def test_identical_frame_has_zero_darkened(analyzer):
    frame = _solid_frame(170, 40, 180)
    analyzer.calibrate_baselines(frame)
    results = analyzer.analyze_frame(frame)
    for snap in results:
        assert snap.state == SlotState.READY
        assert snap.darkened_fraction < 0.01


def test_fully_darkened_frame(analyzer):
    bright = _solid_frame(170, 40, 200)
    analyzer.calibrate_baselines(bright)
    dark = _solid_frame(170, 40, 50)
    results = analyzer.analyze_frame(dark)
    for snap in results:
        assert snap.state == SlotState.ON_COOLDOWN
        assert snap.darkened_fraction > 0.9


# --- Calibration ---

def test_calibrate_stores_baselines(analyzer):
    assert not analyzer.has_baselines
    frame = _solid_frame(170, 40, 180)
    analyzer.calibrate_baselines(frame)
    assert analyzer.has_baselines
    assert len(analyzer.get_baselines()) == 4


def test_calibrate_single_slot(analyzer):
    frame = _solid_frame(170, 40, 180)
    analyzer.calibrate_baselines(frame)
    new_frame = _solid_frame(170, 40, 200)
    analyzer.calibrate_single_slot(new_frame, 2)
    baselines = analyzer.get_baselines()
    assert len(baselines) == 4
    assert np.mean(baselines[2]) > np.mean(baselines[0])


def test_set_get_baselines_roundtrip(analyzer):
    frame = _solid_frame(170, 40, 180)
    analyzer.calibrate_baselines(frame)
    saved = analyzer.get_baselines()

    a2 = SlotAnalyzer()
    a2.update_config({
        "slot_count": 4, "slot_gap": 2, "slot_padding": 0,
        "bbox_width": 170, "bbox_height": 40,
    })
    a2.set_baselines(saved)
    assert a2.has_baselines
    for idx in saved:
        assert np.array_equal(a2.get_baselines()[idx], saved[idx])


# --- State determination ---

def test_no_baseline_gives_unknown(analyzer):
    frame = _solid_frame(170, 40, 180)
    results = analyzer.analyze_frame(frame)
    for snap in results:
        assert snap.state == SlotState.UNKNOWN


def test_matching_baseline_gives_ready(analyzer):
    frame = _solid_frame(170, 40, 180)
    analyzer.calibrate_baselines(frame)
    results = analyzer.analyze_frame(frame)
    for snap in results:
        assert snap.state == SlotState.READY


def test_darkened_slot_gives_cooldown(analyzer):
    bright = _solid_frame(170, 40, 200)
    analyzer.calibrate_baselines(bright)
    dark_frame = _slot_darkened_frame(200, 50, 1, analyzer)
    results = analyzer.analyze_frame(dark_frame)
    assert results[1].state == SlotState.ON_COOLDOWN
    assert results[0].state == SlotState.READY


def test_hysteresis_holds_cooldown(analyzer):
    """ON_COOLDOWN slot needs lower fraction to release."""
    bright = _solid_frame(170, 40, 200)
    analyzer.calibrate_baselines(bright)
    dark = _solid_frame(170, 40, 50)
    analyzer.analyze_frame(dark)

    # Moderate darkening: above release threshold (0.15) but below trigger (0.30)
    # Create a frame where ~20% of pixels are darkened
    partial = bright.copy()
    h, w = partial.shape[:2]
    partial[:int(h * 0.25), :, :] = 100
    results = analyzer.analyze_frame(partial)
    for snap in results:
        assert snap.state == SlotState.ON_COOLDOWN


def test_cooldown_min_duration_gcd(analyzer):
    """When cooldown_min_ms > 0, brief cooldowns show GCD first."""
    analyzer.update_config({
        "slot_count": 4, "slot_gap": 2, "slot_padding": 0,
        "bbox_width": 170, "bbox_height": 40,
        "darken_threshold": 30, "trigger_fraction": 0.30,
        "cooldown_min_ms": 5000,
        "cast_detection_enabled": False,
        "detection_region": "full",
    })
    bright = _solid_frame(170, 40, 200)
    analyzer.calibrate_baselines(bright)
    dark = _solid_frame(170, 40, 50)
    results = analyzer.analyze_frame(dark)
    for snap in results:
        assert snap.state == SlotState.GCD


def test_detection_region_top_left():
    """top_left region uses only top-left quadrant for analysis."""
    a = SlotAnalyzer()
    a.update_config({
        "slot_count": 1, "slot_gap": 0, "slot_padding": 0,
        "bbox_width": 40, "bbox_height": 40,
        "darken_threshold": 30, "trigger_fraction": 0.30,
        "cooldown_min_ms": 0, "cast_detection_enabled": False,
        "detection_region": "top_left",
    })
    bright = _solid_frame(40, 40, 200)
    a.calibrate_baselines(bright)

    # Darken only the bottom-right — top_left region should still see bright
    frame = bright.copy()
    frame[20:, 20:, :] = 50
    results = a.analyze_frame(frame)
    assert results[0].state == SlotState.READY

    # Darken the top-left quadrant — should trigger cooldown
    frame2 = bright.copy()
    frame2[:20, :20, :] = 50
    results2 = a.analyze_frame(frame2)
    assert results2[0].state == SlotState.ON_COOLDOWN
