"""Cast detection module — post-processes brightness slot states with cast/channeling logic."""
from __future__ import annotations

import logging
from abc import ABCMeta
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal

from src.core.base_module import BaseModule

logger = logging.getLogger(__name__)


class _CombinedMeta(type(QObject), ABCMeta):
    pass


class CastDetectionModule(QObject, BaseModule, metaclass=_CombinedMeta):
    """Detects CASTING / CHANNELING states by post-processing brightness data.

    Subscribes to brightness_detection slot states, applies a temporal cast
    state machine based on intermediate darkened fractions, and re-publishes
    augmented states for downstream consumers (automation, UI).
    """

    name = "Cast Detection"
    key = "cast_detection"
    version = "1.0.0"
    description = "Detects casting and channeling states from intermediate brightness changes"
    requires: list[str] = ["brightness_detection"]
    optional: list[str] = ["cast_bar"]
    provides_services = ["slot_states"]
    hooks = ["slot_states_updated"]

    slot_states_updated_signal = pyqtSignal(list)

    def __init__(self) -> None:
        QObject.__init__(self)
        BaseModule.__init__(self)
        self._engine: Any = None
        self._latest_states: list[dict] = []

    def setup(self, core: Any) -> None:
        super().setup(core)
        from modules.cast_detection.cast_engine import CastEngine

        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())

        self._engine = CastEngine()
        self._sync_config_to_engine()

        core.settings.register(
            path="detection/cast",
            factory=self._build_settings,
            title="Cast Detection",
            owner=self.key,
            order=35,
        )

        core.subscribe("config.changed", self._on_config_changed)

    def on_frame(self, frame: np.ndarray) -> None:
        if self._engine is None:
            return

        raw_states = self.core.get_service("brightness_detection", "slot_states") or []
        if not raw_states:
            return

        cast_gate = True
        if self.core.is_loaded("cast_bar"):
            gate = self.core.get_service("cast_bar", "cast_gate_active")
            if gate is not None:
                cast_gate = bool(gate)

        processed = self._engine.process_states(raw_states, cast_gate_active=cast_gate)

        self._latest_states = processed
        self.slot_states_updated_signal.emit(processed)
        self.core.emit(f"{self.key}.slot_states_updated", states=processed)

    def get_service(self, name: str) -> Any:
        if name == "slot_states":
            return self._latest_states
        return None

    def _on_config_changed(self, namespace: str = "") -> None:
        if namespace == self.key:
            self._sync_config_to_engine()

    def _sync_config_to_engine(self) -> None:
        if not self._engine or not self.core:
            return
        cfg = self.core.get_config(self.key)
        self._engine.update_config(cfg)

    def _default_config(self) -> dict:
        return {
            "cast_detection_enabled": True,
            "cast_min_fraction": 0.05,
            "cast_max_fraction": 0.22,
            "cast_confirm_frames": 2,
            "cast_min_ms": 150,
            "cast_max_ms": 3000,
            "cast_cancel_grace_ms": 120,
            "channeling_enabled": True,
        }

    def teardown(self) -> None:
        pass

    def _build_settings(self) -> Any:
        from modules.cast_detection.settings_widget import CastDetectionSettings
        return CastDetectionSettings(self.core, self.key, self)
