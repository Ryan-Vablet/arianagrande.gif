from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class SettingsRegistration:
    path: str
    factory: Callable[[], Any]
    title: str = ""
    owner: str = ""
    order: int = 50


class SettingsManager:
    def __init__(self) -> None:
        self._registrations: dict[str, SettingsRegistration] = {}

    def register(
        self,
        path: str,
        factory: Callable[[], Any],
        *,
        title: str = "",
        owner: str = "",
        order: int = 50,
    ) -> None:
        self._registrations[path] = SettingsRegistration(
            path=path, factory=factory, title=title, owner=owner, order=order,
        )

    def get_tabs(self) -> list[dict]:
        tabs_map: dict[str, dict] = {}

        for path, reg in self._registrations.items():
            parts = path.split("/", 1)
            tab_name = parts[0]

            if tab_name not in tabs_map:
                tabs_map[tab_name] = {
                    "path": tab_name,
                    "title": None,
                    "widget_factory": None,
                    "order": None,
                    "children": [],
                }

            if len(parts) == 1:
                tabs_map[tab_name]["widget_factory"] = reg.factory
                tabs_map[tab_name]["title"] = reg.title
                tabs_map[tab_name]["order"] = reg.order
            else:
                tabs_map[tab_name]["children"].append({
                    "path": path,
                    "title": reg.title,
                    "widget_factory": reg.factory,
                    "order": reg.order,
                })

        result = []
        for tab_name, tab_data in tabs_map.items():
            tab_data["children"].sort(key=lambda c: c["order"])

            if tab_data["order"] is None:
                if tab_data["children"]:
                    tab_data["order"] = min(c["order"] for c in tab_data["children"])
                else:
                    tab_data["order"] = 50

            if tab_data["title"] is None:
                tab_data["title"] = tab_name.replace("_", " ").title()

            result.append(tab_data)

        result.sort(key=lambda t: t["order"])
        return result

    def teardown_module(self, module_key: str) -> None:
        self._registrations = {
            k: v for k, v in self._registrations.items() if v.owner != module_key
        }
