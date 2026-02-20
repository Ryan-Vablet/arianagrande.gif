from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


_STATE_COLORS: dict[str, str] = {
    "ready": "#22bb44",
    "on_cooldown": "#cc3333",
    "casting": "#ee8822",
    "channeling": "#dd7711",
    "gcd": "#ddbb33",
    "locked": "#888888",
    "unknown": "#444455",
}


def _btn_style(color: str) -> str:
    return (
        f"QPushButton {{ background: {color}; color: white;"
        f" border: 1px solid #555; border-radius: 4px;"
        f" font-size: 11px; font-weight: bold; font-family: monospace;"
        f" padding: 2px 0px; }}"
    )


class SlotStatusWidget(QWidget):
    """Horizontal row of slot state indicators."""

    def __init__(self, core: Any, module_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core = core
        self._key = module_key
        self._slot_buttons: list[QPushButton] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        cc_cfg = self._core.get_config("core_capture")
        slot_count = cc_cfg.get("slots", {}).get("count", 10)

        for i in range(slot_count):
            btn = QPushButton(str(i))
            btn.setMinimumHeight(28)
            btn.setFlat(True)
            btn.setStyleSheet(_btn_style(_STATE_COLORS["unknown"]))
            self._slot_buttons.append(btn)
            layout.addWidget(btn, 1)

    def update_states(self, states: list[dict]) -> None:
        for state_dict in states:
            idx = state_dict.get("index", -1)
            if 0 <= idx < len(self._slot_buttons):
                slot_state = state_dict.get("state", "unknown")
                btn = self._slot_buttons[idx]
                color = _STATE_COLORS.get(slot_state, _STATE_COLORS["unknown"])
                btn.setStyleSheet(_btn_style(color))
                frac = state_dict.get("darkened_fraction", 0)
                btn.setToolTip(f"Slot {idx}: {slot_state}\nDarkened: {frac:.1%}")
