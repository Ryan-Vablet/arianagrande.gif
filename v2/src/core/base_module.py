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

    def on_frame(self, frame: "np.ndarray") -> None:
        """Called each capture cycle with the raw frame (BGR numpy array).

        Only implement if the module needs per-frame processing.
        Frame is the full captured region — modules crop what they need.

        IMPORTANT: This is called from the capture worker thread, NOT the GUI thread.
        Do not update Qt widgets directly. Use signals with Qt.QueuedConnection
        to marshal updates to the GUI thread.
        """
        pass

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def teardown(self) -> None:
        pass
