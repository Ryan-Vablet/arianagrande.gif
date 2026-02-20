from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
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


class CollapsiblePanel(QFrame):
    """Wraps a module's widget with a collapsible header bar."""

    def __init__(
        self,
        title: str,
        content: QWidget,
        collapsible: bool = True,
        collapsed: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._collapsible = collapsible
        self._collapsed = collapsed
        self._content = content

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
            f" padding: 6px 10px;"
        )
        self._header.setCursor(Qt.CursorShape.PointingHandCursor if collapsible else Qt.CursorShape.ArrowCursor)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(8)

        self._arrow = QLabel("▾")
        self._arrow.setStyleSheet(
            f"font-size: 12px; color: {THEME['text_title']}; background: transparent;"
        )
        self._arrow.setFixedWidth(14)
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

        if collapsed:
            self._content_wrapper.setVisible(False)
            self._arrow.setText("▸")

    def mousePressEvent(self, event: any) -> None:
        if not self._collapsible:
            return super().mousePressEvent(event)
        local_pos = event.pos()
        if local_pos.y() <= self._header.height():
            self._toggle()
        else:
            super().mousePressEvent(event)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._content_wrapper.setVisible(not self._collapsed)
        self._arrow.setText("▸" if self._collapsed else "▾")


class MainWindow(QMainWindow):
    settings_requested = pyqtSignal()

    def __init__(self, core: Core) -> None:
        super().__init__()
        self._core = core
        self.setWindowTitle("arianagrande.gif")
        self.setMinimumSize(700, 550)
        self._build_ui()
        self._populate_panels()

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
        primary_widget = QWidget()
        self._primary_layout = QVBoxLayout(primary_widget)
        self._primary_layout.setContentsMargins(8, 8, 4, 8)
        self._primary_layout.setSpacing(8)
        primary_scroll.setWidget(primary_widget)

        # Sidebar
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_widget = QWidget()
        self._sidebar_layout = QVBoxLayout(sidebar_widget)
        self._sidebar_layout.setContentsMargins(4, 8, 8, 8)
        self._sidebar_layout.setSpacing(8)
        sidebar_scroll.setWidget(sidebar_widget)

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
            panel = CollapsiblePanel(reg.title, widget, reg.collapsible, reg.default_collapsed)
            self._primary_layout.addWidget(panel)
        self._primary_layout.addStretch()

        for reg in self._core.panels.get_panels("sidebar"):
            widget = reg.factory()
            panel = CollapsiblePanel(reg.title, widget, reg.collapsible, reg.default_collapsed)
            self._sidebar_layout.addWidget(panel)
        self._sidebar_layout.addStretch()

    def _show_windows_menu(self) -> None:
        menu = self._build_windows_menu()
        menu.exec(self._windows_btn.mapToGlobal(self._windows_btn.rect().bottomLeft()))

    def _build_windows_menu(self) -> QMenu:
        menu = QMenu(self)
        entries = self._core.windows.list_menu_entries()
        if not entries:
            action = menu.addAction("(no windows registered)")
            action.setEnabled(False)
            return menu
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
