# arianagrande.gif — Phase 2: Capture, Preview, Overlay + Tests

## Prerequisites

Phase 1 is complete. The shell works: modules register panels, settings, and windows. The demo module proves all three registration paths.

## Goal

Build the **core capture module** — the foundation every detection module will sit on top of. When this phase is done:

- The app captures a screen region at a configurable FPS
- Frames are distributed to all loaded modules via `on_frame()`
- A live preview panel shows what's being captured
- A transparent overlay shows the capture region on screen
- Settings let the user pick monitor, set capture region, configure slot layout
- Start/Stop capture is controlled from the main window toolbar
- All Phase 1 managers have unit tests
- All Phase 2 code has tests

---

## v1 Reference

These v1 files contain working implementations to reference:

- `/v1/src/capture/screen_capture.py` — ScreenCapture using `mss`. 79 lines. Works well, copy and adapt.
- `/v1/src/overlay/calibration_overlay.py` — Transparent overlay. 341 lines. Has a lot of glow/buff/cast-bar specific rendering — **only bring over the basic bounding box + slot outline rendering for now**. Detection-specific overlay features belong in later phases when those modules exist.
- `/v1/src/models/slot.py` — Contains `BoundingBox` dataclass with `as_mss_region()` and `to_dict()`. Copy this model.

---

## New Files

```
/v2/
  src/
    core/
      ... (Phase 1, unchanged)
    capture/
      __init__.py
      screen_capture.py          # Copy from v1, adapt imports
    models/
      __init__.py
      geometry.py                # BoundingBox dataclass
    ui/
      ... (Phase 1, unchanged)
  modules/
    demo/                        # Phase 1, unchanged
    core_capture/
      __init__.py
      module.py                  # Core capture module
      preview_widget.py          # Live preview panel widget
      settings_widget.py         # Monitor, region, slot layout, overlay settings
      overlay.py                 # Simplified calibration overlay
      capture_worker.py          # QThread that grabs frames and distributes them
  tests/
    __init__.py
    # Phase 1 retroactive tests
    test_config_manager.py
    test_panel_manager.py
    test_settings_manager.py
    test_window_manager.py
    test_module_manager.py
    # Phase 2 tests
    test_bounding_box.py
    test_capture_worker.py
    test_core_capture_module.py
```

---

## 1. BoundingBox Model (`src/models/geometry.py`)

Copy from v1's `BoundingBox` in `/v1/src/models/slot.py`. It's a simple dataclass:

```python
from dataclasses import dataclass

@dataclass
class BoundingBox:
    """Screen-relative bounding box for a capture region."""
    top: int = 900
    left: int = 500
    width: int = 400
    height: int = 50
    
    def as_mss_region(self, monitor_offset_x: int = 0, monitor_offset_y: int = 0) -> dict:
        """Convert to mss-compatible region dict."""
        return {
            "top": self.top + monitor_offset_y,
            "left": self.left + monitor_offset_x,
            "width": self.width,
            "height": self.height,
        }
    
    def to_dict(self) -> dict:
        return {"top": self.top, "left": self.left, "width": self.width, "height": self.height}
    
    @classmethod
    def from_dict(cls, d: dict) -> "BoundingBox":
        return cls(
            top=int(d.get("top", 900)),
            left=int(d.get("left", 500)),
            width=int(d.get("width", 400)),
            height=int(d.get("height", 50)),
        )
```

`src/models/__init__.py`:
```python
from .geometry import BoundingBox
```

---

## 2. ScreenCapture (`src/capture/screen_capture.py`)

Copy from `/v1/src/capture/screen_capture.py`. Update the import to use `src.models.geometry.BoundingBox` instead of `src.models.BoundingBox`. Keep the same interface:

- `__init__(monitor_index=1)`
- `start()` / `stop()`
- `monitor_info` property
- `grab_region(bbox) -> np.ndarray` (BGR)
- `list_monitors() -> list[dict]`

No changes to the logic. It works.

---

## 3. BaseModule Update (`src/core/base_module.py`)

Add `on_frame()` to BaseModule:

```python
def on_frame(self, frame: "np.ndarray") -> None:
    """Called each capture cycle with the raw frame (BGR numpy array).
    
    Only implement if the module needs per-frame processing.
    Frame is the full captured region — modules crop what they need.
    
    IMPORTANT: This is called from the capture worker thread, NOT the GUI thread.
    Do not update Qt widgets directly. Use signals with Qt.QueuedConnection
    to marshal updates to the GUI thread.
    """
    pass
```

