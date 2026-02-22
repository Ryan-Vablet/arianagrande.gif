from __future__ import annotations

from PyQt6.QtCore import QMimeData, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDrag, QPainter, QPixmap
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

MIME_PANEL = "application/x-collapsible-panel"
_DRAG_THRESHOLD = 6


class _DragHandle(QLabel):
    """Small grip icon that initiates panel drag."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("⠿", parent)
        self.setStyleSheet(
            f"color: {THEME['text_title']}; font-size: 14px;"
            " background: transparent; padding: 0;"
        )
        self.setFixedWidth(16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _ResizeHandle(QFrame):
    """Bottom-edge handle for vertical panel resizing."""

    MIN_PANEL_HEIGHT = 60

    def __init__(self, panel: CollapsiblePanel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._dragging = False
        self._start_y = 0
        self._start_height = 0
        self.setFixedHeight(6)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setStyleSheet(
            "QFrame { background: transparent; border: none; }"
            "QFrame:hover { background: rgba(102, 238, 255, 0.15); }"
        )

    def mousePressEvent(self, event: any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_y = event.globalPosition().toPoint().y()
            self._start_height = self._panel.height()

    def mouseMoveEvent(self, event: any) -> None:
        if self._dragging:
            dy = event.globalPosition().toPoint().y() - self._start_y
            new_h = max(self.MIN_PANEL_HEIGHT, self._start_height + dy)
            self._panel.setMinimumHeight(new_h)
            self._panel.setMaximumHeight(new_h)

    def mouseReleaseEvent(self, event: any) -> None:
        if self._dragging:
            current_h = self._panel.height()
            self._panel.setMinimumHeight(current_h)
            self._panel.setMaximumHeight(current_h)
        self._dragging = False


class _DropIndicator(QFrame):
    """Thin colored line showing where a dragged panel will land."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self.setStyleSheet(f"background: {THEME['text_accent']};")
        self.hide()


class CollapsiblePanel(QFrame):
    """Wraps a module's widget with a collapsible header bar, optional drag and resize."""

    def __init__(
        self,
        title: str,
        content: QWidget,
        collapsible: bool = True,
        collapsed: bool = False,
        resizable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._collapsible = collapsible
        self._collapsed = collapsed
        self._resizable = resizable
        self._content = content
        self._drag_start: QPoint | None = None

        self.setStyleSheet(
            f"CollapsiblePanel {{ background: {THEME['bg_panel']};"
            f" border: 1px solid {THEME['border_panel']}; border-radius: 4px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QFrame()
        self._header.setStyleSheet(
            f"background: {THEME['bg_panel_header']};"
            f" border-top-left-radius: 4px; border-top-right-radius: 4px;"
        )
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(4, 4, 10, 4)
        header_layout.setSpacing(4)

        self._handle = _DragHandle()
        header_layout.addWidget(self._handle)

        self._arrow = QLabel("▾")
        self._arrow.setStyleSheet(
            f"font-size: 11px; color: {THEME['text_title']}; background: transparent;"
        )
        self._arrow.setFixedWidth(12)
        if not collapsible:
            self._arrow.setVisible(False)
        header_layout.addWidget(self._arrow)

        self._title_label = QLabel(title.upper())
        self._title_label.setStyleSheet(
            f"font-family: monospace; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 1.5px; color: {THEME['text_title']}; background: transparent;"
        )
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        layout.addWidget(self._header)

        # Content wrapper
        self._content_wrapper = QFrame()
        self._content_wrapper.setStyleSheet("background: transparent; border: none;")
        wrapper_layout = QVBoxLayout(self._content_wrapper)
        wrapper_layout.setContentsMargins(8, 6, 8, 8)
        wrapper_layout.addWidget(content)
        layout.addWidget(self._content_wrapper)

        # Resize handle
        if resizable:
            self._resize_handle = _ResizeHandle(self)
            layout.addWidget(self._resize_handle)

        if collapsed:
            self._content_wrapper.setVisible(False)
            self._arrow.setText("▸")

    def mousePressEvent(self, event: any) -> None:
        local_pos = event.pos()
        if local_pos.y() <= self._header.height():
            handle_rect = self._handle.geometry()
            if handle_rect.contains(self._header.mapFrom(self, local_pos)):
                self._drag_start = event.globalPosition().toPoint()
                return
            if self._collapsible:
                self._toggle()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: any) -> None:
        if self._drag_start is not None:
            dist = (event.globalPosition().toPoint() - self._drag_start).manhattanLength()
            if dist >= _DRAG_THRESHOLD:
                self._start_drag()
                self._drag_start = None
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: any) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def _start_drag(self) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_PANEL, b"")
        drag.setMimeData(mime)

        pixmap = QPixmap(self._header.size())
        self._header.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        self.setStyleSheet(
            f"CollapsiblePanel {{ background: {THEME['bg_panel']};"
            f" border: 1px solid {THEME['text_accent']}; border-radius: 4px;"
            f" opacity: 0.5; }}"
        )

        drag.exec(Qt.DropAction.MoveAction)

        self.setStyleSheet(
            f"CollapsiblePanel {{ background: {THEME['bg_panel']};"
            f" border: 1px solid {THEME['border_panel']}; border-radius: 4px; }}"
        )

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._content_wrapper.setVisible(not self._collapsed)
        self._arrow.setText("▸" if self._collapsed else "▾")
        if self._resizable:
            if self._collapsed:
                self.setMinimumHeight(0)
                self.setMaximumHeight(self._header.sizeHint().height() + 12)
            else:
                self.setMinimumHeight(0)
                self.setMaximumHeight(16777215)


