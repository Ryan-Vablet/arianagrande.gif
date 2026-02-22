from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QMimeData, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDrag, QPainter, QPen, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.core import Core
from src.ui.themes import THEME

logger = logging.getLogger(__name__)

_LAYOUT_NS = "ui_layout"
_MIN_PANEL_H = 60
_PAD = 10


class _DragHandle(QLabel):
    """Small grip icon in the panel header for drag-and-drop reordering."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("⠿", parent)
        self.setFixedWidth(16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(
            f"color: {THEME['text_label']}; font-size: 13px; background: transparent;"
        )


class _ResizeHandle(QFrame):
    """Bottom-edge grip for vertically resizing a panel."""

    def __init__(self, panel: CollapsiblePanel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._dragging = False
        self._start_y = 0
        self._start_height = 0
        self.setFixedHeight(8)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setStyleSheet(
            "QFrame { background: transparent; border: none; }"
            "QFrame:hover { background: rgba(102, 238, 255, 0.08); }"
        )

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(THEME["text_label"]))
        pen.setWidth(1)
        p.setPen(pen)
        cx = self.width() // 2
        cy = self.height() // 2
        for dx in (-8, 0, 8):
            p.drawPoint(cx + dx, cy)
        p.end()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_y = event.globalPosition().toPoint().y()
            self._start_height = self._panel.height()

    def mouseMoveEvent(self, event: Any) -> None:
        if self._dragging:
            dy = event.globalPosition().toPoint().y() - self._start_y
            new_h = max(_MIN_PANEL_H, self._start_height + dy)
            self._panel.setMinimumHeight(new_h)
            self._panel.setMaximumHeight(new_h)

    def mouseReleaseEvent(self, event: Any) -> None:
        if self._dragging:
            h = self._panel.height()
            self._panel.setMinimumHeight(h)
            self._panel.setMaximumHeight(h)
            self._panel._save_layout()
        self._dragging = False


class _DropIndicator(QFrame):
    """Thin coloured line shown during drag-and-drop to indicate insertion point."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self.setStyleSheet(f"background: {THEME['text_accent']}; border-radius: 1px;")
        self.hide()