Also add to ModuleManager:

```python
def process_frame(self, frame: "np.ndarray") -> None:
    """Call on_frame() on each enabled module in load order."""
    for key in self._load_order:
        mod = self.modules.get(key)
        if mod is not None and mod.enabled:
            try:
                mod.on_frame(frame)
            except Exception as e:
                logger.exception("Module %s on_frame failed: %s", key, e)
```

---

## 4. CaptureWorker (`modules/core_capture/capture_worker.py`)

A QThread that grabs frames and distributes them.

```python
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage
import numpy as np

class CaptureWorker(QThread):
    """Capture loop: grab frame, emit preview, distribute to modules."""
    
    frame_captured = pyqtSignal(QImage)  # For preview (QImage is thread-safe for QueuedConnection)
    
    def __init__(self, core, module_manager):
        super().__init__()
        self._core = core
        self._module_manager = module_manager
        self._running = False
        self._capture = None
    
    def run(self):
        """
        Main capture loop:
        1. Read monitor_index from core config, create ScreenCapture
        2. Read bounding_box from core config, compute capture region
        3. Loop at configured FPS:
           a. Check if monitor changed, restart capture if so
           b. Grab frame from capture region
           c. Convert to QImage, emit frame_captured for preview
           d. Call module_manager.process_frame(frame) to distribute to all modules
        4. On stop, clean up capture
        """
        from src.capture.screen_capture import ScreenCapture
        from src.models import BoundingBox
        
        self._running = True
        cfg = self._core.get_config("core_capture")
        monitor_index = int(cfg.get("monitor_index", 1))
        
        self._capture = ScreenCapture(monitor_index=monitor_index)
        self._capture.start()
        
        fps = max(1, min(120, int(cfg.get("polling_fps", 20))))
        interval_ms = int(1000 / fps)
        
        try:
            while self._running:
                try:
                    # Check for monitor change
                    new_cfg = self._core.get_config("core_capture")
                    new_monitor = int(new_cfg.get("monitor_index", 1))
                    if new_monitor != monitor_index:
                        monitor_index = new_monitor
                        self._capture.stop()
                        self._capture = ScreenCapture(monitor_index=monitor_index)
                        self._capture.start()
                    
                    # Grab frame
                    bb_dict = new_cfg.get("bounding_box", {})
                    bbox = BoundingBox.from_dict(bb_dict)
                    frame = self._capture.grab_region(bbox)
                    
                    # Emit QImage for preview (BGR -> RGB -> QImage)
                    h, w, ch = frame.shape
                    rgb = frame[:, :, ::-1].copy()
                    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                    self.frame_captured.emit(qimg)
                    
                    # Distribute to modules
                    self._module_manager.process_frame(frame)
                    
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error("Capture error: %s", e, exc_info=True)
                
                self.msleep(interval_ms)
        finally:
            if self._capture:
                self._capture.stop()
    
    def stop(self):
        self._running = False
        self.wait()
```

**Key design decisions:**
- Frame is the raw BGR numpy array from `grab_region`
- QImage is emitted for preview only (thread-safe copy)
- `process_frame` runs in the worker thread — modules must use signals for GUI updates
- FPS is read once at start. A future enhancement could re-read periodically.

---

## 5. Core Capture Module (`modules/core_capture/module.py`)

This is the first "real" module. It owns the capture system, preview, overlay, and capture-region settings.

