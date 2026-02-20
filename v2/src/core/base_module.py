from __future__ import annotations

from abc import ABC
from typing import Any


class BaseModule(ABC):
    """Base class all modules inherit from."""

    name: str = ""
    key: str = ""
    version: str = "1.0.0"
    description: str = ""

    requires: list[str] = []
    optional: list[str] = []

    provides_services: list[str] = []
    hooks: list[str] = []

    def __init__(self) -> None:
        self.core: Any = None
        self.enabled: bool = True

    def setup(self, core: Any) -> None:
        self.core = core

    def ready(self) -> None:
        pass

    def get_service(self, name: str) -> Any:
        return None

    def on_config_changed(self, key: str, value: Any) -> None:
        pass

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def teardown(self) -> None:
        pass
