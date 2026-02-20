"""Spell queue listener: catches non-priority keypresses to fire at next GCD."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)

_LEFT_MOUSE_NAMES = frozenset({"left", "left click", "mouse left"})


def _normalize_key(name: str) -> str:
    return str(name or "").strip().lower()


class _QueueHookThread(QThread):
    def __init__(
        self,
        get_config: Callable[[], dict],
        get_queue: Callable[[], Optional[dict]],
        set_queue_value: Callable[[dict], None],
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._get_config = get_config
        self._get_queue = get_queue
        self._set_queue_value = set_queue_value
        self._running = True
        self._hook = None

    def run(self) -> None:
        try:
            import keyboard
        except ImportError:
            logger.warning("keyboard library not installed; spell queue disabled.")
            return

        def on_event(event):
            if not self._running:
                return
            if getattr(event, "event_type", None) != keyboard.KEY_DOWN:
                return
            name = getattr(event, "name", None)
            key = _normalize_key(name or "")
            if not key or key in _LEFT_MOUSE_NAMES:
                return
            try:
                config = self._get_config()
            except Exception:
                return
            whitelist = config.get("queue_whitelist", []) or []
            keybinds = config.get("keybinds", []) or []
            priority_items = []
            for pl in config.get("priority_lists", []):
                if pl.get("id") == config.get("active_list_id"):
                    priority_items = pl.get("priority_items", [])
                    break
            priority_indices = set()
            for item in priority_items:
                if str(item.get("type", "")).lower() == "slot":
                    idx = item.get("slot_index")
                    if isinstance(idx, int):
                        priority_indices.add(idx)
            priority_keys = set()
            for idx in priority_indices:
                if idx < len(keybinds) and (keybinds[idx] or "").strip():
                    priority_keys.add(_normalize_key(keybinds[idx]))
            if key in priority_keys:
                return
            if key in whitelist:
                existing = self._get_queue()
                if existing and existing.get("key") == key and existing.get("source") == "whitelist":
                    return
                self._set_queue_value({"key": key, "source": "whitelist"})
                return
            for slot_index, bind in enumerate(keybinds):
                if slot_index in priority_indices:
                    continue
                if not (bind or "").strip():
                    continue
                if _normalize_key(bind) == key:
                    existing = self._get_queue()
                    if (
                        existing
                        and existing.get("source") == "tracked"
                        and existing.get("slot_index") == slot_index
                    ):
                        return
                    self._set_queue_value({"key": key, "slot_index": slot_index, "source": "tracked"})
                    return

        try:
            self._hook = keyboard.hook(on_event)
        except Exception as e:
            logger.debug("queue listener hook failed: %s", e)
            return
        while self._running:
            self.msleep(200)
        if self._hook is not None:
            try:
                keyboard.unhook(self._hook)
            except Exception:
                pass
            self._hook = None

    def stop(self) -> None:
        self._running = False


class QueueListener(QObject):
    """Manages a single queued override (whitelist or tracked slot not in priority).

    Adapted from v1 to read flat config dicts instead of AppConfig.
    """

    queue_updated = pyqtSignal(object)

    def __init__(self, get_config: Callable[[], dict], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._get_config = get_config
        self._lock = threading.Lock()
        self._queue: Optional[dict] = None
        self._queue_time: float = 0.0
        self._thread: Optional[_QueueHookThread] = None

    def _get_queue_internal(self) -> Optional[dict]:
        with self._lock:
            return self._queue

    def get_queue(self) -> Optional[dict]:
        try:
            config = self._get_config()
            timeout_ms = config.get("queue_timeout_ms", 5000) or 5000
            timeout_sec = timeout_ms / 1000.0
        except Exception:
            timeout_sec = 5.0
        with self._lock:
            if self._queue is None:
                return None
            if (time.time() - self._queue_time) >= timeout_sec:
                self._queue = None
                self._queue_time = 0.0
                need_emit = True
            else:
                need_emit = False
                return self._queue.copy()
        if need_emit:
            self.queue_updated.emit(None)
        return None

    def clear_queue(self) -> None:
        with self._lock:
            had = self._queue is not None
            self._queue = None
            self._queue_time = 0.0
        if had:
            self.queue_updated.emit(None)

    def start(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return

        def set_value(value: dict) -> None:
            with self._lock:
                self._queue = value.copy()
                self._queue_time = time.time()
            self.queue_updated.emit(value)

        self._thread = _QueueHookThread(
            self._get_config,
            self._get_queue_internal,
            set_value,
            self,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread.wait(2000)
            self._thread = None
        self.clear_queue()
