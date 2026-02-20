from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.config_manager import ConfigManager


@pytest.fixture
def tmp_config(tmp_path: Path) -> tuple[Path, ConfigManager]:
    path = tmp_path / "config.json"
    return path, ConfigManager(path)


def test_load_nonexistent_file(tmp_config):
    path, cm = tmp_config
    cm.load()
    assert cm.get_root() == {}


def test_set_and_get(tmp_config):
    _, cm = tmp_config
    cm.load()
    cm.set("demo", {"message": "hello"})
    assert cm.get("demo") == {"message": "hello"}


def test_get_returns_copy(tmp_config):
    _, cm = tmp_config
    cm.load()
    cm.set("demo", {"message": "hello"})
    copy = cm.get("demo")
    copy["message"] = "mutated"
    assert cm.get("demo")["message"] == "hello"


def test_update_merges(tmp_config):
    _, cm = tmp_config
    cm.load()
    cm.set("demo", {"a": 1, "b": 2})
    cm.update("demo", {"b": 99, "c": 3})
    result = cm.get("demo")
    assert result == {"a": 1, "b": 99, "c": 3}


def test_save_and_load_roundtrip(tmp_config):
    path, cm = tmp_config
    cm.load()
    cm.set("app", {"modules_enabled": ["demo"]})
    cm.set("demo", {"msg": "hi"})

    cm2 = ConfigManager(path)
    cm2.load()
    assert cm2.get("app") == {"modules_enabled": ["demo"]}
    assert cm2.get("demo") == {"msg": "hi"}


def test_get_unknown_namespace(tmp_config):
    _, cm = tmp_config
    cm.load()
    assert cm.get("nonexistent") == {}


def test_load_invalid_json(tmp_config):
    path, cm = tmp_config
    path.write_text("not valid json!!!", encoding="utf-8")
    cm.load()
    assert cm.get_root() == {}
