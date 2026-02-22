from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class CaptureRegion:
    """A registered screen capture region owned by a module."""

    id: str
    owner: str
    config_namespace: str
    config_key: str
    default_bbox: dict
    overlay_color: str = "#00FF00"
    label: str = ""
    callback: Optional[Callable[["np.ndarray"], None]] = None
    overlay_draw: Optional[Callable[["QPainter", "QRect"], None]] = None
    order: int = 0


class CaptureRegionRegistry:
    """Manages capture regions that modules register for independent screen grabs."""

    def __init__(self, config: Any) -> None:
        self._config = config
        self._regions: dict[str, CaptureRegion] = {}

    def register(
        self,
        *,
        id: str,
        owner: str,
        config_namespace: str,
        config_key: str,
        default_bbox: dict,
        overlay_color: str = "#00FF00",
        label: str = "",
        callback: Optional[Callable] = None,
        overlay_draw: Optional[Callable] = None,
        order: int = 0,
    ) -> None:
        cfg = self._config.get(config_namespace)
        if config_key not in cfg:
            cfg[config_key] = dict(default_bbox)
            self._config.set(config_namespace, cfg)

        self._regions[id] = CaptureRegion(
            id=id,
            owner=owner,
            config_namespace=config_namespace,
            config_key=config_key,
            default_bbox=default_bbox,
            overlay_color=overlay_color,
            label=label,
            callback=callback,
            overlay_draw=overlay_draw,
            order=order,
        )
        logger.info("Registered capture region '%s' (owner=%s)", id, owner)

    def get_all(self) -> list[CaptureRegion]:
        return sorted(self._regions.values(), key=lambda r: r.order)

    def get(self, region_id: str) -> CaptureRegion | None:
        return self._regions.get(region_id)

    def get_bbox_dict(self, region_id: str) -> dict:
        reg = self._regions.get(region_id)
        if reg is None:
            return {}
        cfg = self._config.get(reg.config_namespace)
        return cfg.get(reg.config_key, dict(reg.default_bbox))

    def unregister(self, region_id: str) -> None:
        self._regions.pop(region_id, None)

    def teardown_module(self, module_key: str) -> None:
        to_remove = [k for k, v in self._regions.items() if v.owner == module_key]
        for rid in to_remove:
            del self._regions[rid]
