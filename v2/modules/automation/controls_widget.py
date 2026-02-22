"""Arm/disarm toggle button + status display for the primary area."""
from __future__ import annotations

import time
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


_STYLE_DISARMED = (
    "QPushButton { background: #444; color: #ccc; border: 1px solid #555;"
    " border-radius: 4px; font-weight: bold; padding: 4px 16px; }"
    "QPushButton:hover { background: #555; }"
)
_STYLE_ARMED = (
    "QPushButton { background: #883333; color: #ff8888; border: 1px solid #aa4444;"
    " border-radius: 4px; font-weight: bold; padding: 4px 16px; }"
    "QPushButton:hover { background: #994444; }"
)
_STATUS_ARMED = "color: #ff8888; font-size: 11px; font-weight: bold;"
_STATUS_DISARMED = "color: #888; font-size: 11px;"


class AutomationControls(QWidget):
    def __init__(self, core: Any, module_ref: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core = core
        self._module = module_ref
        self._last_action_time: float = 0.0
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh_last_action)

        self._core.subscribe("config.changed", self._on_config_changed)

    def _on_config_changed(self, namespace: str = "") -> None:
        if namespace == self._module.key:
            self._refresh_list_name()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        self._btn_arm = QPushButton("\u25B6  ARM")
        self._btn_arm.setMinimumWidth(100)
        self._btn_arm.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_arm.setStyleSheet(_STYLE_DISARMED)
        self._btn_arm.clicked.connect(self._on_arm_clicked)
        layout.addWidget(self._btn_arm)

        self._status_label = QLabel("Disarmed")
        self._status_label.setStyleSheet(_STATUS_DISARMED)
        layout.addWidget(self._status_label)

        layout.addStretch()

        self._last_action_label = QLabel("")
        self._last_action_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._last_action_label)

        self._list_label = QLabel("")
        self._list_label.setStyleSheet("color: #aaa; font-size: 11px; font-style: italic;")
        self._list_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._list_label)

        self._refresh_list_name()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_arm_clicked(self) -> None:
        self._module.toggle_armed()

    def on_armed_changed(self, armed: bool) -> None:
        if armed:
            self._btn_arm.setText("\u23F9  DISARM")
            self._btn_arm.setStyleSheet(_STYLE_ARMED)
            self._status_label.setText("Armed \u2014 sending keys")
            self._status_label.setStyleSheet(_STATUS_ARMED)
        else:
            self._btn_arm.setText("\u25B6  ARM")
            self._btn_arm.setStyleSheet(_STYLE_DISARMED)
            self._status_label.setText("Disarmed")
            self._status_label.setStyleSheet(_STATUS_DISARMED)
            self._last_action_label.setText("")
            self._timer.stop()

    def on_list_changed(self, list_id: str) -> None:
        self._refresh_list_name()

    def on_key_action(self, result: dict) -> None:
        action = result.get("action", "")
        keybind = result.get("keybind", "?")
        display = result.get("display_name", "")
        if action == "sent":
            self._last_action_time = result.get("timestamp", time.time())
            label = f"[{keybind}]"
            if display:
                label += f" {display}"
            self._last_action_label.setText(label)
            self._last_action_label.setStyleSheet("color: #88ff88; font-size: 11px;")
            if not self._timer.isActive():
                self._timer.start()
        elif action == "blocked":
            reason = result.get("reason", "")
            self._last_action_label.setText(f"[{keybind}] blocked ({reason})")
            self._last_action_label.setStyleSheet("color: #ff8888; font-size: 11px;")

    def _refresh_last_action(self) -> None:
        if self._last_action_time <= 0:
            return
        elapsed = time.time() - self._last_action_time
        if elapsed > 10:
            self._last_action_label.setStyleSheet("color: #666; font-size: 11px;")
            self._timer.stop()

    def _refresh_list_name(self) -> None:
        cfg = self._core.get_config(self._module.key)
        active_id = cfg.get("active_list_id", "")
        for pl in cfg.get("priority_lists", []):
            if pl.get("id") == active_id:
                self._list_label.setText(pl.get("name", active_id))
                return
        self._list_label.setText("")
