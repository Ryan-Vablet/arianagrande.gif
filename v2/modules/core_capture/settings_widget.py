from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #999; font-size: 11px;")
    lbl.setMinimumWidth(80)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _spin(min_val: int, max_val: int, value: int = 0) -> QSpinBox:
    s = QSpinBox()
    s.setRange(min_val, max_val)
    s.setValue(value)
    s.setFixedWidth(90)
    return s


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
    """Monitor selection, bounding box coordinates, polling FPS."""

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

        monitor_row = QHBoxLayout()
        monitor_row.addWidget(_label("Monitor"))
        self._combo_monitor = QComboBox()
        self._combo_monitor.setFixedWidth(220)
        self._load_monitors()
        monitor_row.addWidget(self._combo_monitor)
        monitor_row.addStretch()
        layout.addLayout(monitor_row)

        region_form = QFormLayout()
        region_form.setSpacing(6)
        self._spin_top = _spin(0, 9999)
        self._spin_left = _spin(0, 9999)
        self._spin_width = _spin(1, 9999)
        self._spin_height = _spin(1, 9999)
        region_form.addRow(_label("Top"), self._spin_top)
        region_form.addRow(_label("Left"), self._spin_left)
        region_form.addRow(_label("Width"), self._spin_width)
        region_form.addRow(_label("Height"), self._spin_height)
        layout.addLayout(region_form)

        fps_form = QFormLayout()
        fps_form.setSpacing(6)
        self._spin_fps = _spin(5, 120, 20)
        fps_form.addRow(_label("Polling FPS"), self._spin_fps)
        layout.addLayout(fps_form)

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
        bb = cfg.get("bounding_box", {})
        self._spin_top.setValue(int(bb.get("top", 900)))
        self._spin_left.setValue(int(bb.get("left", 500)))
        self._spin_width.setValue(int(bb.get("width", 400)))
        self._spin_height.setValue(int(bb.get("height", 50)))
        self._spin_fps.setValue(int(cfg.get("polling_fps", 20)))

    def _connect_signals(self) -> None:
        self._combo_monitor.currentIndexChanged.connect(self._save_all)
        self._spin_top.valueChanged.connect(self._save_all)
        self._spin_left.valueChanged.connect(self._save_all)
        self._spin_width.valueChanged.connect(self._save_all)
        self._spin_height.valueChanged.connect(self._save_all)
        self._spin_fps.valueChanged.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["monitor_index"] = self._combo_monitor.currentData() or 1
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

        form = QFormLayout()
        form.setSpacing(6)
        self._spin_slot_count = _spin(1, 100)
        self._spin_slot_gap = _spin(0, 50)
        self._spin_slot_padding = _spin(0, 50)
        form.addRow(_label("Count"), self._spin_slot_count)
        form.addRow(_label("Gap px"), self._spin_slot_gap)
        form.addRow(_label("Padding px"), self._spin_slot_padding)
        layout.addLayout(form)

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


class OverlayDisplaySettings(_SaveMixin, QWidget):
    """Overlay toggle, screen outline, always-on-top."""

    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._build_ui()
        self._populate()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)

        self._check_overlay = QCheckBox("Show capture overlay")
        self._check_outline = QCheckBox("Show active screen outline")
        self._check_aot = QCheckBox("Always on top")

        layout.addWidget(self._check_overlay)
        layout.addWidget(self._check_outline)
        layout.addWidget(self._check_aot)
        layout.addStretch()

    def _populate(self) -> None:
        cfg = self._read_cfg()
        overlay = cfg.get("overlay", {})
        self._check_overlay.setChecked(bool(overlay.get("enabled", False)))
        self._check_outline.setChecked(bool(overlay.get("show_active_screen_outline", False)))
        display = cfg.get("display", {})
        self._check_aot.setChecked(bool(display.get("always_on_top", False)))

    def _connect_signals(self) -> None:
        self._check_overlay.toggled.connect(self._save_all)
        self._check_outline.toggled.connect(self._save_all)
        self._check_aot.toggled.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["overlay"] = {
            "enabled": self._check_overlay.isChecked(),
            "show_active_screen_outline": self._check_outline.isChecked(),
        }
        cfg["display"] = {
            "always_on_top": self._check_aot.isChecked(),
        }
        self._write_cfg(cfg)