```python
from src.core.base_module import BaseModule

class CoreCaptureModule(BaseModule):
    name = "Core Capture"
    key = "core_capture"
    version = "1.0.0"
    description = "Screen capture, live preview, calibration overlay"
    requires = []
    optional = []
    provides_services = ["monitor_info", "capture_running", "bounding_box"]
    hooks = ["capture_started", "capture_stopped"]
    
    def setup(self, core):
        super().setup(core)
        self._worker = None
        self._is_running = False
        
        # Ensure config defaults exist
        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())
        
        # Register panels
        core.panels.register(
            id=f"{self.key}/preview",
            area="primary",
            factory=self._build_preview_widget,
            title="Live Preview",
            owner=self.key,
            order=0,  # Preview should be first
        )
        
        core.panels.register(
            id=f"{self.key}/controls",
            area="primary",
            factory=self._build_controls_widget,
            title="Capture Controls",
            owner=self.key,
            order=1,
        )
        
        # Register settings tab
        core.settings.register(
            path="general",
            factory=self._build_settings,
            title="General",
            owner=self.key,
            order=0,  # General should be first tab
        )
        
        # Register overlay as managed window
        core.windows.register(
            id=f"{self.key}/overlay",
            factory=self._build_overlay,
            title="Capture Overlay",
            window_type="overlay",
            owner=self.key,
            default_visible=False,
            show_in_menu=True,
            remember_geometry=False,  # Overlay position is driven by monitor selection, not user drag
        )
    
    def _default_config(self) -> dict:
        return {
            "monitor_index": 1,
            "polling_fps": 20,
            "bounding_box": {"top": 900, "left": 500, "width": 400, "height": 50},
            "slots": {"count": 10, "gap": 2, "padding": 3},
            "overlay": {"enabled": False, "show_active_screen_outline": False},
            "display": {"always_on_top": False},
        }
    
    def get_service(self, name):
        if name == "capture_running":
            return self._is_running
        if name == "bounding_box":
            cfg = self.core.get_config(self.key)
            return cfg.get("bounding_box", {})
        if name == "monitor_info":
            # Return monitor list if capture worker has it
            return None  # Enhanced in later phases
        return None
    
    def start_capture(self):
        """Start the capture worker thread."""
        if self._is_running:
            return
        from modules.core_capture.capture_worker import CaptureWorker
        from src.core.module_manager import ModuleManager
        
        # Get module_manager from core — it's set as an attribute by main.py
        module_manager = getattr(self.core, '_module_manager', None)
        if module_manager is None:
            return
        
        self._worker = CaptureWorker(self.core, module_manager)
        
        # Connect preview signal
        preview = self._preview_widget
        if preview is not None:
            from PyQt6.QtCore import Qt
            self._worker.frame_captured.connect(
                preview.update_preview, Qt.ConnectionType.QueuedConnection
            )
        
        self._worker.start()
        self._is_running = True
        self.core.emit(f"{self.key}.capture_started")
        
        # Show overlay if configured
        cfg = self.core.get_config(self.key)
        if cfg.get("overlay", {}).get("enabled", False):
            self.core.windows.show(f"{self.key}/overlay")
    
    def stop_capture(self):
        """Stop the capture worker thread."""
        if not self._is_running:
            return
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._is_running = False
        self.core.emit(f"{self.key}.capture_stopped")
    
    def toggle_capture(self):
        if self._is_running:
            self.stop_capture()
        else:
            self.start_capture()
    
    def teardown(self):
        self.stop_capture()
    
    # --- Widget builders (details in separate files) ---
    
    def _build_preview_widget(self):
        from modules.core_capture.preview_widget import PreviewWidget
        self._preview_widget = PreviewWidget()
        return self._preview_widget
    
    def _build_controls_widget(self):
        """Start/Stop button + status. Simple widget, can be inline."""
        from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._btn_capture = QPushButton("▶ Start Capture")
        self._btn_capture.clicked.connect(self._on_capture_toggle)
        layout.addWidget(self._btn_capture)
        
        self._capture_status = QLabel("Stopped")
        self._capture_status.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self._capture_status)
        layout.addStretch()
        return w
    
    def _on_capture_toggle(self):
        self.toggle_capture()
        if self._is_running:
            self._btn_capture.setText("⏹ Stop Capture")
            self._capture_status.setText("Running")
            self._capture_status.setStyleSheet("color: #88ff88; font-size: 11px;")
        else:
            self._btn_capture.setText("▶ Start Capture")
            self._capture_status.setText("Stopped")
            self._capture_status.setStyleSheet("color: #999; font-size: 11px;")
    
    def _build_settings(self):
        from modules.core_capture.settings_widget import CoreCaptureSettings
        return CoreCaptureSettings(self.core, self.key)
    
    def _build_overlay(self):
        from modules.core_capture.overlay import CaptureOverlay
        cfg = self.core.get_config(self.key)
        return CaptureOverlay(self.core, self.key)
```

