from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def _label(text: str, width: int = 110) -> QLabel:
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


class _SaveMixin:
    _core: Any
    _key: str

    def _read_cfg(self) -> dict:
        return self._core.get_config(self._key)

    def _write_cfg(self, cfg: dict) -> None:
        self._core.save_config(self._key, cfg)


class BrightnessSettings(_SaveMixin, QWidget):
    """Brightness detection threshold settings — detection/brightness subtab."""

    def __init__(self, core: Any, module_key: str, module_ref: Any, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._module_ref = module_ref
        self._build_ui()
        self._populate()
        self._connect_signals()

    def _build_ui(self) -> None:
        LW = 120

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        self._spin_darken = _spin(1, 255, 40)
        self._dspin_trigger = _dspin(0.01, 1.0, 0.30)
        self._dspin_change = _dspin(0.01, 1.0, 0.30)
        self._combo_region = QComboBox()
        self._combo_region.addItem("Top-Left Quadrant", "top_left")
        self._combo_region.addItem("Full Slot", "full")
        self._combo_region.setMinimumWidth(140)
        self._spin_cd_min = _spin(0, 10000, 2000)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        grid.addWidget(_label("Darken Threshold", LW), 0, 0)
        grid.addWidget(self._spin_darken, 0, 1)

        grid.addWidget(_label("Trigger Fraction", LW), 1, 0)
        grid.addWidget(self._dspin_trigger, 1, 1)

        grid.addWidget(_label("Change Fraction", LW), 2, 0)
        grid.addWidget(self._dspin_change, 2, 1)

        grid.addWidget(_label("Detection Region", LW), 3, 0)
        grid.addWidget(self._combo_region, 3, 1)

        grid.addWidget(_label("Cooldown Min (ms)", LW), 4, 0)
        grid.addWidget(self._spin_cd_min, 4, 1)

        layout.addLayout(_capped_row(grid, 340))
        layout.addStretch()

    def _populate(self) -> None:
        cfg = self._read_cfg()
        self._spin_darken.setValue(int(cfg.get("darken_threshold", 40)))
        self._dspin_trigger.setValue(float(cfg.get("trigger_fraction", 0.30)))
        self._dspin_change.setValue(float(cfg.get("change_fraction", 0.30)))

        region = cfg.get("detection_region", "top_left")
        idx = self._combo_region.findData(region)
        if idx >= 0:
            self._combo_region.setCurrentIndex(idx)

        self._spin_cd_min.setValue(int(cfg.get("cooldown_min_ms", 2000)))

    def _connect_signals(self) -> None:
        for w in (self._spin_darken, self._spin_cd_min):
            w.valueChanged.connect(self._save_all)
        for w in (self._dspin_trigger, self._dspin_change):
            w.valueChanged.connect(self._save_all)
        self._combo_region.currentIndexChanged.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["darken_threshold"] = self._spin_darken.value()
        cfg["trigger_fraction"] = self._dspin_trigger.value()
        cfg["change_fraction"] = self._dspin_change.value()
        cfg["detection_region"] = self._combo_region.currentData() or "top_left"
        cfg["cooldown_min_ms"] = self._spin_cd_min.value()
        self._write_cfg(cfg)
        if self._module_ref:
            self._module_ref._sync_config_to_analyzer()


def _slot_btn_style(color: str) -> str:
    return (
        f"QPushButton {{ background: {color}; color: white;"
        f" border: 1px solid #555; border-radius: 4px;"
        f" font-size: 11px; font-weight: bold; font-family: monospace;"
        f" padding: 2px 0px; }}"
    )


_SLOT_UNKNOWN_COLOR = "#444455"
_SLOT_CALIBRATED_COLOR = "#336633"


class CalibrationSettings(_SaveMixin, QWidget):
    """Baseline calibration controls — detection/calibration subtab."""

    def __init__(self, core: Any, module_key: str, module_ref: Any, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._module_ref = module_ref
        self._slot_buttons: list[QPushButton] = []
        self._preview_label: QLabel | None = None
        self._build_ui()
        self._update_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        self._status_label = QLabel("Baselines: not calibrated")
        self._status_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        self._btn_calibrate_all = QPushButton("Calibrate All Baselines")
        self._btn_calibrate_all.clicked.connect(self._on_calibrate_all)
        btn_row.addWidget(self._btn_calibrate_all)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._result_label = QLabel("")
        self._result_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._result_label)

        # Live preview
        preview_header = QLabel("LIVE PREVIEW")
        preview_header.setStyleSheet(
            "font-family: monospace; font-size: 10px; font-weight: bold;"
            " letter-spacing: 1px; color: #7a7a8e; padding-top: 6px;"
        )
        layout.addWidget(preview_header)

        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(50)
        self._preview_label.setStyleSheet(
            "background: #1a1a2a; border: 1px solid #3a3a4a; border-radius: 3px;"
        )
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setText("Start capture to see preview")
        layout.addWidget(self._preview_label)

        # Per-slot recalibrate buttons
        slot_header = QLabel("PER-SLOT RECALIBRATE")
        slot_header.setStyleSheet(
            "font-family: monospace; font-size: 10px; font-weight: bold;"
            " letter-spacing: 1px; color: #7a7a8e; padding-top: 6px;"
        )
        layout.addWidget(slot_header)

        self._slot_row_layout = QHBoxLayout()
        self._slot_row_layout.setSpacing(4)
        self._populate_slot_buttons()
        layout.addLayout(self._slot_row_layout)

        layout.addStretch()

    def _populate_slot_buttons(self) -> None:
        cc_cfg = self._core.get_config("core_capture")
        slot_count = cc_cfg.get("slots", {}).get("count", 10)
        calibrated = set()
        if self._module_ref and self._module_ref._analyzer:
            calibrated = set(self._module_ref._analyzer.get_baselines().keys())

        for i in range(slot_count):
            color = _SLOT_CALIBRATED_COLOR if i in calibrated else _SLOT_UNKNOWN_COLOR
            btn = QPushButton(str(i + 1))
            btn.setMinimumHeight(28)
            btn.setStyleSheet(_slot_btn_style(color))
            btn.setToolTip(f"Recalibrate slot {i + 1}")
            btn.clicked.connect(lambda checked, idx=i: self._on_calibrate_slot(idx))
            self._slot_buttons.append(btn)
            self._slot_row_layout.addWidget(btn, 1)

    def update_preview(self, qimg: "QImage") -> None:
        if self._preview_label and not qimg.isNull():
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap.fromImage(qimg)
            avail_w = max(50, self._preview_label.width() - 4)
            scaled = pixmap.scaledToWidth(
                avail_w, Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(scaled)

    def _update_status(self) -> None:
        if self._module_ref and self._module_ref._analyzer:
            baselines = self._module_ref._analyzer.get_baselines()
            cc_cfg = self._core.get_config("core_capture")
            total = cc_cfg.get("slots", {}).get("count", 10)
            count = len(baselines)
            if count > 0:
                self._status_label.setText(f"Baselines: calibrated ({count}/{total} slots)")
                self._status_label.setStyleSheet("color: #88ff88; font-size: 11px;")
            else:
                self._status_label.setText("Baselines: not calibrated")
                self._status_label.setStyleSheet("color: #999; font-size: 11px;")
            self._refresh_button_colors()

    def _refresh_button_colors(self) -> None:
        calibrated = set()
        if self._module_ref and self._module_ref._analyzer:
            calibrated = set(self._module_ref._analyzer.get_baselines().keys())
        for i, btn in enumerate(self._slot_buttons):
            color = _SLOT_CALIBRATED_COLOR if i in calibrated else _SLOT_UNKNOWN_COLOR
            btn.setStyleSheet(_slot_btn_style(color))

    def _on_calibrate_all(self) -> None:
        if not self._module_ref:
            return
        ok, msg = self._module_ref.calibrate_all_baselines()
        color = "#88ff88" if ok else "#ff6666"
        self._result_label.setText(msg)
        self._result_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._update_status()

    def _on_calibrate_slot(self, slot_index: int) -> None:
        if not self._module_ref:
            return
        ok, msg = self._module_ref.calibrate_single_slot(slot_index)
        color = "#88ff88" if ok else "#ff6666"
        self._result_label.setText(msg)
        self._result_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._update_status()
