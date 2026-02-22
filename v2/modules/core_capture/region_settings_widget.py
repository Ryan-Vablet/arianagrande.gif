"""Reusable capture region settings widget.

Any module that registers a capture region can embed this widget in its
settings tab to give the user bbox spinboxes and a live preview of the
region's captured frames.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def _label(text: str, width: int = 55) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #999; font-size: 11px;")
    lbl.setMinimumWidth(width)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _spin(min_val: int, max_val: int, value: int = 0) -> QSpinBox:
    s = QSpinBox()
    s.setRange(min_val, max_val)
    s.setValue(value)
    s.setMinimumWidth(70)
    s.setMaximumWidth(100)
    return s


class RegionSettingsWidget(QWidget):
    """Bbox spinboxes + live preview for a registered capture region.

    Usage::

        w = RegionSettingsWidget(core, region_id="cast_bar")
        layout.addWidget(w)
    """

    def __init__(
        self,
        core: Any,
        region_id: str,
        show_preview: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._core = core
        self._region_id = region_id
        self._show_preview = show_preview
        self._preview_label: QLabel | None = None
        self._build_ui()
        self._populate()
        self._connect_signals()
        self._subscribe_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        self._spin_top = _spin(0, 9999)
        self._spin_left = _spin(0, 9999)
        self._spin_width = _spin(1, 9999)
        self._spin_height = _spin(1, 9999)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)

        grid.addWidget(_label("Top"), 0, 0)
        grid.addWidget(self._spin_top, 0, 1)
        grid.addWidget(_label("Left"), 0, 2)
        grid.addWidget(self._spin_left, 0, 3)

        grid.addWidget(_label("Width"), 1, 0)
        grid.addWidget(self._spin_width, 1, 1)
        grid.addWidget(_label("Height"), 1, 2)
        grid.addWidget(self._spin_height, 1, 3)

        capped = QWidget()
        capped.setLayout(grid)
        capped.setMaximumWidth(360)
        cap_row = QHBoxLayout()
        cap_row.setContentsMargins(0, 0, 0, 0)
        cap_row.addWidget(capped)
        cap_row.addStretch()
        layout.addLayout(cap_row)

        if self._show_preview:
            self._preview_label = QLabel()
            self._preview_label.setMinimumHeight(50)
            self._preview_label.setStyleSheet(
                "background: #1a1a2a; border: 1px solid #3a3a4a; border-radius: 3px;"
            )
            self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._preview_label.setText("Start capture to see preview")
            layout.addWidget(self._preview_label)

    def _populate(self) -> None:
        bb = self._core.capture_regions.get_bbox_dict(self._region_id)
        self._spin_top.setValue(int(bb.get("top", 0)))
        self._spin_left.setValue(int(bb.get("left", 0)))
        self._spin_width.setValue(int(bb.get("width", 100)))
        self._spin_height.setValue(int(bb.get("height", 50)))

    def _connect_signals(self) -> None:
        for w in (self._spin_top, self._spin_left,
                  self._spin_width, self._spin_height):
            w.valueChanged.connect(self._save)

    def _save(self) -> None:
        region = self._core.capture_regions.get(self._region_id)
        if region is None:
            return
        cfg = self._core.get_config(region.config_namespace)
        cfg[region.config_key] = {
            "top": self._spin_top.value(),
            "left": self._spin_left.value(),
            "width": self._spin_width.value(),
            "height": self._spin_height.value(),
        }
        self._core.save_config(region.config_namespace, cfg)

    def _subscribe_preview(self) -> None:
        if not self._show_preview:
            return
        self._core.subscribe(
            "capture.region_frame", self._on_region_frame,
        )

    def _on_region_frame(self, region_id: str = "", qimg: Any = None) -> None:
        if region_id != self._region_id:
            return
        if self._preview_label is None or qimg is None or qimg.isNull():
            return
        pixmap = QPixmap.fromImage(qimg)
        avail_w = max(50, self._preview_label.width() - 4)
        scaled = pixmap.scaledToWidth(
            avail_w, Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)