**Note on module_manager access:** The module needs to pass module_manager to CaptureWorker for `process_frame()`. Main.py should set `core._module_manager = module_manager` after creating both. This is a pragmatic bridge — a cleaner approach (like a frame distribution hook) can replace it later. Add this line to `main.py` after `module_manager = ModuleManager(core)`:

```python
core._module_manager = module_manager  # Bridge for capture worker frame distribution
```

---

## 6. Preview Widget (`modules/core_capture/preview_widget.py`)

Shows the latest captured frame, scaled to fit.

```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy

PREVIEW_PADDING = 12

class PreviewWidget(QLabel):
    """Displays the latest captured frame. Updated via QueuedConnection from capture thread."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("No capture running")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(300, 42)
        self.setStyleSheet(
            "background: #111; border-radius: 3px; color: #666; font-size: 11px;"
        )
        self.setScaledContents(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    
    def update_preview(self, qimg: QImage) -> None:
        """Slot: receives QImage from capture worker (QueuedConnection)."""
        if qimg.isNull():
            return
        pixmap = QPixmap.fromImage(qimg)
        max_w = max(50, self.width() - 2 * PREVIEW_PADDING)
        max_h = max(20, self.height() - 2 * PREVIEW_PADDING)
        scaled = pixmap.scaled(
            max_w, max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setText("")
        self.setPixmap(scaled)
```

---

## 7. Settings Widget (`modules/core_capture/settings_widget.py`)

Settings for: monitor selection, capture region (top/left/width/height), slot layout (count/gap/padding), overlay toggle, polling FPS, always-on-top toggle.

```python
class CoreCaptureSettings(QWidget):
    """General settings: monitor, capture region, slots, overlay, display."""
    
    def __init__(self, core, module_key, parent=None):
        super().__init__(parent)
        self._core = core
        self._key = module_key
        self._build_ui()
        self._populate()
        self._connect_signals()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # --- Monitor section ---
        # QComboBox for monitor selection
        # Populate with available monitors (index, resolution)
        # To get monitors: create a temporary ScreenCapture, start, list_monitors, stop
        
        # --- Capture Region section ---
        # QSpinBox for top, left, width, height
        # All in a 2x2 grid or form layout
        
        # --- Slot Layout section ---
        # QSpinBox for count, gap, padding
        
        # --- Capture section ---
        # QSpinBox for polling FPS (range 5-120)
        
        # --- Overlay section ---
        # QCheckBox "Show capture overlay"
        # QCheckBox "Show active screen outline"
        
        # --- Display section ---
        # QCheckBox "Always on top"
    
    def _populate(self):
        """Read from core config and set widget values."""
        cfg = self._core.get_config(self._key)
        # Set all widget values from cfg
    
    def _connect_signals(self):
        """Connect all widgets to _save()."""
        # Every spinbox.valueChanged, checkbox.toggled, combo.currentIndexChanged -> _save
    
    def _save(self):
        """Read all widgets, build config dict, save via core."""
        cfg = self._core.get_config(self._key)
        cfg["monitor_index"] = self._combo_monitor.currentData() or 1
        cfg["polling_fps"] = self._spin_fps.value()
        cfg["bounding_box"] = {
            "top": self._spin_top.value(),
            "left": self._spin_left.value(),
            "width": self._spin_width.value(),
            "height": self._spin_height.value(),
        }
        cfg["slots"] = {
            "count": self._spin_slot_count.value(),
            "gap": self._spin_slot_gap.value(),
            "padding": self._spin_slot_padding.value(),
        }
        cfg["overlay"] = {
            "enabled": self._check_overlay.isChecked(),
            "show_active_screen_outline": self._check_outline.isChecked(),
        }
        cfg["display"] = {
            "always_on_top": self._check_aot.isChecked(),
        }
        self._core.save_config(self._key, cfg)
```

Style all widgets to match the theme. Use `_section_frame` from the settings_dialog helpers if you want visual grouping, or use simple QFormLayouts with labels.

---

## 8. Overlay (`modules/core_capture/overlay.py`)

Simplified version of v1's `CalibrationOverlay`. **Only include:**
- Transparent, frameless, always-on-top, click-through
- Green bounding box outline
- Magenta slot outlines (using slot count/gap/padding math)
- Active screen outline (subtle green border when capture is running)

**Do NOT include** glow detection, buff ROI, cast bar rendering — those belong to future detection modules that will draw their own overlay elements (or extend this one via hooks).

