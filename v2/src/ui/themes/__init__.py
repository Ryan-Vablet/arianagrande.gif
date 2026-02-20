from __future__ import annotations

THEME = {
    "bg_window": "#2a2a3a",
    "bg_panel": "#252535",
    "bg_panel_header": "#1e1e2e",
    "bg_section": "#252535",
    "bg_subsection": "#1e1e2e",
    "bg_input": "#1a1a2a",
    "bg_button": "#333345",
    "bg_toolbar": "#1e1e2e",
    "bg_statusbar": "#1e1e2e",
    "border_panel": "#3a3a4a",
    "border_section": "#3a3a4a",
    "border_input": "#555",
    "text_primary": "#e0e0e0",
    "text_secondary": "#ccc",
    "text_label": "#999",
    "text_title": "#7a7a8e",
    "text_accent": "#66eeff",
}


def build_stylesheet() -> str:
    t = THEME
    return f"""
/* ===== Base ===== */
QMainWindow, QDialog {{
    background: {t["bg_window"]};
    color: {t["text_primary"]};
}}

QWidget {{
    color: {t["text_primary"]};
    font-size: 12px;
}}

/* ===== Labels ===== */
QLabel {{
    color: {t["text_primary"]};
    background: transparent;
    border: none;
}}

/* ===== Buttons ===== */
QPushButton {{
    background: {t["bg_button"]};
    border: 1px solid {t["border_input"]};
    color: {t["text_secondary"]};
    padding: 6px 14px;
    border-radius: 3px;
    font-size: 12px;
    min-height: 22px;
}}
QPushButton:hover {{
    background: #3d3d50;
    border-color: #666;
}}
QPushButton:pressed {{
    background: #2a2a3e;
    border-color: #777;
}}
QPushButton:disabled {{
    background: #2a2a38;
    color: #555;
    border-color: #444;
}}

/* ===== Line Edit ===== */
QLineEdit {{
    background: {t["bg_input"]};
    border: 1px solid {t["border_input"]};
    border-radius: 3px;
    padding: 5px 8px;
    color: {t["text_primary"]};
    selection-background-color: #445566;
}}
QLineEdit:focus {{
    border-color: {t["text_accent"]};
}}

/* ===== Spin Box ===== */
QSpinBox, QDoubleSpinBox {{
    background: {t["bg_input"]};
    border: 1px solid {t["border_input"]};
    border-radius: 3px;
    padding: 4px 8px;
    color: {t["text_primary"]};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: {t["bg_button"]};
    border: none;
    width: 16px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: #3d3d50;
}}

/* ===== Combo Box ===== */
QComboBox {{
    background: {t["bg_input"]};
    border: 1px solid {t["border_input"]};
    border-radius: 3px;
    padding: 5px 8px;
    color: {t["text_primary"]};
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: #666;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {t["bg_subsection"]};
    border: 1px solid {t["border_panel"]};
    color: {t["text_primary"]};
    selection-background-color: #3a3a5a;
    outline: none;
}}

/* ===== Check Box ===== */
QCheckBox {{
    spacing: 6px;
    color: {t["text_primary"]};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {t["border_input"]};
    border-radius: 3px;
    background: {t["bg_input"]};
}}
QCheckBox::indicator:checked {{
    background: #2d5a2d;
    border-color: #3a7a3a;
}}

/* ===== Slider ===== */
QSlider::groove:horizontal {{
    height: 4px;
    background: #333345;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #556;
    border: 1px solid #777;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: #667;
}}

/* ===== Tab Widget ===== */
QTabWidget::pane {{
    border: 1px solid {t["border_panel"]};
    border-top: none;
    background: {t["bg_window"]};
}}
QTabBar::tab {{
    background: {t["bg_subsection"]};
    border: 1px solid {t["border_panel"]};
    border-bottom: none;
    padding: 7px 18px;
    margin-right: 2px;
    color: {t["text_label"]};
    font-size: 11px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {t["bg_window"]};
    color: {t["text_primary"]};
    border-bottom: 1px solid {t["bg_window"]};
}}
QTabBar::tab:hover:!selected {{
    background: #2a2a42;
    color: {t["text_secondary"]};
}}

/* ===== Scroll Area ===== */
QScrollArea {{
    border: none;
    background: transparent;
}}

/* ===== Scroll Bar ===== */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #444;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #555;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #444;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #555;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ===== Splitter ===== */
QSplitter::handle {{
    background: {t["border_panel"]};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}

/* ===== Menu ===== */
QMenu {{
    background: {t["bg_subsection"]};
    border: 1px solid {t["border_panel"]};
    color: {t["text_primary"]};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 24px;
}}
QMenu::item:selected {{
    background: #3a3a5a;
}}
QMenu::separator {{
    height: 1px;
    background: {t["border_panel"]};
    margin: 4px 8px;
}}

/* ===== Toolbar ===== */
QToolBar {{
    background: {t["bg_toolbar"]};
    border-bottom: 1px solid {t["border_panel"]};
    padding: 4px 8px;
    spacing: 6px;
}}
QToolBar QPushButton {{
    padding: 5px 12px;
    font-size: 11px;
    min-height: 20px;
}}

/* ===== Status Bar ===== */
QStatusBar {{
    background: {t["bg_statusbar"]};
    border-top: 1px solid #333;
    padding: 4px 12px;
    font-size: 10px;
    font-family: monospace;
    color: #555;
}}

/* ===== Frame ===== */
QFrame#sectionFrame {{
    background: {t["bg_section"]};
    border: 1px solid {t["border_section"]};
    border-radius: 4px;
}}
QFrame#subsectionFrame {{
    background: {t["bg_subsection"]};
    border: 1px solid {t["border_section"]};
    border-radius: 4px;
}}

/* ===== Section Titles ===== */
QLabel#sectionTitle {{
    font-family: monospace;
    font-size: 10px;
    color: {t["text_title"]};
    font-weight: bold;
    letter-spacing: 1.5px;
    background: transparent;
}}
"""
