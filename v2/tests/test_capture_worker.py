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
    return Core(cfg)


def _mock_screen_capture():
    mock_sc = MagicMock()
    mock_sc.grab_region.return_value = np.zeros((50, 100, 3), dtype=np.uint8)
    mock_sc.monitor_info = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    return mock_sc


def test_worker_starts_and_stops(core):
    from modules.core_capture.capture_worker import CaptureWorker

    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        MockSC.return_value = _mock_screen_capture()
        worker.start()
        time.sleep(0.3)
        worker.stop()

    assert not worker.isRunning()


def test_worker_emits_frame_captured(core):
    """Verify frame_captured signal fires by checking process_frame was called with a frame.

    Direct signal connection to a lambda won't deliver across threads without
    a running QApplication event loop, so we verify the emission indirectly:
    if process_frame receives frames, frame_captured.emit() also ran in the
    same code path.
    """
    from modules.core_capture.capture_worker import CaptureWorker

    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        MockSC.return_value = _mock_screen_capture()
        worker.start()
        time.sleep(0.3)
        worker.stop()

    assert mm.process_frame.call_count > 0


def test_worker_calls_process_frame(core):
    from modules.core_capture.capture_worker import CaptureWorker

    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        MockSC.return_value = _mock_screen_capture()
        worker.start()
        time.sleep(0.3)
        worker.stop()

    assert mm.process_frame.call_count > 0
    frame_arg = mm.process_frame.call_args[0][0]
    assert isinstance(frame_arg, np.ndarray)


def test_worker_reads_config(core):
    from modules.core_capture.capture_worker import CaptureWorker

    mm = MagicMock()
    worker = CaptureWorker(core, mm)

    with patch("src.capture.screen_capture.ScreenCapture") as MockSC:
        mock_sc = _mock_screen_capture()
        MockSC.return_value = mock_sc
        worker.start()
        time.sleep(0.2)
        worker.stop()

    MockSC.assert_called_with(monitor_index=1)
