from __future__ import annotations

import numpy as np
import pytest

from modules.cast_bar.cast_bar_analyzer import CastBarAnalyzer, CastBarState


@pytest.fixture
def analyzer():
    a = CastBarAnalyzer()
    a.update_config({
        "bar_color_hue_min": 15,
        "bar_color_hue_max": 45,
        "bar_saturation_min": 80,
        "bar_brightness_min": 120,
        "active_pixel_fraction": 0.15,
        "confirm_frames": 2,
        "progress_sub_region": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
    })
    return a


def _make_bar_frame(w: int = 200, h: int = 30, fill_fraction: float = 0.0) -> np.ndarray:
    """Create a synthetic cast bar frame (BGR).

    Filled portion is a WoW-like orange/yellow color; unfilled is near-black.
    """
    import cv2

    frame = np.zeros((h, w, 3), dtype=np.uint8)
    fill_w = int(w * fill_fraction)
    if fill_w > 0:
        hsv_bar = np.zeros((h, fill_w, 3), dtype=np.uint8)
        hsv_bar[:, :, 0] = 25  # hue in WoW cast bar range
        hsv_bar[:, :, 1] = 200  # high saturation
        hsv_bar[:, :, 2] = 200  # high value
        bgr_bar = cv2.cvtColor(hsv_bar, cv2.COLOR_HSV2BGR)
        frame[:, :fill_w, :] = bgr_bar
    return frame


class TestBasicDetection:
    def test_empty_frame_returns_inactive(self, analyzer):
        frame = _make_bar_frame(fill_fraction=0.0)
        state = analyzer.analyze(frame)
        assert state.active is False
        assert state.progress == 0.0

    def test_full_bar_activates_after_confirm_frames(self, analyzer):
        frame = _make_bar_frame(fill_fraction=0.8)
        s1 = analyzer.analyze(frame)
        assert s1.active is False  # first frame, not yet confirmed
        s2 = analyzer.analyze(frame)
        assert s2.active is True  # second frame confirms

    def test_progress_reflects_fill_fraction(self, analyzer):
        frame = _make_bar_frame(fill_fraction=0.5)
        analyzer.analyze(frame)
        state = analyzer.analyze(frame)
        assert state.active is True
        assert 0.4 <= state.progress <= 0.6

    def test_bar_disappearing_deactivates(self, analyzer):
        filled = _make_bar_frame(fill_fraction=0.8)
        analyzer.analyze(filled)
        analyzer.analyze(filled)
        assert analyzer.analyze(filled).active is True

        empty = _make_bar_frame(fill_fraction=0.0)
        state = analyzer.analyze(empty)
        assert state.active is False


class TestProgressMeasurement:
    def test_full_bar_near_100(self, analyzer):
        frame = _make_bar_frame(fill_fraction=1.0)
        analyzer.analyze(frame)
        state = analyzer.analyze(frame)
        assert state.progress >= 0.95

    def test_quarter_bar(self, analyzer):
        frame = _make_bar_frame(fill_fraction=0.25)
        analyzer.analyze(frame)
        state = analyzer.analyze(frame)
        assert 0.2 <= state.progress <= 0.35

    def test_zero_progress_when_inactive(self, analyzer):
        frame = _make_bar_frame(fill_fraction=0.0)
        state = analyzer.analyze(frame)
        assert state.progress == 0.0


class TestChanneling:
    def test_decreasing_progress_flags_channeling(self, analyzer):
        full = _make_bar_frame(fill_fraction=0.9)
        analyzer.analyze(full)
        analyzer.analyze(full)  # confirm
        assert analyzer.analyze(full).active is True

        partial = _make_bar_frame(fill_fraction=0.4)
        state = analyzer.analyze(partial)
        assert state.channeling is True

    def test_increasing_progress_not_channeling(self, analyzer):
        half = _make_bar_frame(fill_fraction=0.3)
        analyzer.analyze(half)
        analyzer.analyze(half)

        more = _make_bar_frame(fill_fraction=0.6)
        state = analyzer.analyze(more)
        assert state.channeling is False


class TestConfigUpdate:
    def test_higher_confirm_frames_delays_activation(self, analyzer):
        analyzer.update_config({"confirm_frames": 5})
        frame = _make_bar_frame(fill_fraction=0.8)
        for _ in range(4):
            assert analyzer.analyze(frame).active is False
        assert analyzer.analyze(frame).active is True

    def test_higher_fraction_threshold_requires_more_bar(self, analyzer):
        analyzer.update_config({"active_pixel_fraction": 0.5})
        small = _make_bar_frame(fill_fraction=0.3)
        analyzer.analyze(small)
        state = analyzer.analyze(small)
        assert state.active is False

        big = _make_bar_frame(fill_fraction=0.8)
        analyzer.analyze(big)
        state = analyzer.analyze(big)
        assert state.active is True


class TestReset:
    def test_reset_clears_state(self, analyzer):
        frame = _make_bar_frame(fill_fraction=0.8)
        analyzer.analyze(frame)
        analyzer.analyze(frame)
        assert analyzer.analyze(frame).active is True

        analyzer.reset()
        state = analyzer.analyze(frame)
        assert state.active is False  # needs to re-confirm


class TestEdgeCases:
    def test_tiny_frame(self, analyzer):
        frame = np.zeros((1, 1, 3), dtype=np.uint8)
        state = analyzer.analyze(frame)
        assert state.active is False

    def test_state_has_timestamp(self, analyzer):
        frame = _make_bar_frame()
        state = analyzer.analyze(frame)
        assert state.timestamp > 0

    def test_sub_region_config(self, analyzer):
        analyzer.update_config({
            "progress_sub_region": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8}
        })
        frame = _make_bar_frame(fill_fraction=0.8)
        analyzer.analyze(frame)
        state = analyzer.analyze(frame)
        assert state.active is True