```python
class CaptureOverlay(QWidget):
    """Transparent overlay showing capture region and slot layout."""
    
    def __init__(self, core, module_key, parent=None):
        super().__init__(parent)
        self._core = core
        self._key = module_key
        self._capture_active = False
        self._setup_window()
        self._refresh_from_config()
    
    def _setup_window(self):
        """Frameless, transparent, always-on-top, click-through. Covers selected monitor."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    
    def _refresh_from_config(self):
        """Read bounding_box, slots, monitor from config and reposition/repaint."""
        cfg = self._core.get_config(self._key)
        bb = cfg.get("bounding_box", {})
        self._bbox = BoundingBox.from_dict(bb)
        slots = cfg.get("slots", {})
        self._slot_count = int(slots.get("count", 10))
        self._slot_gap = int(slots.get("gap", 2))
        self._slot_padding = int(slots.get("padding", 3))
        self._show_outline = cfg.get("overlay", {}).get("show_active_screen_outline", False)
        # Reposition to cover selected monitor
        # (needs monitor geometry — get from ScreenCapture or stored in config)
        self.update()
    
    def set_capture_active(self, active: bool):
        self._capture_active = active
        self.update()
    
    def paintEvent(self, event):
        """Draw bounding box and slot outlines."""
        # Reference /v1/src/overlay/calibration_overlay.py paintEvent
        # but ONLY the bounding box rect (green) and slot rects (magenta).
        # Skip all glow/buff/cast-bar rendering.
```

The overlay subscribes to the `core_capture.capture_started` and `core_capture.capture_stopped` hooks to toggle the active screen outline.

---

## 9. Update main.py

Add the module_manager bridge and update the startup sequence:

```python
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
    
    config = ConfigManager(CONFIG_PATH)
    config.load()
    
    core = Core(config)
    
    module_manager = ModuleManager(core)
    core._module_manager = module_manager  # Bridge for capture worker frame distribution
    
    module_manager.discover(MODULES_DIR)
    enabled = config.get("app").get("modules_enabled") or None
    module_manager.load(enabled)
    
    window = MainWindow(core)
    settings_dialog = SettingsDialog(core, parent=window)
    window.settings_requested.connect(settings_dialog.show_or_raise)
    
    core.windows.show_defaults()
    
    window.show()
    exit_code = app.exec()
    
    # Shutdown — stop capture before closing windows
    capture_mod = module_manager.get("core_capture")
    if capture_mod and hasattr(capture_mod, "stop_capture"):
        capture_mod.stop_capture()
    
    core.windows.teardown()
    module_manager.shutdown()
    sys.exit(exit_code)
```

Update default config to include core_capture:

```json
{
  "app": {
    "modules_enabled": ["core_capture", "demo"],
    "window_geometry": {}
  },
  "core_capture": {
    "monitor_index": 1,
    "polling_fps": 20,
    "bounding_box": {"top": 900, "left": 500, "width": 400, "height": 50},
    "slots": {"count": 10, "gap": 2, "padding": 3},
    "overlay": {"enabled": false, "show_active_screen_outline": false},
    "display": {"always_on_top": false}
  },
  "demo": {
    "message": "Hello from demo module"
  }
}
```

---

## 10. Tests

Use `pytest`. All tests go in `/v2/tests/`. No Qt app fixture needed for manager tests — they're pure Python. Use mocking where needed for Qt-dependent tests.

### Phase 1 Retroactive Tests

**`tests/test_config_manager.py`:**
```python
# Test: load from nonexistent file → empty root
# Test: set namespace, get returns the data
# Test: get returns a COPY (mutating returned dict doesn't affect stored data)
# Test: update merges into existing namespace
# Test: save writes to disk, load reads it back
# Test: get unknown namespace returns empty dict
```

**`tests/test_panel_manager.py`:**
```python
# Test: register panel, get_panels returns it
# Test: panels sorted by order
# Test: get_panels filters by area ("primary" vs "sidebar")
# Test: hidden panels (visible=False) not returned
# Test: teardown_module removes only that module's panels
# Test: registering same id overwrites previous
```

