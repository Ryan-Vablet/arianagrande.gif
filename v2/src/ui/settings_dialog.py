from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.core import Core
from src.ui.themes import THEME


def _section_frame(title: str, content: QWidget) -> QFrame:
    f = QFrame()
    f.setObjectName("sectionFrame")
    layout = QVBoxLayout(f)
    layout.setContentsMargins(10, 8, 10, 10)
    layout.setSpacing(8)

    title_label = QLabel(title.upper())
    title_label.setObjectName("sectionTitle")
    title_label.setStyleSheet(
        f"font-family: monospace; font-size: 10px; font-weight: bold;"
        f" letter-spacing: 1.5px; color: {THEME['text_title']};"
        f" background: transparent; border: none;"
    )
    layout.addWidget(title_label)
    layout.addWidget(content)

    f.setStyleSheet(
        f"QFrame#sectionFrame {{ background: {THEME['bg_section']};"
        f" border: 1px solid {THEME['border_section']}; border-radius: 4px; }}"
    )
    return f


class SettingsDialog(QDialog):
    def __init__(self, core: Core, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core = core
        self._user_resized = False
        self.setWindowTitle("Settings")
        self.setMinimumSize(300, 200)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        self._build_tabs()

    def _build_tabs(self) -> None:
        for tab_info in self._core.settings.get_tabs():
            tab_widget = self._build_tab(tab_info)
            title = tab_info["title"] or tab_info["path"].replace("_", " ").title()
            self._tabs.addTab(tab_widget, title)

    def _build_tab(self, tab_info: dict) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)

        if tab_info.get("widget_factory"):
            layout.addWidget(tab_info["widget_factory"]())

        for child in tab_info.get("children", []):
            title = child["title"] or child["path"].rsplit("/", 1)[-1].replace("_", " ").title()
            widget = child["widget_factory"]()
            section = _section_frame(title, widget)
            layout.addWidget(section)

        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def show_or_raise(self) -> None:
        if self.isVisible():
            self.raise_()
            self.activateWindow()
        else:
            if not self._user_resized:
                self._auto_fit()
            self.show()

    def _auto_fit(self) -> None:
        """Resize to comfortably fit content, capped to 85% of the screen."""
        self._tabs.adjustSize()
        hint = self._tabs.sizeHint()

        chrome_w = 8 * 2 + 2
        chrome_h = 8 * 2 + 2
        ideal_w = hint.width() + chrome_w + 24
        ideal_h = hint.height() + chrome_h + 24

        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            max_w = int(avail.width() * 0.85)
            max_h = int(avail.height() * 0.85)
            ideal_w = min(ideal_w, max_w)
            ideal_h = min(ideal_h, max_h)

        ideal_w = max(ideal_w, 300)
        ideal_h = max(ideal_h, 200)

        self.resize(ideal_w, ideal_h)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self._user_resized = True

    def rebuild(self) -> None:
        while self._tabs.count():
            self._tabs.removeTab(0)
        self._build_tabs()
        self._user_resized = False