class CollapsiblePanel(QFrame):
    """Wraps a module widget with a collapsible header, optional drag handle and resize grip."""

    def __init__(
        self,
        title: str,
        content: QWidget,
        panel_id: str = "",
        collapsible: bool = True,
        collapsed: bool = False,
        resizable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel_id = panel_id
        self._collapsible = collapsible
        self._collapsed = collapsed
        self._resizable = resizable
        self._content = content
        self._core: Core | None = None

        self.setStyleSheet(
            f"CollapsiblePanel {{ background: {THEME['bg_panel']};"
            f" border: 1px solid {THEME['border_panel']}; border-radius: 4px; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Header ---
        self._header = QFrame()
        self._header.setStyleSheet(
            f"background: {THEME['bg_panel_header']};"
            f" border-top-left-radius: 4px; border-top-right-radius: 4px;"
        )
        hdr = QHBoxLayout(self._header)
        hdr.setContentsMargins(4, 4, 10, 4)
        hdr.setSpacing(4)

        self._drag_handle = _DragHandle()
        hdr.addWidget(self._drag_handle)

        self._arrow = QLabel("▾")
        self._arrow.setStyleSheet(
            f"font-size: 12px; color: {THEME['text_title']}; background: transparent;"
        )
        self._arrow.setFixedWidth(14)
        if not collapsible:
            self._arrow.setVisible(False)
        hdr.addWidget(self._arrow)

        self._title_label = QLabel(title.upper())
        self._title_label.setStyleSheet(
            f"font-family: monospace; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 1.5px; color: {THEME['text_title']}; background: transparent;"
        )
        hdr.addWidget(self._title_label)
        hdr.addStretch()

        root.addWidget(self._header)

        # --- Content wrapper ---
        self._content_wrapper = QFrame()
        self._content_wrapper.setStyleSheet("background: transparent; border: none;")
        cw = QVBoxLayout(self._content_wrapper)
        cw.setContentsMargins(8, 6, 8, 8)
        cw.addWidget(content)
        root.addWidget(self._content_wrapper)

        # --- Resize handle (only for resizable panels) ---
        self._resize_handle: _ResizeHandle | None = None
        if resizable:
            self._resize_handle = _ResizeHandle(self)
            root.addWidget(self._resize_handle)

        if collapsed:
            self._content_wrapper.setVisible(False)
            self._arrow.setText("▸")
            if self._resize_handle:
                self._resize_handle.setVisible(False)

    def set_core(self, core: Core) -> None:
        self._core = core

    # --- Collapse ---

    def mousePressEvent(self, event: Any) -> None:
        if not self._collapsible:
            return super().mousePressEvent(event)
        local = event.pos()
        if local.y() <= self._header.height():
            if local.x() <= self._drag_handle.width() + 8:
                self._start_drag(event)
                return
            self._toggle()
        else:
            super().mousePressEvent(event)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._content_wrapper.setVisible(not self._collapsed)
        self._arrow.setText("▸" if self._collapsed else "▾")
        if self._resizable:
            if self._resize_handle:
                self._resize_handle.setVisible(not self._collapsed)
            if self._collapsed:
                self.setMinimumHeight(0)
                self.setMaximumHeight(self._header.sizeHint().height() + 12)
            else:
                self.setMinimumHeight(0)
                self.setMaximumHeight(16777215)
        self._save_layout()

    # --- Drag-and-drop ---

    def _start_drag(self, event: Any) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.panel_id)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    # --- Persistence helper ---

    def _save_layout(self) -> None:
        column = self.parent()
        if isinstance(column, _PanelColumn):
            column.save_layout()

    def apply_saved_height(self, height: int) -> None:
        if self._resizable and not self._collapsed and height >= _MIN_PANEL_H:
            self.setMinimumHeight(height)
            self.setMaximumHeight(height)


class _PanelColumn(QWidget):
    """Container that holds panels for one area and manages drag-and-drop reordering."""

    def __init__(self, area: str, core: Core, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._area = area
        self._core = core
        self._panels: list[CollapsiblePanel] = []
        self._indicator = _DropIndicator(self)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        self.setAcceptDrops(True)

    def add_panel(self, panel: CollapsiblePanel) -> None:
        panel.set_core(self._core)
        self._panels.append(panel)
        self._layout.addWidget(panel)

    def finish(self) -> None:
        self._layout.addStretch()

    # --- Drag-and-drop ---

    def dragEnterEvent(self, event: Any) -> None:
        if event.mimeData().hasText():
            pid = event.mimeData().text()
            if any(p.panel_id == pid for p in self._panels):
                event.acceptProposedAction()

    def dragMoveEvent(self, event: Any) -> None:
        idx = self._insert_index(event.position().toPoint())
        self._show_indicator(idx)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: Any) -> None:
        self._indicator.hide()

    def dropEvent(self, event: Any) -> None:
        self._indicator.hide()
        pid = event.mimeData().text()
        src = next((p for p in self._panels if p.panel_id == pid), None)
        if src is None:
            return

        target_idx = self._insert_index(event.position().toPoint())
        old_idx = self._panels.index(src)
        if old_idx == target_idx or old_idx + 1 == target_idx:
            return

        self._panels.remove(src)
        if target_idx > old_idx:
            target_idx -= 1
        self._panels.insert(target_idx, src)

        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        for p in self._panels:
            self._layout.addWidget(p)
        self._layout.addStretch()

        self.save_layout()
        event.acceptProposedAction()

    def _insert_index(self, pos: QPoint) -> int:
        for i, p in enumerate(self._panels):
            mid = p.y() + p.height() // 2
            if pos.y() < mid:
                return i
        return len(self._panels)

    def _show_indicator(self, idx: int) -> None:
        if idx < len(self._panels):
            y = self._panels[idx].y() - 2
        elif self._panels:
            last = self._panels[-1]
            y = last.y() + last.height() + 2
        else:
            y = 0
        self._indicator.setGeometry(0, y, self.width(), 3)
        self._indicator.show()
        self._indicator.raise_()

    # --- Persistence ---

    def save_layout(self) -> None:
        cfg = self._core.get_config(_LAYOUT_NS) or {}
        order = cfg.setdefault("panel_order", {})
        heights = cfg.setdefault("panel_heights", {})
        collapsed = cfg.setdefault("panel_collapsed", {})

        order[self._area] = [p.panel_id for p in self._panels]
        for p in self._panels:
            collapsed[p.panel_id] = p._collapsed
            if p._resizable and not p._collapsed:
                heights[p.panel_id] = p.height()

        self._core.save_config(_LAYOUT_NS, cfg)


class MainWindow(QMainWindow):
    settings_requested = pyqtSignal()

    def __init__(self, core: Core) -> None:
        super().__init__()
        self._core = core
        self.setWindowTitle("arianagrande.gif")
        self.setMinimumSize(700, 550)
        self._build_ui()
        self._populate_panels()
        self._apply_always_on_top()
        self._core.subscribe("config.changed", self._on_config_changed)

    # --- Config reactivity ---

    def _on_config_changed(self, namespace: str = "") -> None:
        if namespace == "core_capture":
            self._apply_always_on_top()

    def _apply_always_on_top(self) -> None:
        cfg = self._core.get_config("core_capture")
        aot = cfg.get("display", {}).get("always_on_top", False)
        flags = self.windowFlags()
        is_on_top = bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        if aot == is_on_top:
            return
        if aot:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def _toggle_always_on_top(self, checked: bool) -> None:
        cfg = self._core.get_config("core_capture")
        cfg.setdefault("display", {})["always_on_top"] = checked
        self._core.save_config("core_capture", cfg)

    # --- UI build ---

    def _build_ui(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self.settings_requested.emit)
        toolbar.addWidget(settings_btn)

        self._windows_btn = QPushButton("Windows ▾")
        self._windows_btn.clicked.connect(self._show_windows_menu)
        toolbar.addWidget(self._windows_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {THEME['text_label']}; font-size: 11px; padding-right: 8px;"
        )
        toolbar.addWidget(self._status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(_PAD // 2)

        primary_scroll = QScrollArea()
        primary_scroll.setWidgetResizable(True)
        primary_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._primary_column = _PanelColumn("primary", self._core)
        self._primary_column._layout.setContentsMargins(_PAD, _PAD, _PAD // 2, _PAD)
        primary_scroll.setWidget(self._primary_column)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._sidebar_column = _PanelColumn("sidebar", self._core)
        self._sidebar_column._layout.setContentsMargins(_PAD // 2, _PAD, _PAD, _PAD)
        sidebar_scroll.setWidget(self._sidebar_column)

        splitter.addWidget(primary_scroll)
        splitter.addWidget(sidebar_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([480, 220])

        self.setCentralWidget(splitter)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _populate_panels(self) -> None:
        layout_cfg = self._core.get_config(_LAYOUT_NS) or {}
        saved_order = layout_cfg.get("panel_order", {})
        saved_heights = layout_cfg.get("panel_heights", {})
        saved_collapsed = layout_cfg.get("panel_collapsed", {})

        for area, column in (
            ("primary", self._primary_column),
            ("sidebar", self._sidebar_column),
        ):
            regs = self._core.panels.get_panels(area)
            reg_map = {r.id: r for r in regs}
            ordered_ids = saved_order.get(area, [])

            ordered: list[Any] = []
            for pid in ordered_ids:
                if pid in reg_map:
                    ordered.append(reg_map.pop(pid))
            for r in regs:
                if r.id in reg_map:
                    ordered.append(r)

            for reg in ordered:
                widget = reg.factory()
                is_collapsed = saved_collapsed.get(reg.id, reg.default_collapsed)
                panel = CollapsiblePanel(
                    reg.title, widget,
                    panel_id=reg.id,
                    collapsible=reg.collapsible,
                    collapsed=is_collapsed,
                    resizable=reg.resizable,
                )
                column.add_panel(panel)

                h = saved_heights.get(reg.id)
                if h is not None:
                    panel.apply_saved_height(h)

            column.finish()

    # --- Windows menu ---

    def _show_windows_menu(self) -> None:
        menu = self._build_windows_menu()
        menu.exec(self._windows_btn.mapToGlobal(self._windows_btn.rect().bottomLeft()))

    def _build_windows_menu(self) -> QMenu:
        menu = QMenu(self)

        cfg = self._core.get_config("core_capture")
        aot = cfg.get("display", {}).get("always_on_top", False)
        aot_action = menu.addAction("Always on Top")
        aot_action.setCheckable(True)
        aot_action.setChecked(aot)
        aot_action.triggered.connect(self._toggle_always_on_top)

        entries = self._core.windows.list_menu_entries()
        if entries:
            menu.addSeparator()
        for entry in entries:
            action = menu.addAction(entry.title or entry.id)
            action.setCheckable(True)
            action.setChecked(self._core.windows.is_visible(entry.id))
            action.triggered.connect(
                lambda checked, id=entry.id: self._core.windows.toggle(id)
            )
        return menu

    def show_status_message(self, text: str, timeout_ms: int = 0) -> None:
        self._status_label.setText(text)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._status_label.setText(""))
