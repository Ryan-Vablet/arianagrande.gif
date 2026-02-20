from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BoundingBox:
    """Screen-relative bounding box for a capture region."""
    top: int = 900
    left: int = 500
    width: int = 400
    height: int = 50

    def as_mss_region(self, monitor_offset_x: int = 0, monitor_offset_y: int = 0) -> dict:
        return {
            "top": self.top + monitor_offset_y,
            "left": self.left + monitor_offset_x,
            "width": self.width,
            "height": self.height,
        }

    def to_dict(self) -> dict:
        return {"top": self.top, "left": self.left, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, d: dict) -> BoundingBox:
        return cls(
            top=int(d.get("top", 900)),
            left=int(d.get("left", 500)),
            width=int(d.get("width", 400)),
            height=int(d.get("height", 50)),
        )
