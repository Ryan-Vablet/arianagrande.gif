from __future__ import annotations

import sys
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from src.core.config_manager import ConfigManager
from src.core.core import Core
from src.core.module_manager import ModuleManager
from src.ui.main_window import MainWindow
from src.ui.settings_dialog import SettingsDialog
from src.ui.themes import build_stylesheet

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "default_config.json"
MODULES_DIR = PROJECT_ROOT / "modules"


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    config = ConfigManager(CONFIG_PATH)
    config.load()

    core = Core(config)

    module_manager = ModuleManager(core)
    module_manager.discover(MODULES_DIR)

    enabled = config.get("app").get("modules_enabled") or None
    module_manager.load(enabled)

    window = MainWindow(core)
    settings_dialog = SettingsDialog(core, parent=window)
    window.settings_requested.connect(settings_dialog.show_or_raise)

    core.windows.show_defaults()

    window.show()
    exit_code = app.exec()

    core.windows.teardown()
    module_manager.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
