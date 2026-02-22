from __future__ import annotations

import pytest

from src.core.config_manager import ConfigManager
from src.core.capture_region_registry import CaptureRegionRegistry


@pytest.fixture
def cfg(tmp_path):
    c = ConfigManager(tmp_path / "config.json")
    c.load()
    c.set("my_module", {})
    return c


@pytest.fixture
def registry(cfg):
    return CaptureRegionRegistry(cfg)


def test_register_and_get(registry):
    registry.register(
        id="test_region",
        owner="test_mod",
        config_namespace="my_module",
        config_key="bbox",
        default_bbox={"top": 10, "left": 20, "width": 100, "height": 50},
        overlay_color="#FF0000",
        label="Test",
    )
    region = registry.get("test_region")
    assert region is not None
    assert region.owner == "test_mod"
    assert region.overlay_color == "#FF0000"
    assert region.label == "Test"


def test_get_all_sorted_by_order(registry):
    registry.register(
        id="b", owner="m", config_namespace="my_module", config_key="b",
        default_bbox={"top": 0, "left": 0, "width": 1, "height": 1}, order=20,
    )
    registry.register(
        id="a", owner="m", config_namespace="my_module", config_key="a",
        default_bbox={"top": 0, "left": 0, "width": 1, "height": 1}, order=10,
    )
    regions = registry.get_all()
    assert [r.id for r in regions] == ["a", "b"]


def test_get_bbox_dict_reads_from_config(registry, cfg):
    registry.register(
        id="r1", owner="m", config_namespace="my_module", config_key="my_bbox",
        default_bbox={"top": 100, "left": 200, "width": 300, "height": 40},
    )
    bb = registry.get_bbox_dict("r1")
    assert bb["top"] == 100
    assert bb["width"] == 300

    cfg.set("my_module", {"my_bbox": {"top": 999, "left": 0, "width": 50, "height": 10}})
    bb2 = registry.get_bbox_dict("r1")
    assert bb2["top"] == 999


def test_default_bbox_written_to_config(registry, cfg):
    registry.register(
        id="r1", owner="m", config_namespace="my_module", config_key="auto_bbox",
        default_bbox={"top": 55, "left": 66, "width": 77, "height": 88},
    )
    stored = cfg.get("my_module").get("auto_bbox")
    assert stored == {"top": 55, "left": 66, "width": 77, "height": 88}


def test_existing_config_not_overwritten(registry, cfg):
    cfg.set("my_module", {"existing_bbox": {"top": 1, "left": 2, "width": 3, "height": 4}})
    registry.register(
        id="r1", owner="m", config_namespace="my_module", config_key="existing_bbox",
        default_bbox={"top": 99, "left": 99, "width": 99, "height": 99},
    )
    stored = cfg.get("my_module").get("existing_bbox")
    assert stored["top"] == 1


def test_unregister(registry):
    registry.register(
        id="r1", owner="m", config_namespace="my_module", config_key="b",
        default_bbox={"top": 0, "left": 0, "width": 1, "height": 1},
    )
    assert registry.get("r1") is not None
    registry.unregister("r1")
    assert registry.get("r1") is None


def test_teardown_module(registry):
    registry.register(
        id="r1", owner="mod_a", config_namespace="my_module", config_key="b1",
        default_bbox={"top": 0, "left": 0, "width": 1, "height": 1},
    )
    registry.register(
        id="r2", owner="mod_b", config_namespace="my_module", config_key="b2",
        default_bbox={"top": 0, "left": 0, "width": 1, "height": 1},
    )
    registry.teardown_module("mod_a")
    assert registry.get("r1") is None
    assert registry.get("r2") is not None


def test_get_nonexistent_returns_none(registry):
    assert registry.get("nope") is None
    assert registry.get_bbox_dict("nope") == {}


def test_callback_and_overlay_draw_stored(registry):
    cb = lambda frame: None
    draw = lambda painter, rect: None
    registry.register(
        id="r1", owner="m", config_namespace="my_module", config_key="b",
        default_bbox={"top": 0, "left": 0, "width": 1, "height": 1},
        callback=cb, overlay_draw=draw,
    )
    region = registry.get("r1")
    assert region.callback is cb
    assert region.overlay_draw is draw