**`tests/test_settings_manager.py`:**
```python
# Test: register "foo" → get_tabs returns one tab with path "foo"
# Test: register "foo/bar" → get_tabs returns tab "foo" with child "bar"
# Test: tab title inferred from path when not provided
# Test: auto-created container tab when only children registered (no parent)
# Test: register both "detection" and "detection/brightness" → tab has own widget + child
# Test: children sorted by order within tab
# Test: tabs sorted by order
# Test: teardown_module removes only that module's registrations
```

**`tests/test_window_manager.py`:**
```python
# NOTE: WindowManager uses ConfigManager for geometry persistence.
#       Mock ConfigManager or use a real one with a temp file.
# Test: register window, list_menu_entries returns it
# Test: show_in_menu=False excluded from list
# Test: show creates instance lazily (factory called on first show)
# Test: show called twice doesn't create second instance (singleton)
# Test: hide hides the window
# Test: toggle flips visibility
# Test: is_visible returns correct state
# Test: save_all_geometry writes to config
# Test: teardown_module closes and removes module's windows
# Test: teardown saves geometry and closes all
```

**`tests/test_module_manager.py`:**
```python
# NOTE: Needs a real or mocked Core and test module classes.
# Create simple test module classes inline:
#   class ModA(BaseModule): key = "a"; requires = []
#   class ModB(BaseModule): key = "b"; requires = ["a"]
#   class ModC(BaseModule): key = "c"; requires = ["nonexistent"]
#
# Test: discover finds modules in a temp directory
# Test: load calls setup() then ready() in order
# Test: dependency order: B depends on A → A loaded before B
# Test: missing required dependency: C skipped with warning
# Test: optional dependency: present → sorted after it; absent → still loads
# Test: cycle detection: A requires B, B requires A → both skipped
# Test: modules registered with core (core.get_module works after load)
# Test: shutdown calls teardown in reverse order
# Test: process_frame calls on_frame on enabled modules only
# Test: disabled module skipped in process_frame
```

### Phase 2 Tests

**`tests/test_bounding_box.py`:**
```python
# Test: default values
# Test: from_dict with all fields
# Test: from_dict with missing fields uses defaults
# Test: to_dict roundtrip
# Test: as_mss_region applies monitor offset
```

**`tests/test_capture_worker.py`:**
```python
# NOTE: CaptureWorker uses ScreenCapture which requires a display.
#       Mock ScreenCapture for unit tests.
# Test: worker starts and stops cleanly
# Test: worker emits frame_captured signal (mock ScreenCapture.grab_region)
# Test: worker calls module_manager.process_frame with the frame
# Test: worker reads config for FPS and monitor_index
```

**`tests/test_core_capture_module.py`:**
```python
# Test: setup registers panels, settings, and overlay window
# Test: default config created if none exists
# Test: start_capture / stop_capture toggle is_running service
# Test: get_service returns correct values
# Test: teardown stops capture
```

### Test Configuration

Add `/v2/pytest.ini` or `/v2/pyproject.toml` section:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

So tests can be run with:
```bash
cd v2
pytest
```

---

## Verification

When the app starts with both core_capture and demo modules:

1. Main window shows "LIVE PREVIEW" panel at top (blank, says "No capture running")
2. Below it: "CAPTURE CONTROLS" panel with a "▶ Start Capture" button
3. Below that: demo panels from Phase 1
4. Settings dialog has "General" tab (from core_capture) with monitor dropdown, region spinboxes, slot layout, FPS, overlay toggle, always-on-top
5. Clicking "▶ Start Capture" starts capture:
   - Preview shows live screen grab of the configured region
   - Button text changes to "⏹ Stop Capture"
   - Status shows "Running" in green
6. If overlay is enabled in settings, the transparent green rectangle appears on screen showing the capture region with magenta slot outlines
7. Changing bounding box values in settings updates what's captured (visible in preview)
8. Stopping capture clears the preview
9. "Windows" menu shows "Capture Overlay" with toggle
10. All tests pass: `cd v2 && pytest` — green across the board

---

## What This Phase Does NOT Include

- No frame analysis / slot detection (Phase 3: brightness detection module)
- No glow/buff/cast-bar overlay rendering (belongs to their respective detection modules)
- No key sending / automation (Phase 4+)
- No hotkey system (Phase 4+)
- No capture subscriptions / multi-region (future: health module)
- No drag-to-reorder panels

The capture system is the nervous system. Detection modules are the eyes. This phase builds the nervous system.
