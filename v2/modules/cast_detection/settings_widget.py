from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def _label(text: str, width: int = 120) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #999; font-size: 11px;")
    lbl.setMinimumWidth(width)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _spin(min_val: int, max_val: int, value: int = 0) -> QSpinBox:
    s = QSpinBox()
    s.setRange(min_val, max_val)
    s.setValue(value)
    s.setMinimumWidth(70)
    s.setMaximumWidth(100)
    return s


def _dspin(min_val: float, max_val: float, value: float = 0.0, step: float = 0.01) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(min_val, max_val)
    s.setValue(value)
    s.setSingleStep(step)
    s.setDecimals(2)
    s.setMinimumWidth(70)
    s.setMaximumWidth(100)
    return s


def _capped_row(inner_layout: QVBoxLayout | QHBoxLayout | QGridLayout, max_width: int = 420) -> QHBoxLayout:
    container = QWidget()
    container.setLayout(inner_layout)
    container.setMaximumWidth(max_width)
    outer = QHBoxLayout()
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(container)
    outer.addStretch()
    return outer


class CastDetectionSettings(QWidget):
    """Cast detection threshold and timing settings — detection/cast subtab."""

    def __init__(self, core: Any, module_key: str, module_ref: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core = core
        self._key = module_key
        self._module_ref = module_ref
        self._build_ui()
        self._populate()
        self._connect_signals()

    def _read_cfg(self) -> dict:
        return self._core.get_config(self._key)

    def _write_cfg(self, cfg: dict) -> None:
        self._core.save_config(self._key, cfg)

    def _build_ui(self) -> None:
        LW = 120

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        self._check_cast = QCheckBox("Enable cast detection")
        layout.addWidget(self._check_cast)

        self._dspin_cast_min = _dspin(0.0, 1.0, 0.05)
        self._dspin_cast_max = _dspin(0.0, 1.0, 0.22)
        self._spin_cast_confirm = _spin(1, 20, 2)
        self._spin_cast_min_ms = _spin(0, 10000, 150)
        self._spin_cast_max_ms = _spin(0, 30000, 3000)
        self._spin_cast_grace = _spin(0, 5000, 120)
        self._check_channeling = QCheckBox("Enable channeling")

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        grid.addWidget(_label("Cast Min Frac", LW), 0, 0)
        grid.addWidget(self._dspin_cast_min, 0, 1)
        grid.addWidget(_label("Cast Max Frac", LW), 0, 2)
        grid.addWidget(self._dspin_cast_max, 0, 3)

        grid.addWidget(_label("Confirm Frames", LW), 1, 0)
        grid.addWidget(self._spin_cast_confirm, 1, 1)

        grid.addWidget(_label("Cast Min (ms)", LW), 2, 0)
        grid.addWidget(self._spin_cast_min_ms, 2, 1)
        grid.addWidget(_label("Cast Max (ms)", LW), 2, 2)
        grid.addWidget(self._spin_cast_max_ms, 2, 3)

        grid.addWidget(_label("Cancel Grace (ms)", LW), 3, 0)
        grid.addWidget(self._spin_cast_grace, 3, 1)

        layout.addLayout(_capped_row(grid, 520))
        layout.addWidget(self._check_channeling)
        layout.addStretch()

    def _populate(self) -> None:
        cfg = self._read_cfg()
        self._check_cast.setChecked(bool(cfg.get("cast_detection_enabled", True)))
        self._dspin_cast_min.setValue(float(cfg.get("cast_min_fraction", 0.05)))
        self._dspin_cast_max.setValue(float(cfg.get("cast_max_fraction", 0.22)))
        self._spin_cast_confirm.setValue(int(cfg.get("cast_confirm_frames", 2)))
        self._spin_cast_min_ms.setValue(int(cfg.get("cast_min_ms", 150)))
        self._spin_cast_max_ms.setValue(int(cfg.get("cast_max_ms", 3000)))
        self._spin_cast_grace.setValue(int(cfg.get("cast_cancel_grace_ms", 120)))
        self._check_channeling.setChecked(bool(cfg.get("channeling_enabled", True)))

    def _connect_signals(self) -> None:
        for w in (self._spin_cast_confirm, self._spin_cast_min_ms,
                   self._spin_cast_max_ms, self._spin_cast_grace):
            w.valueChanged.connect(self._save_all)
        for w in (self._dspin_cast_min, self._dspin_cast_max):
            w.valueChanged.connect(self._save_all)
        self._check_cast.toggled.connect(self._save_all)
        self._check_channeling.toggled.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["cast_detection_enabled"] = self._check_cast.isChecked()
        cfg["cast_min_fraction"] = self._dspin_cast_min.value()
        cfg["cast_max_fraction"] = self._dspin_cast_max.value()
        cfg["cast_confirm_frames"] = self._spin_cast_confirm.value()
        cfg["cast_min_ms"] = self._spin_cast_min_ms.value()
        cfg["cast_max_ms"] = self._spin_cast_max_ms.value()
        cfg["cast_cancel_grace_ms"] = self._spin_cast_grace.value()
        cfg["channeling_enabled"] = self._check_channeling.isChecked()
        self._write_cfg(cfg)
