from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def _label(text: str, width: int = 80) -> QLabel:
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


def _field_pair(label: QLabel, spin: QSpinBox) -> QHBoxLayout:
    """Label + spinbox packed tight, for use inside grid cells."""
    row = QHBoxLayout()
    row.setSpacing(4)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(label)
    row.addWidget(spin)
    return row


def _capped_row(inner_layout: QVBoxLayout | QHBoxLayout | QGridLayout, max_width: int = 380) -> QHBoxLayout:
    """Wrap a layout in a fixed-max-width container so it doesn't stretch with the panel."""
    container = QWidget()
    container.setLayout(inner_layout)
    container.setMaximumWidth(max_width)
    outer = QHBoxLayout()
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(container)
    outer.addStretch()
    return outer


class _SaveMixin:
    """Shared save logic — reads all widgets, builds full config, writes back."""

    _core: Any
    _key: str

    def _save_all(self) -> None:
        """Must be implemented by each widget to gather its own fields."""
        raise NotImplementedError

    def _read_cfg(self) -> dict:
        return self._core.get_config(self._key)

    def _write_cfg(self, cfg: dict) -> None:
        self._core.save_config(self._key, cfg)


class CaptureRegionSettings(_SaveMixin, QWidget):
    """Bounding box coordinates."""

    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._build_ui()
        self._populate()
        self._connect_signals()

    def _build_ui(self) -> None:
        LW = 55

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        self._spin_top = _spin(0, 9999)
        self._spin_left = _spin(0, 9999)
        self._spin_width = _spin(1, 9999)
        self._spin_height = _spin(1, 9999)
        self._spin_fps = _spin(5, 120, 20)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)

        grid.addWidget(_label("Top", LW), 0, 0)
        grid.addWidget(self._spin_top, 0, 1)
        grid.addWidget(_label("Left", LW), 0, 2)
        grid.addWidget(self._spin_left, 0, 3)

        grid.addWidget(_label("Width", LW), 1, 0)
        grid.addWidget(self._spin_width, 1, 1)
        grid.addWidget(_label("Height", LW), 1, 2)
        grid.addWidget(self._spin_height, 1, 3)

        grid.addWidget(_label("Poll FPS", LW), 2, 0)
        grid.addWidget(self._spin_fps, 2, 1)

        layout.addLayout(_capped_row(grid, 360))
        layout.addStretch()

    def _populate(self) -> None:
        cfg = self._read_cfg()
        bb = cfg.get("bounding_box", {})
        self._spin_top.setValue(int(bb.get("top", 900)))
        self._spin_left.setValue(int(bb.get("left", 500)))
        self._spin_width.setValue(int(bb.get("width", 400)))
        self._spin_height.setValue(int(bb.get("height", 50)))
        self._spin_fps.setValue(int(cfg.get("polling_fps", 20)))

    def _connect_signals(self) -> None:
        self._spin_top.valueChanged.connect(self._save_all)
        self._spin_left.valueChanged.connect(self._save_all)
        self._spin_width.valueChanged.connect(self._save_all)
        self._spin_height.valueChanged.connect(self._save_all)
        self._spin_fps.valueChanged.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["polling_fps"] = self._spin_fps.value()
        cfg["bounding_box"] = {
            "top": self._spin_top.value(),
            "left": self._spin_left.value(),
            "width": self._spin_width.value(),
            "height": self._spin_height.value(),
        }
        self._write_cfg(cfg)


class SlotLayoutSettings(_SaveMixin, QWidget):
    """Slot count, gap, padding."""

    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._build_ui()
        self._populate()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        self._spin_slot_count = _spin(1, 100)
        self._spin_slot_gap = _spin(0, 50)
        self._spin_slot_padding = _spin(0, 50)

        slot_row = QHBoxLayout()
        slot_row.setSpacing(16)
        slot_row.addLayout(_field_pair(_label("Count", 50), self._spin_slot_count))
        slot_row.addLayout(_field_pair(_label("Gap px", 50), self._spin_slot_gap))
        slot_row.addLayout(_field_pair(_label("Pad px", 50), self._spin_slot_padding))
        layout.addLayout(_capped_row(slot_row, 460))

        layout.addStretch()

    def _populate(self) -> None:
        cfg = self._read_cfg()
        slots = cfg.get("slots", {})
        self._spin_slot_count.setValue(int(slots.get("count", 10)))
        self._spin_slot_gap.setValue(int(slots.get("gap", 2)))
        self._spin_slot_padding.setValue(int(slots.get("padding", 3)))

    def _connect_signals(self) -> None:
        self._spin_slot_count.valueChanged.connect(self._save_all)
        self._spin_slot_gap.valueChanged.connect(self._save_all)
        self._spin_slot_padding.valueChanged.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["slots"] = {
            "count": self._spin_slot_count.value(),
            "gap": self._spin_slot_gap.value(),
            "padding": self._spin_slot_padding.value(),
        }
        self._write_cfg(cfg)


