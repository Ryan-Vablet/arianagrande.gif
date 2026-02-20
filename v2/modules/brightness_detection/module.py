from __future__ import annotations

import base64
import logging
from abc import ABCMeta
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal

from src.core.base_module import BaseModule

logger = logging.getLogger(__name__)


class _CombinedMeta(type(QObject), ABCMeta):
    pass


class BrightnessDetectionModule(QObject, BaseModule, metaclass=_CombinedMeta):
    """Brightness-based cooldown detection.

    Receives frames from core_capture, analyzes per-slot brightness
    against baselines, publishes slot states.
    """

    name = "Brightness Detection"
    key = "brightness_detection"
    version = "1.0.0"
    description = "Detects slot cooldown states by comparing brightness to calibrated baselines"
    requires: list[str] = ["core_capture"]
    optional: list[str] = ["cast_bar"]
    provides_services = ["slot_states", "baselines_calibrated"]
    hooks = ["slot_states_updated"]

    slot_states_updated_signal = pyqtSignal(list)

    def __init__(self) -> None:
        QObject.__init__(self)
        BaseModule.__init__(self)
        self._analyzer: Any = None
        self._latest_states: list[dict] = []

    def setup(self, core: Any) -> None:
        super().setup(core)
        from modules.brightness_detection.analyzer import SlotAnalyzer

        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())

        self._analyzer = SlotAnalyzer()
        self._sync_config_to_analyzer()

        core.panels.register(
            id=f"{self.key}/slot_status",
            area="primary",
            factory=self._build_status_widget,
            title="Slot States",
            owner=self.key,
            order=10,
        )

        core.settings.register(
            path="detection/brightness",
            factory=self._build_settings,
            title="Brightness Detection",
            owner=self.key,
            order=30,
        )

        core.settings.register(
            path="detection/calibration",
            factory=self._build_calibration_settings,
            title="Calibration",
            owner=self.key,
            order=40,
        )

        core.subscribe("config.changed", self._on_config_changed)

    def ready(self) -> None:
        cfg = self.core.get_config(self.key)
        saved = cfg.get("slot_baselines")
        if saved and self._analyzer:
            try:
                decoded = self._decode_baselines(saved)
                if decoded:
                    self._analyzer.set_baselines(decoded)
            except Exception as e:
                logger.warning("Could not load baselines: %s", e)

    def on_frame(self, frame: np.ndarray) -> None:
        if self._analyzer is None:
            return

        cast_gate = True
        if self.core.is_loaded("cast_bar"):
            gate = self.core.get_service("cast_bar", "cast_gate_active")
            if gate is not None:
                cast_gate = bool(gate)

        snapshots = self._analyzer.analyze_frame(frame, cast_gate_active=cast_gate)

        states = []
        for s in snapshots:
            states.append({
                "index": s.index,
                "state": s.state.value,
                "darkened_fraction": s.darkened_fraction,
                "changed_fraction": s.changed_fraction,
                "timestamp": s.timestamp,
            })

        self._latest_states = states
        self.slot_states_updated_signal.emit(states)
        self.core.emit(f"{self.key}.slot_states_updated", states=states)

    def get_service(self, name: str) -> Any:
        if name == "slot_states":
            return self._latest_states
        if name == "baselines_calibrated":
            return self._analyzer.has_baselines if self._analyzer else False
        return None

    def _on_config_changed(self, namespace: str = "") -> None:
        if namespace in (self.key, "core_capture"):
            self._sync_config_to_analyzer()

    def on_config_changed(self, key: str, value: Any) -> None:
        self._sync_config_to_analyzer()

    def _sync_config_to_analyzer(self) -> None:
        if not self._analyzer or not self.core:
            return
        cc_cfg = self.core.get_config("core_capture")
        bd_cfg = self.core.get_config(self.key)
        bb = cc_cfg.get("bounding_box", {})
        slots = cc_cfg.get("slots", {})
        merged = {
            "bbox_width": bb.get("width", 400),
            "bbox_height": bb.get("height", 50),
            "slot_count": slots.get("count", 10),
            "slot_gap": slots.get("gap", 2),
            "slot_padding": slots.get("padding", 3),
            **bd_cfg,
        }
        self._analyzer.update_config(merged)

    def _default_config(self) -> dict:
        return {
            "darken_threshold": 40,
            "trigger_fraction": 0.30,
            "change_fraction": 0.30,
            "change_ignore_slots": [],
            "detection_region": "top_left",
            "detection_region_overrides": {},
            "cooldown_min_ms": 2000,
            "cast_detection_enabled": True,
            "cast_min_fraction": 0.05,
            "cast_max_fraction": 0.22,
            "cast_confirm_frames": 2,
            "cast_min_ms": 150,
            "cast_max_ms": 3000,
            "cast_cancel_grace_ms": 120,
            "channeling_enabled": True,
            "slot_baselines": [],
            "slot_display_names": [],
        }

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def calibrate_all_baselines(self) -> tuple[bool, str]:
        if not self._analyzer:
            return False, "Analyzer not initialized"
        if not self.core.get_service("core_capture", "capture_running"):
            return False, "Capture not running"

        from src.capture.screen_capture import ScreenCapture
        from src.models import BoundingBox

        cc_cfg = self.core.get_config("core_capture")
        capture = ScreenCapture(monitor_index=int(cc_cfg.get("monitor_index", 1)))
        capture.start()
        try:
            bbox = BoundingBox.from_dict(cc_cfg.get("bounding_box", {}))
            frame = capture.grab_region(bbox)
            self._analyzer.calibrate_baselines(frame)
            self._save_baselines()
            return True, f"Calibrated {len(self._analyzer.get_baselines())} slots ✓"
        except Exception as e:
            return False, str(e)
        finally:
            capture.stop()

    def calibrate_single_slot(self, slot_index: int) -> tuple[bool, str]:
        if not self._analyzer:
            return False, "Analyzer not initialized"

        from src.capture.screen_capture import ScreenCapture
        from src.models import BoundingBox

        cc_cfg = self.core.get_config("core_capture")
        capture = ScreenCapture(monitor_index=int(cc_cfg.get("monitor_index", 1)))
        capture.start()
        try:
            bbox = BoundingBox.from_dict(cc_cfg.get("bounding_box", {}))
            frame = capture.grab_region(bbox)
            self._analyzer.calibrate_single_slot(frame, slot_index)
            self._save_baselines()
            return True, f"Slot {slot_index} calibrated ✓"
        except Exception as e:
            return False, str(e)
        finally:
            capture.stop()

    def _save_baselines(self) -> None:
        if not self._analyzer:
            return
        encoded = self._encode_baselines(self._analyzer.get_baselines())
        cfg = self.core.get_config(self.key)
        cfg["slot_baselines"] = encoded
        self.core.save_config(self.key, cfg)

    @staticmethod
    def _encode_baselines(baselines: dict[int, np.ndarray]) -> list[dict]:
        result = []
        for idx, arr in baselines.items():
            b64 = base64.b64encode(arr.tobytes()).decode("ascii")
            result.append({"index": idx, "data": b64, "shape": list(arr.shape)})
        return result

    @staticmethod
    def _decode_baselines(data: list[dict]) -> dict[int, np.ndarray]:
        result = {}
        for item in data:
            idx = int(item["index"])
            shape = tuple(item["shape"])
            arr = np.frombuffer(
                base64.b64decode(item["data"]), dtype=np.uint8,
            ).reshape(shape)
            result[idx] = arr
        return result

    def teardown(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Widget builders
    # ------------------------------------------------------------------

    def _build_status_widget(self) -> Any:
        from modules.brightness_detection.status_widget import SlotStatusWidget
        widget = SlotStatusWidget(self.core, self.key)
        self.slot_states_updated_signal.connect(
            widget.update_states, Qt.ConnectionType.QueuedConnection,
        )
        return widget

    def _build_settings(self) -> Any:
        from modules.brightness_detection.settings_widget import BrightnessSettings
        return BrightnessSettings(self.core, self.key, self)

    def _build_calibration_settings(self) -> Any:
        from modules.brightness_detection.settings_widget import CalibrationSettings
        return CalibrationSettings(self.core, self.key, self)
