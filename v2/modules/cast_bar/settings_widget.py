"""Cast bar settings — region config, color thresholds, and live preview."""
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


def _capped_row(inner, max_width: int = 420) -> QHBoxLayout:
    container = QWidget()
    container.setLayout(inner)
    container.setMaximumWidth(max_width)
    outer = QHBoxLayout()
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(container)
    outer.addStretch()
    return outer


class CastBarSettings(QWidget):
    """Settings for the cast bar detection module."""

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
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        self._check_enabled = QCheckBox("Enable cast bar detection")
        layout.addWidget(self._check_enabled)

        # Capture region
        region_header = QLabel("CAPTURE REGION")
        region_header.setStyleSheet(
            "font-family: monospace; font-size: 10px; font-weight: bold;"
            " letter-spacing: 1px; color: #7a7a8e; padding-top: 6px;"
        )
        layout.addWidget(region_header)

        from modules.core_capture.region_settings_widget import RegionSettingsWidget
        self._region_widget = RegionSettingsWidget(
            self._core, region_id="cast_bar", show_preview=True,
        )
        layout.addWidget(self._region_widget)

        # Detection thresholds
        thresh_header = QLabel("COLOR DETECTION")
        thresh_header.setStyleSheet(
            "font-family: monospace; font-size: 10px; font-weight: bold;"
            " letter-spacing: 1px; color: #7a7a8e; padding-top: 6px;"
        )
        layout.addWidget(thresh_header)

        LW = 120
        self._spin_hue_min = _spin(0, 179, 15)
        self._spin_hue_max = _spin(0, 179, 45)
        self._spin_sat_min = _spin(0, 255, 80)
        self._spin_val_min = _spin(0, 255, 120)
        self._dspin_fraction = _dspin(0.01, 1.0, 0.15)
        self._spin_confirm = _spin(1, 20, 2)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        grid.addWidget(_label("Hue Min", LW), 0, 0)
        grid.addWidget(self._spin_hue_min, 0, 1)
        grid.addWidget(_label("Hue Max", LW), 0, 2)
        grid.addWidget(self._spin_hue_max, 0, 3)

        grid.addWidget(_label("Saturation Min", LW), 1, 0)
        grid.addWidget(self._spin_sat_min, 1, 1)
        grid.addWidget(_label("Brightness Min", LW), 1, 2)
        grid.addWidget(self._spin_val_min, 1, 3)

        grid.addWidget(_label("Active Fraction", LW), 2, 0)
        grid.addWidget(self._dspin_fraction, 2, 1)
        grid.addWidget(_label("Confirm Frames", LW), 2, 2)
        grid.addWidget(self._spin_confirm, 2, 3)

        layout.addLayout(_capped_row(grid, 520))

        # Progress sub-region
        sub_header = QLabel("PROGRESS BAR SUB-REGION")
        sub_header.setStyleSheet(
            "font-family: monospace; font-size: 10px; font-weight: bold;"
            " letter-spacing: 1px; color: #7a7a8e; padding-top: 6px;"
        )
        layout.addWidget(sub_header)

        self._dspin_sub_x = _dspin(0.0, 1.0, 0.02)
        self._dspin_sub_y = _dspin(0.0, 1.0, 0.15)
        self._dspin_sub_w = _dspin(0.0, 1.0, 0.96)
        self._dspin_sub_h = _dspin(0.0, 1.0, 0.70)

        sub_grid = QGridLayout()
        sub_grid.setHorizontalSpacing(12)
        sub_grid.setVerticalSpacing(6)
        sub_grid.addWidget(_label("X (frac)", LW), 0, 0)
        sub_grid.addWidget(self._dspin_sub_x, 0, 1)
        sub_grid.addWidget(_label("Y (frac)", LW), 0, 2)
        sub_grid.addWidget(self._dspin_sub_y, 0, 3)
        sub_grid.addWidget(_label("W (frac)", LW), 1, 0)
        sub_grid.addWidget(self._dspin_sub_w, 1, 1)
        sub_grid.addWidget(_label("H (frac)", LW), 1, 2)
        sub_grid.addWidget(self._dspin_sub_h, 1, 3)

        layout.addLayout(_capped_row(sub_grid, 520))

        # Status
        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("color: #999; font-size: 11px; padding-top: 4px;")
        layout.addWidget(self._status_label)

        layout.addStretch()

        if self._module_ref:
            from PyQt6.QtCore import Qt as QtConst
            self._module_ref.cast_bar_updated_signal.connect(
                self._on_state_updated, QtConst.ConnectionType.QueuedConnection,
            )

    def _populate(self) -> None:
        cfg = self._read_cfg()
        self._check_enabled.setChecked(bool(cfg.get("enabled", True)))
        self._spin_hue_min.setValue(int(cfg.get("bar_color_hue_min", 15)))
        self._spin_hue_max.setValue(int(cfg.get("bar_color_hue_max", 45)))
        self._spin_sat_min.setValue(int(cfg.get("bar_saturation_min", 80)))
        self._spin_val_min.setValue(int(cfg.get("bar_brightness_min", 120)))
        self._dspin_fraction.setValue(float(cfg.get("active_pixel_fraction", 0.15)))
        self._spin_confirm.setValue(int(cfg.get("confirm_frames", 2)))

        pr = cfg.get("progress_sub_region", {})
        self._dspin_sub_x.setValue(float(pr.get("x", 0.02)))
        self._dspin_sub_y.setValue(float(pr.get("y", 0.15)))
        self._dspin_sub_w.setValue(float(pr.get("w", 0.96)))
        self._dspin_sub_h.setValue(float(pr.get("h", 0.70)))

    def _connect_signals(self) -> None:
        self._check_enabled.toggled.connect(self._save_all)
        for w in (self._spin_hue_min, self._spin_hue_max,
                  self._spin_sat_min, self._spin_val_min, self._spin_confirm):
            w.valueChanged.connect(self._save_all)
        self._dspin_fraction.valueChanged.connect(self._save_all)
        for w in (self._dspin_sub_x, self._dspin_sub_y,
                  self._dspin_sub_w, self._dspin_sub_h):
            w.valueChanged.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["enabled"] = self._check_enabled.isChecked()
        cfg["bar_color_hue_min"] = self._spin_hue_min.value()
        cfg["bar_color_hue_max"] = self._spin_hue_max.value()
        cfg["bar_saturation_min"] = self._spin_sat_min.value()
        cfg["bar_brightness_min"] = self._spin_val_min.value()
        cfg["active_pixel_fraction"] = self._dspin_fraction.value()
        cfg["confirm_frames"] = self._spin_confirm.value()
        cfg["progress_sub_region"] = {
            "x": self._dspin_sub_x.value(),
            "y": self._dspin_sub_y.value(),
            "w": self._dspin_sub_w.value(),
            "h": self._dspin_sub_h.value(),
        }
        self._write_cfg(cfg)

    def _on_state_updated(self, state: Any) -> None:
        if state is None:
            self._status_label.setText("Idle")
            self._status_label.setStyleSheet("color: #999; font-size: 11px;")
            return
        if state.active:
            pct = int(state.progress * 100)
            mode = "Channeling" if state.channeling else "Casting"
            self._status_label.setText(f"{mode} — {pct}%")
            color = "#ffd37a" if state.channeling else "#88ff88"
            self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        else:
            self._status_label.setText("No cast detected")
            self._status_label.setStyleSheet("color: #999; font-size: 11px;")
