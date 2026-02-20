"""Key sender — evaluates priority and sends keypresses."""
from __future__ import annotations

import logging
import sys
import time
from typing import Callable, Optional

from src.automation.binds import normalize_bind
from src.automation.priority_rules import (
    manual_item_is_eligible,
    slot_item_is_eligible_for_state_dict,
)

logger = logging.getLogger(__name__)


def _is_target_window_active_win(target_title: str) -> bool:
    if not (target_title or "").strip():
        return True
    try:
        import ctypes
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        foreground = buf.value or ""
        return target_title.strip().lower() in foreground.lower()
    except Exception as e:
        logger.debug("Foreground window check failed: %s", e)
        return False


def is_target_window_active(target_window_title: str) -> bool:
    if sys.platform != "win32":
        return True
    return _is_target_window_active_win(target_window_title or "")


class KeySender:
    """Evaluates priority list and sends the highest-priority ready keybind."""

    def __init__(self) -> None:
        self._last_send_time: float = 0.0
        self._suppress_priority_until: float = 0.0
        self._single_fire_pending: bool = False
        self._single_fire_list_id: str | None = None

    def request_single_fire(self, list_id: str | None = None) -> None:
        self._single_fire_pending = True
        self._single_fire_list_id = list_id

    @property
    def single_fire_pending(self) -> bool:
        return self._single_fire_pending

    @property
    def single_fire_list_id(self) -> str | None:
        return self._single_fire_list_id

    def evaluate_and_send(
        self,
        slot_states: list[dict],
        priority_items: list[dict],
        keybinds: list[str],
        manual_actions: list[dict],
        armed: bool,
        *,
        min_interval_ms: int = 150,
        target_window_title: str = "",
        allow_cast_while_casting: bool = False,
        queue_window_ms: int = 120,
        gcd_ms: int = 1500,
        queued_override: dict | None = None,
        on_queued_sent: Callable[[], None] | None = None,
        buff_states: dict | None = None,
        queue_fire_delay_ms: int = 100,
    ) -> dict | None:
        single_fire = self._single_fire_pending
        if not armed and not single_fire:
            return None

        min_interval_sec = max(0.01, min_interval_ms / 1000.0)
        now = time.time()
        min_interval_ok = (now - self._last_send_time) >= min_interval_sec
        window_ok = is_target_window_active(target_window_title)

        if not allow_cast_while_casting:
            for sd in slot_states:
                state_val = str(sd.get("state", "")).lower()
                if state_val in ("casting", "channeling"):
                    return {
                        "action": "blocked",
                        "reason": "casting",
                        "slot_index": sd.get("index"),
                    }

        states_by_index: dict[int, dict] = {
            sd["index"]: sd for sd in slot_states if "index" in sd
        }

        any_priority_ready = any(
            isinstance(item, dict)
            and str(item.get("type", "")).lower() == "slot"
            and isinstance(item.get("slot_index"), int)
            and str(states_by_index.get(item["slot_index"], {}).get("state", "")).lower() == "ready"
            for item in (priority_items or [])
        )

        # --- Queued override ---
        if queued_override:
            source = queued_override.get("source")
            key = (queued_override.get("key") or "").strip()
            if source == "whitelist" and key:
                if any_priority_ready and min_interval_ok and window_ok:
                    delay_sec = max(0, queue_fire_delay_ms) / 1000.0
                    if delay_sec > 0:
                        time.sleep(delay_sec)
                    try:
                        import keyboard
                        keyboard.send(key)
                    except Exception as e:
                        logger.warning("keyboard send(queued %r) failed: %s", key, e)
                        return None
                    self._last_send_time = now
                    gcd_sec = max(0, gcd_ms) / 1000.0
                    self._suppress_priority_until = now + gcd_sec
                    if on_queued_sent:
                        on_queued_sent()
                    return {"keybind": key, "action": "sent", "timestamp": now, "queued": True}
                return None
            if source == "tracked":
                slot_index = queued_override.get("slot_index")
                if slot_index is not None and key:
                    sd = states_by_index.get(slot_index, {})
                    slot_ready = str(sd.get("state", "")).lower() == "ready"
                    if slot_ready and any_priority_ready and min_interval_ok and window_ok:
                        delay_sec = max(0, queue_fire_delay_ms) / 1000.0
                        if delay_sec > 0:
                            time.sleep(delay_sec)
                        try:
                            import keyboard
                            keyboard.send(key)
                        except Exception as e:
                            logger.warning("keyboard send(queued %r) failed: %s", key, e)
                            return None
                        self._last_send_time = now
                        gcd_sec = max(0, gcd_ms) / 1000.0
                        self._suppress_priority_until = now + gcd_sec
                        if on_queued_sent:
                            on_queued_sent()
                        return {"keybind": key, "action": "sent", "timestamp": now, "slot_index": slot_index, "queued": True}
                return None
            return None

        # --- Priority evaluation ---
        if not min_interval_ok:
            return None
        if now < self._suppress_priority_until:
            return None

        manual_by_id = {
            str(a.get("id", "")).strip().lower(): a
            for a in (manual_actions or [])
        }

        for item in priority_items:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "")).strip().lower()
            slot_index: int | None = None
            display_name = "Unidentified"
            keybind: str | None = None

            if item_type == "slot":
                slot_index = item.get("slot_index")
                if not isinstance(slot_index, int):
                    continue
                sd = states_by_index.get(slot_index)
                if not slot_item_is_eligible_for_state_dict(item, sd, buff_states=buff_states):
                    continue
                keybind = keybinds[slot_index] if slot_index < len(keybinds) else None
            elif item_type == "manual":
                if not manual_item_is_eligible(item, buff_states=buff_states):
                    continue
                action_id = str(item.get("action_id", "")).strip().lower()
                if not action_id:
                    continue
                action = manual_by_id.get(action_id)
                if not isinstance(action, dict):
                    continue
                keybind = str(action.get("keybind", "")).strip()
                display_name = str(action.get("name", "")).strip() or "Manual Action"
            else:
                continue

            if not keybind:
                continue
            keybind = normalize_bind(str(keybind))
            if not keybind:
                continue

            if not is_target_window_active(target_window_title):
                return {
                    "keybind": keybind, "display_name": display_name,
                    "item_type": item_type, "action": "blocked",
                    "reason": "window", "slot_index": slot_index,
                }

            try:
                import keyboard
                keyboard.send(keybind)
            except Exception as e:
                logger.warning("keyboard.send(%r) failed: %s", keybind, e)
                return None

            self._last_send_time = now
            if single_fire:
                self._single_fire_pending = False
                self._single_fire_list_id = None
            return {
                "keybind": keybind, "display_name": display_name,
                "item_type": item_type, "action": "sent",
                "timestamp": now, "slot_index": slot_index,
            }

        return None
