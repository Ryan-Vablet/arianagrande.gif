from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.core.config_manager import ConfigManager
from src.core.core import Core


@pytest.fixture
def core(tmp_path):
    cfg = ConfigManager(tmp_path / "config.json")
    cfg.load()
    cfg.set("core_capture", {
        "monitor_index": 1,
        "polling_fps": 60,
        "bounding_box": {"top": 0, "left": 0, "width": 100, "height": 50},
    })
    c = Core(cfg)
    return c


def _register_primary_region(core_obj, callback):
    """Register an action_bar region so the worker has something to capture."""
    core_obj.capture_regions.register(
        id="action_bar",
        owner="core_capture",
        config_namespace="core_capture",
        config_key="bounding_box",
        default_bbox={"top": 0, "left": 0, "width": 100, "height": 50},
        callback=callback,
    )


def _mock_screen_capture():
    mock_sc = MagicMock()
    mock_sc.grab_region.return_value = np.zeros((50, 100, 3), dtype=np.uint8)
    mock_sc.monitor_info = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    return mock_sc


def test_worker_starts_and_stops(core):
    from modules.core_capture.capture_worker import CaptureWorker

    callback = MagicMock()
    _register_primary_region(core, callback)
    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        MockSC.return_value = _mock_screen_capture()
        worker.start()
        time.sleep(0.3)
        worker.stop()

    assert not worker.isRunning()


def test_worker_emits_region_frame(core):
    """Verify region callbacks are invoked by the worker."""
    from modules.core_capture.capture_worker import CaptureWorker

    callback = MagicMock()
    _register_primary_region(core, callback)
    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        MockSC.return_value = _mock_screen_capture()
        worker.start()
        time.sleep(0.3)
        worker.stop()

    assert callback.call_count > 0


def test_worker_calls_region_callback_with_frame(core):
    from modules.core_capture.capture_worker import CaptureWorker

    callback = MagicMock()
    _register_primary_region(core, callback)
    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        MockSC.return_value = _mock_screen_capture()
        worker.start()
        time.sleep(0.3)
        worker.stop()

    assert callback.call_count > 0
    frame_arg = callback.call_args[0][0]
    assert isinstance(frame_arg, np.ndarray)


def test_worker_reads_config(core):
    from modules.core_capture.capture_worker import CaptureWorker

    callback = MagicMock()
    _register_primary_region(core, callback)
    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        mock_sc = _mock_screen_capture()
        MockSC.return_value = mock_sc
        worker.start()
        time.sleep(0.2)
        worker.stop()

    MockSC.assert_called_with(monitor_index=1)
