from __future__ import annotations

import pytest

from src.models.geometry import BoundingBox


def test_default_values():
    bb = BoundingBox()
    assert bb.top == 900
    assert bb.left == 500
    assert bb.width == 400
    assert bb.height == 50


def test_from_dict_all_fields():
    bb = BoundingBox.from_dict({"top": 100, "left": 200, "width": 300, "height": 60})
    assert bb.top == 100
    assert bb.left == 200
    assert bb.width == 300
    assert bb.height == 60


def test_from_dict_missing_fields_uses_defaults():
    bb = BoundingBox.from_dict({})
    assert bb.top == 900
    assert bb.left == 500
    assert bb.width == 400
    assert bb.height == 50


def test_to_dict_roundtrip():
    bb = BoundingBox(top=10, left=20, width=30, height=40)
    d = bb.to_dict()
    bb2 = BoundingBox.from_dict(d)
    assert bb == bb2


def test_as_mss_region_applies_offset():
    bb = BoundingBox(top=100, left=200, width=300, height=50)
    region = bb.as_mss_region(monitor_offset_x=1920, monitor_offset_y=0)
    assert region == {
        "top": 100,
        "left": 2120,
        "width": 300,
        "height": 50,
    }


def test_as_mss_region_no_offset():
    bb = BoundingBox(top=100, left=200, width=300, height=50)
    region = bb.as_mss_region()
    assert region == {
        "top": 100,
        "left": 200,
        "width": 300,
        "height": 50,
    }
