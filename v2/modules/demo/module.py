from __future__ import annotations

from src.core.base_module import BaseModule


class DemoModule(BaseModule):
    name = "Demo"
    key = "demo"
    version = "1.0.0"
    description = "Test module — registers panels, settings, and a window"

    def setup(self, core) -> None:
        super().setup(core)

        core.panels.register(
            id=f"{self.key}/main_panel",
            area="primary",
            factory=self._build_main_panel,
            title="Demo Panel",
            owner=self.key,
            order=10,
        )

        core.panels.register(
            id=f"{self.key}/sidebar_panel",
            area="sidebar",
            factory=self._build_sidebar_panel,
            title="Demo Sidebar",
            owner=self.key,
            order=10,
        )

        core.settings.register(
            path=self.key,
            factory=self._build_settings,
            title="Demo",
            owner=self.key,
        )

        core.settings.register(
            path="detection/demo_detector",
            factory=self._build_detection_settings,
            title="Demo Detector",
            owner=self.key,
            order=99,
        )

        core.windows.register(
            id=f"{self.key}/popup",
            factory=self._build_popup,
            title="Demo Popup",
            window_type="panel",
            owner=self.key,
            default_visible=False,
            show_in_menu=True,
        )

    def _build_main_panel(self):
        from PyQt6.QtWidgets import QLabel
        label = QLabel(
            "This is the demo module's primary panel.\n\n"
            "It was registered during setup() and injected into the main window."
        )
        label.setWordWrap(True)
        label.setStyleSheet("padding: 12px; color: #ccc;")
        return label

    def _build_sidebar_panel(self):
        from PyQt6.QtWidgets import QLabel
        label = QLabel("Sidebar panel\nfrom demo module.")
        label.setWordWrap(True)
        label.setStyleSheet("padding: 12px; color: #999;")
        return label

    def _build_settings(self):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Demo module settings"))

        msg_input = QLineEdit()
        msg_input.setPlaceholderText("Enter a message...")
        cfg = self.core.get_config(self.key)
        msg_input.setText(cfg.get("message", ""))
        msg_input.textChanged.connect(
            lambda text: self.core.update_config(self.key, {"message": text})
        )
        layout.addWidget(msg_input)

        show_popup_btn = QPushButton("Show Demo Popup")
        show_popup_btn.clicked.connect(
            lambda: self.core.windows.show(f"{self.key}/popup")
        )
        layout.addWidget(show_popup_btn)

        layout.addStretch()
        return w

    def _build_detection_settings(self):
        from PyQt6.QtWidgets import QLabel
        label = QLabel(
            "This section was injected into the 'Detection' tab by the Demo module.\n"
            "It demonstrates cross-module settings injection."
        )
        label.setWordWrap(True)
        label.setStyleSheet("padding: 8px; color: #999; font-style: italic;")
        return label

    def _build_popup(self):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
        w = QWidget()
        w.setMinimumSize(300, 200)
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "This is a managed popup window.\n\n"
            "Its position will be saved and restored across sessions."
        ))
        return w
