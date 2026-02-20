from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


@dataclass
class WindowRegistration:
    id: str
    factory: Callable[[], Any]
    title: str = ""
    window_type: str = "panel"
    owner: str = ""
    default_visible: bool = False
    remember_geometry: bool = True
    show_in_menu: bool = True
    singleton: bool = True
    instance: Any = None


class WindowManager:
    def __init__(self, config_manager: ConfigManager) -> None:
        self._config = config_manager
        self._registry: dict[str, WindowRegistration] = {}
        self._visibility_callbacks: list[Callable[[str, bool], None]] = []

    def on_visibility_changed(self, callback: Callable[[str, bool], None]) -> None:
        """Register *callback(window_id, visible)* called after show/hide."""
        self._visibility_callbacks.append(callback)

    def _notify_visibility(self, id: str, visible: bool) -> None:
        for cb in self._visibility_callbacks:
            try:
                cb(id, visible)
            except Exception as e:
                logger.warning("visibility callback failed for %s: %s", id, e)

    def register(
        self,
        id: str,
        factory: Callable[[], Any],
        *,
        title: str = "",
        window_type: str = "panel",
        owner: str = "",
        default_visible: bool = False,
        remember_geometry: bool = True,
        show_in_menu: bool = True,
        singleton: bool = True,
    ) -> None:
        self._registry[id] = WindowRegistration(
            id=id, factory=factory, title=title, window_type=window_type,
            owner=owner, default_visible=default_visible,
            remember_geometry=remember_geometry, show_in_menu=show_in_menu,
            singleton=singleton,
        )

    def show(self, id: str) -> None:
        entry = self._registry.get(id)
        if entry is None:
            return
        if entry.instance is None:
            entry.instance = entry.factory()
            entry.instance.setWindowTitle(entry.title or entry.id)
            if entry.remember_geometry:
                self._restore_geometry(entry)
        entry.instance.show()
        entry.instance.raise_()
        self._notify_visibility(id, True)

    def hide(self, id: str) -> None:
        entry = self._registry.get(id)
        if entry and entry.instance:
            entry.instance.hide()
            self._notify_visibility(id, False)

    def toggle(self, id: str) -> None:
        entry = self._registry.get(id)
        if entry and entry.instance and entry.instance.isVisible():
            self.hide(id)
        else:
            self.show(id)

    def is_visible(self, id: str) -> bool:
        entry = self._registry.get(id)
        return bool(entry and entry.instance and entry.instance.isVisible())

    def get(self, id: str) -> Any:
        entry = self._registry.get(id)
        return entry.instance if entry else None

    def list_menu_entries(self) -> list[WindowRegistration]:
        return sorted(
            [r for r in self._registry.values() if r.show_in_menu],
            key=lambda r: r.title or r.id,
        )

    def show_defaults(self) -> None:
        app_cfg = self._config.get("app")
        saved_geo = app_cfg.get("window_geometry", {})
        for entry in self._registry.values():
            saved = saved_geo.get(entry.id, {})
            if saved.get("visible", entry.default_visible):
                self.show(entry.id)

    def save_all_geometry(self) -> None:
        geo: dict[str, dict] = {}
        for entry in self._registry.values():
            if entry.instance and entry.remember_geometry:
                rect = entry.instance.geometry()
                geo[entry.id] = {
                    "x": rect.x(), "y": rect.y(),
                    "w": rect.width(), "h": rect.height(),
                    "visible": entry.instance.isVisible(),
                }
        app_cfg = self._config.get("app")
        app_cfg["window_geometry"] = geo
        self._config.set("app", app_cfg)

    def teardown_module(self, module_key: str) -> None:
        to_remove = [k for k, v in self._registry.items() if v.owner == module_key]
        for id in to_remove:
            entry = self._registry[id]
            if entry.instance:
                entry.instance.close()
            del self._registry[id]

    def teardown(self) -> None:
        self.save_all_geometry()
        for entry in self._registry.values():
            if entry.instance:
                entry.instance.close()
                entry.instance = None

    def _restore_geometry(self, entry: WindowRegistration) -> None:
        app_cfg = self._config.get("app")
        saved = app_cfg.get("window_geometry", {}).get(entry.id)
        if saved and entry.instance:
            entry.instance.setGeometry(saved["x"], saved["y"], saved["w"], saved["h"])
