"""Automation settings — four sub-tab widget classes."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

LW = 130


def _label(text: str, width: int = LW) -> QLabel:
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


def _capped_row(inner, max_width: int = 420) -> QHBoxLayout:
    container = QWidget()
    container.setLayout(inner)
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


# ======================================================================
# General
# ======================================================================


class GeneralSettings(_SaveMixin, QWidget):
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

        self._spin_interval = _spin(50, 2000, 150)
        self._spin_gcd = _spin(500, 5000, 1500)
        self._edit_target = QLineEdit()
        self._edit_target.setPlaceholderText("Leave empty for any window")
        self._edit_target.setMaximumWidth(260)
        self._check_cast = QCheckBox("Allow cast while casting")

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.addWidget(_label("Min Press Interval (ms)"), 0, 0)
        grid.addWidget(self._spin_interval, 0, 1)
        grid.addWidget(_label("GCD Duration (ms)"), 1, 0)
        grid.addWidget(self._spin_gcd, 1, 1)
        grid.addWidget(_label("Target Window Title"), 2, 0)
        grid.addWidget(self._edit_target, 2, 1)
        layout.addLayout(_capped_row(grid, 460))
        layout.addWidget(self._check_cast)
        layout.addStretch()

    def _populate(self) -> None:
        cfg = self._read_cfg()
        self._spin_interval.setValue(int(cfg.get("min_press_interval_ms", 150)))
        self._spin_gcd.setValue(int(cfg.get("gcd_ms", 1500)))
        self._edit_target.setText(cfg.get("target_window_title", ""))
        self._check_cast.setChecked(bool(cfg.get("allow_cast_while_casting", False)))

    def _connect_signals(self) -> None:
        self._spin_interval.valueChanged.connect(self._save_all)
        self._spin_gcd.valueChanged.connect(self._save_all)
        self._edit_target.editingFinished.connect(self._save_all)
        self._check_cast.toggled.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["min_press_interval_ms"] = self._spin_interval.value()
        cfg["gcd_ms"] = self._spin_gcd.value()
        cfg["target_window_title"] = self._edit_target.text().strip()
        cfg["allow_cast_while_casting"] = self._check_cast.isChecked()
        self._write_cfg(cfg)


# ======================================================================
# Keybinds
# ======================================================================


class KeybindSettings(_SaveMixin, QWidget):
    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._capture_thread = None
        self._capture_target: int | None = None
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        cc_cfg = self._core.get_config("core_capture")
        slot_count = cc_cfg.get("slots", {}).get("count", 10)
        cfg = self._read_cfg()
        keybinds = cfg.get("keybinds", [])
        display_names = cfg.get("slot_display_names", [])

        while len(keybinds) < slot_count:
            keybinds.append("")
        while len(display_names) < slot_count:
            display_names.append("")

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        grid.addWidget(_label("Slot", 40), 0, 0)
        grid.addWidget(_label("Keybind", 60), 0, 1)
        grid.addWidget(_label("Display Name", 80), 0, 2)

        for i in range(slot_count):
            row = i + 1
            lbl = QLabel(str(i + 1))
            lbl.setStyleSheet("color: #aaa; font-size: 11px;")
            lbl.setFixedWidth(40)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, row, 0)

            from src.automation.binds import format_bind_for_display
            btn = QPushButton(format_bind_for_display(keybinds[i]))
            btn.setFixedWidth(90)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._start_capture(idx))
            grid.addWidget(btn, row, 1)

            edit = QLineEdit(display_names[i])
            edit.setMaximumWidth(180)
            edit.editingFinished.connect(self._save_all)
            grid.addWidget(edit, row, 2)

            self._rows.append({"btn": btn, "edit": edit})

        layout.addLayout(_capped_row(grid, 400))
        layout.addStretch()

    def _start_capture(self, slot_index: int) -> None:
        if self._capture_thread is not None:
            return
        self._capture_target = slot_index
        self._rows[slot_index]["btn"].setText("Press a key...")
        from modules.automation.global_hotkey import CaptureOneKeyThread
        self._capture_thread = CaptureOneKeyThread(self)
        self._capture_thread.captured.connect(self._on_captured)
        self._capture_thread.finished.connect(self._on_capture_finished)
        self._capture_thread.start()

    def _on_captured(self, bind: str) -> None:
        idx = self._capture_target
        if idx is not None and 0 <= idx < len(self._rows):
            from src.automation.binds import format_bind_for_display
            self._rows[idx]["btn"].setText(format_bind_for_display(bind))
            cfg = self._read_cfg()
            keybinds = cfg.get("keybinds", [])
            while len(keybinds) <= idx:
                keybinds.append("")
            keybinds[idx] = bind
            cfg["keybinds"] = keybinds
            self._write_cfg(cfg)
        self._capture_target = None

    def _on_capture_finished(self) -> None:
        self._capture_thread = None

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        names = []
        for row_data in self._rows:
            names.append(row_data["edit"].text().strip())
        cfg["slot_display_names"] = names
        self._write_cfg(cfg)


# ======================================================================
# Priority Lists
# ======================================================================


class PriorityListSettings(_SaveMixin, QWidget):
    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._core = core
        self._key = module_key
        self._list_rows: list[dict] = []
        self._capture_thread = None
        self._capture_target: tuple[int, str] | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._rows_container = QVBoxLayout()
        self._layout.addLayout(self._rows_container)
        self._rebuild_rows()

        btn_new = QPushButton("+ New List")
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.clicked.connect(self._on_add_list)
        add_row = QHBoxLayout()
        add_row.addWidget(btn_new)
        add_row.addStretch()
        self._layout.addLayout(add_row)
        self._layout.addStretch()

    def _rebuild_rows(self) -> None:
        for row_data in self._list_rows:
            row_data["widget"].deleteLater()
        self._list_rows.clear()

        cfg = self._read_cfg()
        active_id = cfg.get("active_list_id", "")
        lists = cfg.get("priority_lists", [])

        for i, pl in enumerate(lists):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(8)

            name_edit = QLineEdit(pl.get("name", ""))
            name_edit.setMaximumWidth(140)
            name_edit.editingFinished.connect(self._save_all_lists)
            row_layout.addWidget(name_edit)

            from src.automation.binds import format_bind_for_display
            toggle_btn = QPushButton(format_bind_for_display(pl.get("toggle_bind", "")))
            toggle_btn.setToolTip("Toggle bind — press to record")
            toggle_btn.setFixedWidth(80)
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_btn.clicked.connect(lambda checked, idx=i: self._start_bind_capture(idx, "toggle"))
            row_layout.addWidget(toggle_btn)

            sf_btn = QPushButton(format_bind_for_display(pl.get("single_fire_bind", "")))
            sf_btn.setToolTip("Single fire bind — press to record")
            sf_btn.setFixedWidth(80)
            sf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sf_btn.clicked.connect(lambda checked, idx=i: self._start_bind_capture(idx, "single_fire"))
            row_layout.addWidget(sf_btn)

            is_active = pl.get("id") == active_id
            active_label = QLabel("\u2713" if is_active else "")
            active_label.setStyleSheet("color: #88ff88; font-size: 12px;")
            active_label.setFixedWidth(16)
            row_layout.addWidget(active_label)

            del_btn = QPushButton("\u2715")
            del_btn.setFixedWidth(28)
            del_btn.setToolTip("Delete list")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setEnabled(len(lists) > 1)
            del_btn.clicked.connect(lambda checked, idx=i: self._on_delete_list(idx))
            row_layout.addWidget(del_btn)

            if is_active:
                row_widget.setStyleSheet("background: #2a3a2a; border-radius: 3px;")

            self._rows_container.addWidget(row_widget)
            self._list_rows.append({
                "widget": row_widget,
                "name": name_edit,
                "toggle_btn": toggle_btn,
                "sf_btn": sf_btn,
            })

    def _save_all_lists(self) -> None:
        cfg = self._read_cfg()
        lists = cfg.get("priority_lists", [])
        for i, row_data in enumerate(self._list_rows):
            if i < len(lists):
                lists[i]["name"] = row_data["name"].text().strip() or f"List {i}"
        self._write_cfg(cfg)

    def _start_bind_capture(self, list_index: int, bind_type: str) -> None:
        if self._capture_thread is not None:
            return
        self._capture_target = (list_index, bind_type)
        btn_key = "toggle_btn" if bind_type == "toggle" else "sf_btn"
        if list_index < len(self._list_rows):
            self._list_rows[list_index][btn_key].setText("Press...")
        from modules.automation.global_hotkey import CaptureOneKeyThread
        self._capture_thread = CaptureOneKeyThread(self)
        self._capture_thread.captured.connect(self._on_bind_captured)
        self._capture_thread.finished.connect(self._on_bind_capture_finished)
        self._capture_thread.start()

    def _on_bind_captured(self, bind: str) -> None:
        if self._capture_target is None:
            return
        list_index, bind_type = self._capture_target
        cfg = self._read_cfg()
        lists = cfg.get("priority_lists", [])
        if list_index < len(lists):
            cfg_key = "toggle_bind" if bind_type == "toggle" else "single_fire_bind"
            lists[list_index][cfg_key] = bind
            self._write_cfg(cfg)
        self._capture_target = None
        self._rebuild_rows()

    def _on_bind_capture_finished(self) -> None:
        self._capture_thread = None

    def _on_add_list(self) -> None:
        cfg = self._read_cfg()
        new_id = uuid.uuid4().hex[:8]
        cfg.setdefault("priority_lists", []).append({
            "id": new_id,
            "name": f"List {len(cfg['priority_lists'])}",
            "toggle_bind": "",
            "single_fire_bind": "",
            "priority_items": [],
            "manual_actions": [],
        })
        self._write_cfg(cfg)
        self._rebuild_rows()

    def _on_delete_list(self, index: int) -> None:
        cfg = self._read_cfg()
        lists = cfg.get("priority_lists", [])
        if len(lists) <= 1:
            return
        removed = lists.pop(index)
        if cfg.get("active_list_id") == removed.get("id") and lists:
            cfg["active_list_id"] = lists[0]["id"]
        self._write_cfg(cfg)
        self._rebuild_rows()


# ======================================================================
# Spell Queue
# ======================================================================


class QueueSettings(_SaveMixin, QWidget):
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

        self._spin_timeout = _spin(1000, 30000, 5000)
        self._spin_delay = _spin(0, 500, 100)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.addWidget(_label("Queue Timeout (ms)"), 0, 0)
        grid.addWidget(self._spin_timeout, 0, 1)
        grid.addWidget(_label("Queue Fire Delay (ms)"), 1, 0)
        grid.addWidget(self._spin_delay, 1, 1)
        layout.addLayout(_capped_row(grid, 380))

        wl_label = QLabel("Queue Whitelist (one key per line):")
        wl_label.setStyleSheet("color: #999; font-size: 11px; padding-top: 6px;")
        layout.addWidget(wl_label)

        self._text_whitelist = QTextEdit()
        self._text_whitelist.setMaximumHeight(120)
        self._text_whitelist.setMaximumWidth(260)
        self._text_whitelist.setStyleSheet(
            "QTextEdit { background: #2a2a2a; color: #ccc; border: 1px solid #444;"
            " border-radius: 3px; font-size: 11px; }"
        )
        layout.addWidget(self._text_whitelist)
        layout.addStretch()

    def _populate(self) -> None:
        cfg = self._read_cfg()
        self._spin_timeout.setValue(int(cfg.get("queue_timeout_ms", 5000)))
        self._spin_delay.setValue(int(cfg.get("queue_fire_delay_ms", 100)))
        wl = cfg.get("queue_whitelist", [])
        self._text_whitelist.setPlainText("\n".join(wl))

    def _connect_signals(self) -> None:
        self._spin_timeout.valueChanged.connect(self._save_all)
        self._spin_delay.valueChanged.connect(self._save_all)
        self._text_whitelist.textChanged.connect(self._save_all)

    def _save_all(self) -> None:
        cfg = self._read_cfg()
        cfg["queue_timeout_ms"] = self._spin_timeout.value()
        cfg["queue_fire_delay_ms"] = self._spin_delay.value()
        raw = self._text_whitelist.toPlainText()
        cfg["queue_whitelist"] = [line.strip() for line in raw.splitlines() if line.strip()]
        self._write_cfg(cfg)
