from __future__ import annotations

import logging
from typing import Any, Callable

from src.core.activation_rules import ActivationRuleRegistry
from src.core.base_module import BaseModule
from src.core.capture_region_registry import CaptureRegionRegistry
from src.core.config_manager import ConfigManager
from src.core.panel_manager import PanelManager
from src.core.settings_manager import SettingsManager
from src.core.window_manager import WindowManager

logger = logging.getLogger(__name__)


class Core:
    def __init__(self, config: ConfigManager) -> None:
        self._config = config
        self._modules: dict[str, BaseModule] = {}
        self._hooks: dict[str, list[Callable]] = {}

        self.panels = PanelManager()
        self.settings = SettingsManager()
        self.windows = WindowManager(config)
        self.activation_rules = ActivationRuleRegistry()
        self.capture_regions = CaptureRegionRegistry(config)
        self.windows.on_visibility_changed(self._on_window_visibility_changed)

    def _on_window_visibility_changed(self, window_id: str, visible: bool) -> None:
        self.emit("window.visibility_changed", window_id=window_id, visible=visible)

    # --- Config ---
    def get_config(self, namespace: str) -> dict:
        return self._config.get(namespace)

    def save_config(self, namespace: str, data: dict) -> None:
        self._config.set(namespace, data)
        self.emit("config.changed", namespace=namespace)

    def update_config(self, namespace: str, updates: dict) -> None:
        self._config.update(namespace, updates)
        self.emit("config.changed", namespace=namespace)

    # --- Module access ---
    def get_module(self, key: str) -> BaseModule | None:
        return self._modules.get(key)

    def is_loaded(self, key: str) -> bool:
        return key in self._modules

    def register_module(self, key: str, module: BaseModule) -> None:
        self._modules[key] = module

    # --- Services ---
    def get_service(self, module_key: str, service_name: str) -> Any:
        mod = self._modules.get(module_key)
        if mod is None:
            return None
        try:
            return mod.get_service(service_name)
        except Exception:
            return None

    # --- Hooks ---
    def subscribe(self, hook: str, callback: Callable) -> None:
        self._hooks.setdefault(hook, []).append(callback)

    def emit(self, hook: str, **kwargs: Any) -> None:
        for cb in self._hooks.get(hook, []):
            try:
                cb(**kwargs)
            except Exception as e:
                logger.exception("Hook %s subscriber failed: %s", hook, e)
