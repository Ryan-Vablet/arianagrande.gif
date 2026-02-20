"""Automation module — reads slot states and sends keys based on priority lists."""
from __future__ import annotations

import logging
from abc import ABCMeta
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal

from src.core.base_module import BaseModule

logger = logging.getLogger(__name__)


class _CombinedMeta(type(QObject), ABCMeta):
    pass


class AutomationModule(QObject, BaseModule, metaclass=_CombinedMeta):
    name = "Automation"
    key = "automation"
    version = "1.0.0"
    description = "Priority-based key sending with multiple lists, auto/single fire, spell queue"
    requires: list[str] = ["core_capture"]
    optional: list[str] = ["brightness_detection", "glow_detection", "cast_bar", "buff_tracking"]
    provides_services = ["armed", "active_list_id", "last_action"]
    hooks = ["key_sent", "armed_changed", "list_switched"]

    key_action_signal = pyqtSignal(dict)
    armed_changed_signal = pyqtSignal(bool)
    list_changed_signal = pyqtSignal(str)

    def __init__(self) -> None:
        QObject.__init__(self)
        BaseModule.__init__(self)
        self._key_sender: Any = None
        self._queue_listener: Any = None
        self._hotkey_listener: Any = None
        self._armed: bool = False
        self._last_action: dict | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self, core: Any) -> None:
        super().setup(core)
        from modules.automation.key_sender import KeySender

        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())

        self._key_sender = KeySender()

        core.activation_rules.register(
            id="always",
            label="Always",
            group="general",
            group_label="General",
            owner=self.key,
            order=0,
        )

        core.panels.register(
            id=f"{self.key}/controls",
            area="primary",
            factory=self._build_controls,
            title="Automation",
            owner=self.key,
            order=5,
        )
        core.panels.register(
            id=f"{self.key}/priority",
            area="sidebar",
            factory=self._build_priority_panel,
            title="Priority",
            owner=self.key,
            order=0,
        )

        core.settings.register(
            path="automation/general",
            factory=self._build_general_settings,
            title="General",
            owner=self.key,
            order=0,
        )
        core.settings.register(
            path="automation/keybinds",
            factory=self._build_keybind_settings,
            title="Keybinds",
            owner=self.key,
            order=10,
        )
        core.settings.register(
            path="automation/priority_lists",
            factory=self._build_list_settings,
            title="Priority Lists",
            owner=self.key,
            order=20,
        )
        core.settings.register(
            path="automation/queue",
            factory=self._build_queue_settings,
            title="Spell Queue",
            owner=self.key,
            order=30,
        )

    def ready(self) -> None:
        self._start_hotkey_listener()
        self._start_queue_listener()

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def on_frame(self, frame: np.ndarray) -> None:
        if not self._key_sender:
            return

        slot_states = self.core.get_service("brightness_detection", "slot_states") or []
        if not slot_states:
            return

        cfg = self.core.get_config(self.key)

        # Resolve which list to use for this tick
        sf_list_id = self._key_sender.single_fire_list_id
        if self._key_sender.single_fire_pending and sf_list_id:
            active_list = self._get_list_by_id(sf_list_id)
        else:
            active_list = self._get_active_list()
        if not active_list:
            return

        buff_states = self.core.get_service("buff_tracking", "buff_states")

        queued = self._queue_listener.get_queue() if self._queue_listener else None
        on_queued_sent = self._queue_listener.clear_queue if self._queue_listener else None

        result = self._key_sender.evaluate_and_send(
            slot_states=slot_states,
            priority_items=active_list.get("priority_items", []),
            keybinds=cfg.get("keybinds", []),
            manual_actions=active_list.get("manual_actions", []),
            armed=self._armed,
            min_interval_ms=cfg.get("min_press_interval_ms", 150),
            target_window_title=cfg.get("target_window_title", ""),
            allow_cast_while_casting=cfg.get("allow_cast_while_casting", False),
            queue_window_ms=cfg.get("queue_window_ms", 120),
            gcd_ms=cfg.get("gcd_ms", 1500),
            queued_override=queued,
            on_queued_sent=on_queued_sent,
            buff_states=buff_states,
            queue_fire_delay_ms=cfg.get("queue_fire_delay_ms", 100),
        )

        if result:
            self._last_action = result
            self.key_action_signal.emit(result)
            self.core.emit(f"{self.key}.key_sent", **result)

    # ------------------------------------------------------------------
    # Arm / disarm
    # ------------------------------------------------------------------

    def arm(self) -> None:
        if not self._armed:
            self._armed = True
            self.armed_changed_signal.emit(True)
            self.core.emit(f"{self.key}.armed_changed", armed=True)

    def disarm(self) -> None:
        if self._armed:
            self._armed = False
            self.armed_changed_signal.emit(False)
            self.core.emit(f"{self.key}.armed_changed", armed=False)

    def toggle_armed(self) -> None:
        if self._armed:
            self.disarm()
        else:
            self.arm()

    @property
    def is_armed(self) -> bool:
        return self._armed

    # ------------------------------------------------------------------
    # List switching
    # ------------------------------------------------------------------

    def switch_to_list(self, list_id: str) -> None:
        cfg = self.core.get_config(self.key)
        lists = cfg.get("priority_lists", [])
        if any(pl.get("id") == list_id for pl in lists):
            cfg["active_list_id"] = list_id
            self.core.save_config(self.key, cfg)
            self.list_changed_signal.emit(list_id)
            self.core.emit(f"{self.key}.list_switched", list_id=list_id)

    def _get_active_list(self) -> dict | None:
        cfg = self.core.get_config(self.key)
        active_id = cfg.get("active_list_id", "")
        for pl in cfg.get("priority_lists", []):
            if pl.get("id") == active_id:
                return pl
        lists = cfg.get("priority_lists", [])
        return lists[0] if lists else None

    def _get_list_by_id(self, list_id: str) -> dict | None:
        cfg = self.core.get_config(self.key)
        for pl in cfg.get("priority_lists", []):
            if pl.get("id") == list_id:
                return pl
        return None

    # ------------------------------------------------------------------
    # Hotkey handling
    # ------------------------------------------------------------------

    def _on_hotkey_triggered(self, bind: str) -> None:
        cfg = self.core.get_config(self.key)
        for pl in cfg.get("priority_lists", []):
            if pl.get("toggle_bind") == bind:
                if cfg.get("active_list_id") == pl["id"] and self._armed:
                    self.disarm()
                else:
                    self.switch_to_list(pl["id"])
                    self.arm()
                return
            if pl.get("single_fire_bind") == bind:
                self._key_sender.request_single_fire(list_id=pl["id"])
                return

    def _start_hotkey_listener(self) -> None:
        from modules.automation.global_hotkey import GlobalToggleListener

        def get_all_binds() -> list[str]:
            cfg = self.core.get_config(self.key)
            binds: list[str] = []
            for pl in cfg.get("priority_lists", []):
                tb = pl.get("toggle_bind", "")
                if tb:
                    binds.append(tb)
                sfb = pl.get("single_fire_bind", "")
                if sfb:
                    binds.append(sfb)
            return binds

        self._hotkey_listener = GlobalToggleListener(get_all_binds)
        self._hotkey_listener.triggered.connect(self._on_hotkey_triggered)
        self._hotkey_listener.start()

    def _start_queue_listener(self) -> None:
        from modules.automation.queue_listener import QueueListener

        self._queue_listener = QueueListener(
            get_config=lambda: self.core.get_config(self.key),
        )
        self._queue_listener.start()

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def get_service(self, name: str) -> Any:
        if name == "armed":
            return self._armed
        if name == "active_list_id":
            cfg = self.core.get_config(self.key)
            return cfg.get("active_list_id", "")
        if name == "last_action":
            return self._last_action
        return None

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _default_config(self) -> dict:
        return {
            "min_press_interval_ms": 150,
            "gcd_ms": 1500,
            "target_window_title": "",
            "allow_cast_while_casting": False,
            "queue_window_ms": 120,
            "queue_whitelist": [],
            "queue_timeout_ms": 5000,
            "queue_fire_delay_ms": 100,
            "active_list_id": "default",
            "keybinds": [],
            "slot_display_names": [],
            "priority_lists": [
                {
                    "id": "default",
                    "name": "Default",
                    "toggle_bind": "",
                    "single_fire_bind": "",
                    "priority_items": [],
                    "manual_actions": [],
                }
            ],
        }

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def teardown(self) -> None:
        self.disarm()
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        if self._queue_listener:
            self._queue_listener.stop()

    # ------------------------------------------------------------------
    # Widget builders
    # ------------------------------------------------------------------

    def _build_controls(self) -> Any:
        from modules.automation.controls_widget import AutomationControls
        w = AutomationControls(self.core, self)
        self.armed_changed_signal.connect(
            w.on_armed_changed, Qt.ConnectionType.QueuedConnection,
        )
        self.list_changed_signal.connect(
            w.on_list_changed, Qt.ConnectionType.QueuedConnection,
        )
        self.key_action_signal.connect(
            w.on_key_action, Qt.ConnectionType.QueuedConnection,
        )
        return w

    def _build_priority_panel(self) -> Any:
        from modules.automation.priority_panel import PriorityPanel
        w = PriorityPanel(self.core, self)
        self.list_changed_signal.connect(
            w.refresh_from_config, Qt.ConnectionType.QueuedConnection,
        )
        if self.core.is_loaded("brightness_detection"):
            bd = self.core.get_module("brightness_detection")
            if bd and hasattr(bd, "slot_states_updated_signal"):
                bd.slot_states_updated_signal.connect(
                    w.update_states, Qt.ConnectionType.QueuedConnection,
                )
        return w

    def _build_general_settings(self) -> Any:
        from modules.automation.settings_widget import GeneralSettings
        return GeneralSettings(self.core, self.key)

    def _build_keybind_settings(self) -> Any:
        from modules.automation.settings_widget import KeybindSettings
        return KeybindSettings(self.core, self.key)

    def _build_list_settings(self) -> Any:
        from modules.automation.settings_widget import PriorityListSettings
        return PriorityListSettings(self.core, self.key)

    def _build_queue_settings(self) -> Any:
        from modules.automation.settings_widget import QueueSettings
        return QueueSettings(self.core, self.key)
