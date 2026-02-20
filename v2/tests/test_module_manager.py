from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
import numpy as np

from src.core.base_module import BaseModule
from src.core.config_manager import ConfigManager
from src.core.core import Core
from src.core.module_manager import ModuleManager


class ModA(BaseModule):
    name = "A"
    key = "a"
    requires: list[str] = []

    def setup(self, core):
        super().setup(core)
        self._setup_called = True

    def ready(self):
        self._ready_called = True

    def teardown(self):
        self._teardown_called = True


class ModB(BaseModule):
    name = "B"
    key = "b"
    requires = ["a"]

    def setup(self, core):
        super().setup(core)
        self._setup_called = True


class ModC(BaseModule):
    name = "C"
    key = "c"
    requires = ["nonexistent"]


class ModCycleX(BaseModule):
    name = "X"
    key = "x"
    requires = ["y"]


class ModCycleY(BaseModule):
    name = "Y"
    key = "y"
    requires = ["x"]


class ModOptional(BaseModule):
    name = "Opt"
    key = "opt"
    requires: list[str] = []
    optional = ["a"]

    def setup(self, core):
        super().setup(core)


class ModWithFrame(BaseModule):
    name = "Framer"
    key = "framer"
    requires: list[str] = []

    def __init__(self):
        super().__init__()
        self.frames: list = []

    def on_frame(self, frame):
        self.frames.append(frame)


@pytest.fixture
def core(tmp_path):
    cfg = ConfigManager(tmp_path / "config.json")
    cfg.load()
    return Core(cfg)


def _write_module_package(modules_dir: Path, key: str, cls_name: str, cls_body: str = ""):
    pkg = modules_dir / key
    pkg.mkdir(parents=True, exist_ok=True)
    body = cls_body or f"""
from src.core.base_module import BaseModule
class {cls_name}(BaseModule):
    name = "{cls_name}"
    key = "{key}"
"""
    (pkg / "__init__.py").write_text(f"from modules.{key}.module import {cls_name}\n")
    (pkg / "module.py").write_text(textwrap.dedent(body))


def test_discover_finds_modules(core, tmp_path):
    modules_dir = tmp_path / "modules"
    _write_module_package(modules_dir, "test_mod", "TestMod")
    mm = ModuleManager(core)
    keys = mm.discover(modules_dir)
    assert "test_mod" in keys


def test_load_calls_setup_then_ready(core):
    mm = ModuleManager(core)
    mm._discovered = {"a": ModA}
    mm.load(["a"])
    mod = mm.get("a")
    assert mod is not None
    assert mod._setup_called
    assert mod._ready_called


def test_dependency_order(core):
    mm = ModuleManager(core)
    mm._discovered = {"a": ModA, "b": ModB}
    mm.load(["a", "b"])
    assert mm._load_order.index("a") < mm._load_order.index("b")


def test_missing_required_dependency_skips(core):
    mm = ModuleManager(core)
    mm._discovered = {"c": ModC}
    mm.load(["c"])
    assert mm.get("c") is None


def test_optional_dependency_still_loads(core):
    mm = ModuleManager(core)
    mm._discovered = {"opt": ModOptional}
    mm.load(["opt"])
    assert mm.get("opt") is not None


def test_optional_dependency_with_target(core):
    mm = ModuleManager(core)
    mm._discovered = {"a": ModA, "opt": ModOptional}
    mm.load(["a", "opt"])
    assert mm.get("a") is not None
    assert mm.get("opt") is not None
    assert mm._load_order.index("a") < mm._load_order.index("opt")


def test_cycle_detection(core):
    mm = ModuleManager(core)
    mm._discovered = {"x": ModCycleX, "y": ModCycleY}
    mm.load(["x", "y"])
    assert mm.get("x") is None
    assert mm.get("y") is None


def test_modules_registered_with_core(core):
    mm = ModuleManager(core)
    mm._discovered = {"a": ModA}
    mm.load(["a"])
    assert core.get_module("a") is not None


def test_shutdown_reverse_order(core):
    mm = ModuleManager(core)
    mm._discovered = {"a": ModA, "b": ModB}
    mm.load(["a", "b"])
    mm.shutdown()
    assert mm.get("a")._teardown_called


def test_process_frame_calls_on_frame(core):
    mm = ModuleManager(core)
    mm._discovered = {"framer": ModWithFrame}
    mm.load(["framer"])
    frame = np.zeros((50, 400, 3), dtype=np.uint8)
    mm.process_frame(frame)
    assert len(mm.get("framer").frames) == 1


def test_disabled_module_skipped_in_process_frame(core):
    mm = ModuleManager(core)
    mm._discovered = {"framer": ModWithFrame}
    mm.load(["framer"])
    mm.get("framer").enabled = False
    frame = np.zeros((50, 400, 3), dtype=np.uint8)
    mm.process_frame(frame)
    assert len(mm.get("framer").frames) == 0