class _PanelColumn(QWidget):
    """Container for a column of CollapsiblePanels that supports drag-and-drop reorder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._indicator = _DropIndicator(self)
        self._drop_index: int = -1
        self._panels: list[CollapsiblePanel] = []

    def add_panel(self, panel: CollapsiblePanel) -> None:
        self._panels.append(panel)
        self._layout.insertWidget(self._layout.count(), panel)

    def finish(self) -> None:
        self._layout.addStretch()

    def _panel_count(self) -> int:
        return len(self._panels)

    def _calc_drop_index(self, y: int) -> int:
        for i, p in enumerate(self._panels):
            mid = p.y() + p.height() // 2
            if y < mid:
                return i
        return len(self._panels)

    def dragEnterEvent(self, event: any) -> None:
        if event.mimeData().hasFormat(MIME_PANEL):
            source = event.source()
            if isinstance(source, CollapsiblePanel) and source in self._panels:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event: any) -> None:
        if not event.mimeData().hasFormat(MIME_PANEL):
            return
        idx = self._calc_drop_index(event.position().toPoint().y())
        self._drop_index = idx
        if idx < len(self._panels):
            iy = self._panels[idx].y() - 2
        else:
            last = self._panels[-1] if self._panels else None
            iy = (last.y() + last.height() + 2) if last else 0
        self._indicator.setGeometry(0, iy, self.width(), 3)
        self._indicator.show()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: any) -> None:
        self._indicator.hide()
        self._drop_index = -1

    def dropEvent(self, event: any) -> None:
        self._indicator.hide()
        source = event.source()
        if not isinstance(source, CollapsiblePanel) or source not in self._panels:
            event.ignore()
            return

        old_idx = self._panels.index(source)
        new_idx = self._drop_index
        if new_idx < 0:
            event.ignore()
            return
        if new_idx > old_idx:
            new_idx -= 1
        if old_idx == new_idx:
            event.accept()
            return

        self._panels.pop(old_idx)
        self._panels.insert(new_idx, source)

        self._layout.removeWidget(source)
        self._layout.insertWidget(new_idx, source)

        event.acceptProposedAction()


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

    def _build_ui(self) -> None:
        # Toolbar
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

        # Central splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Primary area
        primary_scroll = QScrollArea()
        primary_scroll.setWidgetResizable(True)
        primary_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._primary_column = _PanelColumn()
        primary_scroll.setWidget(self._primary_column)

        # Sidebar
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._sidebar_column = _PanelColumn()
        sidebar_scroll.setWidget(self._sidebar_column)

        splitter.addWidget(primary_scroll)
        splitter.addWidget(sidebar_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([480, 220])

        self.setCentralWidget(splitter)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _populate_panels(self) -> None:
        for reg in self._core.panels.get_panels("primary"):
            widget = reg.factory()
            panel = CollapsiblePanel(
                reg.title, widget, reg.collapsible, reg.default_collapsed,
                resizable=reg.resizable,
            )
            self._primary_column.add_panel(panel)
        self._primary_column.finish()

        for reg in self._core.panels.get_panels("sidebar"):
            widget = reg.factory()
            panel = CollapsiblePanel(
                reg.title, widget, reg.collapsible, reg.default_collapsed,
                resizable=reg.resizable,
            )
            self._sidebar_column.add_panel(panel)
        self._sidebar_column.finish()

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

    def _toggle_always_on_top(self, checked: bool) -> None:
        cfg = self._core.get_config("core_capture")
        cfg.setdefault("display", {})["always_on_top"] = checked
        self._core.save_config("core_capture", cfg)

    def show_status_message(self, text: str, timeout_ms: int = 0) -> None:
        self._status_label.setText(text)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._status_label.setText(""))
