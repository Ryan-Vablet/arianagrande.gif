from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PanelRegistration:
    id: str
    area: str
    factory: Callable[[], Any]
    title: str = ""
    owner: str = ""
    order: int = 50
    collapsible: bool = True
    default_collapsed: bool = False
    visible: bool = True


class PanelManager:
    def __init__(self) -> None:
        self._panels: dict[str, PanelRegistration] = {}

    def register(
        self,
        id: str,
        area: str,
        factory: Callable[[], Any],
        *,
        title: str = "",
        owner: str = "",
        order: int = 50,
        collapsible: bool = True,
        default_collapsed: bool = False,
    ) -> None:
        self._panels[id] = PanelRegistration(
            id=id, area=area, factory=factory, title=title,
            owner=owner, order=order, collapsible=collapsible,
            default_collapsed=default_collapsed,
        )

    def get_panels(self, area: str) -> list[PanelRegistration]:
        return sorted(
            [p for p in self._panels.values() if p.area == area and p.visible],
            key=lambda p: p.order,
        )

    def teardown_module(self, module_key: str) -> None:
        self._panels = {k: v for k, v in self._panels.items() if v.owner != module_key}