class DisplayOverlaySettings(_SaveMixin, QWidget):
    """Monitor selection, overlay toggles, always-on-top."""

    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._build_ui()
        self._populate()
        self._connect_signals()

    def _build_ui(self) -> None:
        LW = 65

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        self._combo_monitor = QComboBox()
        self._combo_monitor.setMinimumWidth(160)
        self._load_monitors()

        self._check_aot = QCheckBox("Always on top")

        monitor_row = QHBoxLayout()
        monitor_row.setSpacing(14)
        monitor_row.addWidget(_label("Monitor", LW))
        monitor_row.addWidget(self._combo_monitor)
        monitor_row.addWidget(self._check_aot)
        monitor_row.addStretch()
        layout.addLayout(monitor_row)

        self._check_overlay = QCheckBox("Show capture overlay")
        self._check_outline = QCheckBox("Show active screen outline")

        layout.addWidget(self._check_overlay)
        layout.addWidget(self._check_outline)
        layout.addStretch()

    def _load_monitors(self) -> None:
        try:
            from src.capture.screen_capture import ScreenCapture
            sc = ScreenCapture(monitor_index=1)
            sc.start()
            monitors = sc.list_monitors()
            sc.stop()
            for i, mon in enumerate(monitors):
                idx = i + 1
                w, h = mon.get("width", "?"), mon.get("height", "?")
                self._combo_monitor.addItem(f"Monitor {idx}  ({w}x{h})", idx)
        except Exception as e:
            logger.warning("Failed to list monitors: %s", e)
            self._combo_monitor.addItem("Monitor 1", 1)

    def _populate(self) -> None:
        cfg = self._read_cfg()
        monitor_index = int(cfg.get("monitor_index", 1))
        for i in range(self._combo_monitor.count()):
            if self._combo_monitor.itemData(i) == monitor_index:
                self._combo_monitor.setCurrentIndex(i)
                break
        display = cfg.get("display", {})
        self._check_aot.setChecked(bool(display.get("always_on_top", False)))
        overlay = cfg.get("overlay", {})
        self._check_overlay.setChecked(bool(overlay.get("enabled", False)))
        self._check_outline.setChecked(bool(overlay.get("show_active_screen_outline", False)))

    def _connect_signals(self) -> None:
        self._combo_monitor.currentIndexChanged.connect(self._save_all)
        self._check_aot.toggled.connect(self._save_all)
        self._check_overlay.toggled.connect(self._on_overlay_toggled)
        self._check_outline.toggled.connect(self._save_all)

        self._core.subscribe(
            "window.visibility_changed", self._on_window_visibility_changed
        )
        self._core.subscribe("config.changed", self._on_config_changed)

    def _on_config_changed(self, namespace: str = "") -> None:
        if namespace != self._key:
            return
        cfg = self._read_cfg()
        aot = cfg.get("display", {}).get("always_on_top", False)
        if aot != self._check_aot.isChecked():
            self._check_aot.blockSignals(True)
            self._check_aot.setChecked(aot)
            self._check_aot.blockSignals(False)

    def _on_overlay_toggled(self, checked: bool) -> None:
        self._save_all()
        overlay_id = f"{self._key}/overlay"
        if checked:
            self._core.windows.show(overlay_id)
        else:
            self._core.windows.hide(overlay_id)

    def _on_window_visibility_changed(self, window_id: str = "", visible: bool = False) -> None:
        if window_id != f"{self._key}/overlay":
            return
        self._check_overlay.blockSignals(True)
        self._check_overlay.setChecked(visible)
        self._check_overlay.blockSignals(False)
        cfg = self._read_cfg()
        cfg.setdefault("overlay", {})["enabled"] = visible
        self._write_cfg(cfg)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["monitor_index"] = self._combo_monitor.currentData() or 1
        cfg["display"] = {
            "always_on_top": self._check_aot.isChecked(),
        }
        cfg["overlay"] = {
            "enabled": self._check_overlay.isChecked(),
            "show_active_screen_outline": self._check_outline.isChecked(),
        }
        self._write_cfg(cfg)
