# arianagrande.gif — Phase 1: The Shell

## Project Layout

```
/v1/    ← Previous version. READ-ONLY reference. Do NOT modify.
/v2/    ← New modular version. All work goes here.
```

### v1 Reference Guide

The v1 codebase at `/v1/` is a working app. Use it as a style and behavior reference, but do not copy code wholesale — the architecture is different. Specifically:

**Look at for style/theme reference:**
- `/v1/src/ui/themes/__init__.py` — QSS dark theme, color palette, widget styling
- `/v1/src/ui/main_window.py` — overall window structure, section frame styling, collapsible panel feel
- `/v1/src/ui/settings_dialog.py` — `_section_frame()`, `_subsection_frame()`, `_row_label()` helpers, tab layout, form styling
- `/v1/modules/cooldown_rotation/status_widget.py` — panel styling constants (SECTION_BG, SECTION_BORDER, etc.)

**Ignore (architecture is being replaced):**
- `/v1/src/main.py` — tangled wiring, dead code, don't reference
- `/v1/src/core/` — being rewritten with new manager pattern
- `/v1/src/core/config_migration.py` — v1-specific migration, not needed
- Any `debug-6d0385` / `#region agent log` blocks — leftover debugging, ignore entirely

### Running the App

Run from the v2 directory:

```bash
cd v2
PYTHONPATH=. python src/main.py
# or
python -m src.main
```

Both `src` and `modules` must be importable from the v2 root. The ModuleManager adds the modules directory to `sys.path` during discovery, but `src` must be resolvable from the working directory.

---

## Goal

Build the bare minimum application shell that modules plug into. When this phase is done, the app starts, loads modules from a directory, and modules can register panels in the main window, tabs/sections in settings, and managed windows. Nothing else — no detection, no automation, no capture. Just the skeleton.

We verify it works with a demo module (`/v2/modules/demo/`) that registers a panel, a settings section, and a window. If the demo module shows up in the UI, the shell works.

---

## Project Structure

```
/v2/
  src/
    __init__.py
    main.py                      # Entry point: create app, load modules, show window
    core/
      __init__.py
      core.py                    # Core service provider — facade for all managers
      module_manager.py          # Discovery, dependency sort, lifecycle
      base_module.py             # Abstract base class for modules
      config_manager.py          # Load/save namespaced JSON config
      panel_manager.py           # Tracks panel registrations for main window
      settings_manager.py        # Tracks settings registrations (path-based tree)
      window_manager.py          # Tracks module windows, lazy creation, geometry persistence
    ui/
      __init__.py
      main_window.py             # Shell: toolbar + primary area + sidebar
      settings_dialog.py         # Shell: tab container built from settings tree
      themes/
        __init__.py              # QSS theme (reference /v1/src/ui/themes/ for palette)
  modules/
    demo/
      __init__.py                # Exports DemoModule
      module.py                  # Test module that registers everything
  config/
    default_config.json          # Minimal starting config
```

---

## 1. ConfigManager (`src/core/config_manager.py`)

Manages a single JSON file with namespaced sections.

```python
class ConfigManager:
    def __init__(self, path: Path):
        self._path = path
        self._root: dict = {}
    
    def load(self) -> None:
        """Load from disk. If file missing or invalid, start with empty dict."""
    
    def save(self) -> None:
        """Write current root to disk. Pretty-printed JSON, 2-space indent."""
    
    def get_root(self) -> dict:
        """Return full config dict. Do not mutate directly."""
        return self._root
    
    def get(self, namespace: str) -> dict:
        """Get a COPY of a namespace's config section. Returns empty dict if missing."""
        return dict(self._root.get(namespace, {}))
    
    def set(self, namespace: str, data: dict) -> None:
        """Replace a namespace's section and save to disk."""
        self._root[namespace] = data
        self.save()
    
    def update(self, namespace: str, updates: dict) -> None:
        """Merge updates into a namespace's section and save."""
        section = self._root.setdefault(namespace, {})
        section.update(updates)
        self.save()
```

**Important:** `get()` returns a **copy** (via `dict(...)`). Any code that reads config, mutates it, and wants to persist must call `set()` or `update()` afterward. This is intentional — prevents accidental mutation of the live config.

Config shape:
```json
{
  "app": {
    "modules_enabled": ["demo"],
    "window_geometry": {}
  },
  "demo": {
    "message": "Hello from demo module"
  }
}
```

`"app"` is the reserved namespace for shell-level config (which modules are enabled, window positions, etc). Module namespaces match their `key`.

---

## 2. BaseModule (`src/core/base_module.py`)

```python
from abc import ABC
from typing import Any

class BaseModule(ABC):
    """Base class all modules inherit from."""
    
    # --- Identity (subclass MUST define) ---
    name: str = ""          # Human-readable: "Brightness Detection"
    key: str = ""           # Machine key: "brightness_detection"
    version: str = "1.0.0"
    description: str = ""
    
    # --- Dependencies ---
    requires: list[str] = []    # Module keys that MUST be loaded
    optional: list[str] = []    # Module keys used if available
    
    # --- Capabilities ---
    provides_services: list[str] = []   # Service names other modules can read
    hooks: list[str] = []               # Hook names this module emits
    
    def __init__(self):
        self.core = None        # Set by setup()
        self.enabled: bool = True
    
    def setup(self, core) -> None:
        """Called once after dependency check. Register panels, settings, windows, hooks here."""
        self.core = core
    
    def ready(self) -> None:
        """Called after ALL modules have completed setup(). Safe to read other modules' services."""
        pass
    
    def get_service(self, name: str) -> Any:
        """Return current value for a named service. Called by Core on behalf of other modules."""
        return None
    
    def on_config_changed(self, key: str, value: Any) -> None:
        """Called when this module's config section changes."""
        pass
    
    def on_enable(self) -> None:
        pass
    
    def on_disable(self) -> None:
        pass
    
    def teardown(self) -> None:
        """Cleanup. Called in reverse load order on app exit."""
        pass
```

Note: No `on_frame()` in the base. Frame processing will be added in Phase 2 when we build the capture system. For now modules are purely UI-registration.

---

## 3. ModuleManager (`src/core/module_manager.py`)

```python
class ModuleManager:
    def __init__(self, core):
        self.core = core
        self._discovered: dict[str, type[BaseModule]] = {}  # key -> class
        self.modules: dict[str, BaseModule] = {}             # key -> instance
        self._load_order: list[str] = []                     # topological order
    
    def discover(self, modules_dir: Path) -> list[str]:
        """
        Scan modules_dir for subdirectories with __init__.py.
        Import each, find the BaseModule subclass, store by key.
        Return list of discovered keys.
        
        If two packages declare the same key, log a warning and keep the first one found.
        """
    
    def load(self, enabled_keys: list[str] | None = None) -> None:
        """
        Load enabled modules (or all discovered if None).
        
        Steps:
        1. Validate requires — skip module if a required dependency is missing, log warning
        2. Topological sort by requires + optional (Kahn's algorithm)
        3. Detect cycles — log error, skip cycle participants
        4. Instantiate in order
        5. Register each with Core: core.register_module(key, instance)
        6. Call setup(core) on each in order
        7. Call ready() on each in order (after ALL setup() calls complete)
        
        Step 5 is critical — without it, core.get_module() and core.get_service()
        won't find any modules during setup() or ready().
        """
    
    def get(self, key: str) -> BaseModule | None:
        return self.modules.get(key)
    
    def shutdown(self) -> None:
        """Call teardown() in reverse load order."""
```

---

## 4. PanelManager (`src/core/panel_manager.py`)

Tracks widget registrations for the main window's two content areas.

```python
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class PanelRegistration:
    id: str                          # "core/preview", "cooldown_rotation/slot_states"
    area: str                        # "primary" or "sidebar"
    factory: Callable[[], Any]       # Returns QWidget when called
    title: str = ""                  # Display title for the panel header
    owner: str = ""                  # Module key that registered it
    order: int = 50                  # Sort order (lower = higher in stack)
    collapsible: bool = True         # Can the user collapse this panel?
    default_collapsed: bool = False
    visible: bool = True             # Can be hidden by user

class PanelManager:
    def __init__(self):
        self._panels: dict[str, PanelRegistration] = {}  # id -> registration
    
    def register(
        self,
        id: str,
        area: str,
        factory: Callable,
        *,
        title: str = "",
        owner: str = "",
        order: int = 50,
        collapsible: bool = True,
        default_collapsed: bool = False,
    ) -> None:
        """Register a panel. Called by modules during setup()."""
        self._panels[id] = PanelRegistration(
            id=id, area=area, factory=factory, title=title,
            owner=owner, order=order, collapsible=collapsible,
            default_collapsed=default_collapsed,
        )
    
    def get_panels(self, area: str) -> list[PanelRegistration]:
        """Return panels for an area, sorted by order."""
        return sorted(
            [p for p in self._panels.values() if p.area == area and p.visible],
            key=lambda p: p.order,
        )
    
    def teardown_module(self, module_key: str) -> None:
        """Remove all panels owned by a module."""
        self._panels = {k: v for k, v in self._panels.items() if v.owner != module_key}
```

---

## 5. SettingsManager (`src/core/settings_manager.py`)

Tracks settings registrations as a path-based tree. This is what makes the settings system fully extensible — any module can register settings at any path, including inside another module's tab.

```python
@dataclass
class SettingsRegistration:
    path: str                         # "detection/brightness", "automation", "buff_tracking"
    factory: Callable[[], Any]        # Returns QWidget when called
    title: str = ""                   # Display title
    owner: str = ""                   # Module key
    order: int = 50                   # Sort order within parent

class SettingsManager:
    def __init__(self):
        self._registrations: dict[str, SettingsRegistration] = {}
    
    def register(
        self,
        path: str,
        factory: Callable,
        *,
        title: str = "",
        owner: str = "",
        order: int = 50,
    ) -> None:
        """
        Register a settings widget at a path.
        
        Path rules:
        - "foo"              -> top-level tab named "foo"
        - "foo/bar"          -> section "bar" inside tab "foo"
        
        Phase 1 supports two levels: tabs and sections within tabs.
        Deeper nesting (e.g. "foo/bar/baz") is not required yet — can be added later.
        
        If a parent path has no explicit registration (e.g. someone registers
        "detection/brightness" but nobody registered "detection"), an empty 
        container tab is auto-created to hold the children.
        """
        self._registrations[path] = SettingsRegistration(
            path=path, factory=factory, title=title, owner=owner, order=order,
        )
    
    def get_tabs(self) -> list[dict]:
        """
        Build the tab tree from registrations.
        
        Algorithm:
        1. Group all registrations by their first path segment (the tab name).
           - "detection/brightness" has tab "detection", child key "brightness"
           - "automation" has tab "automation", no children from this entry
           - "demo" has tab "demo"
        2. For each unique tab name:
           a. If a registration exists at the exact tab path (e.g. "automation"),
              use its factory as the tab's widget_factory and its title/order.
           b. If no registration exists at the tab path but children exist
              (e.g. only "detection/brightness" and "detection/glow" registered),
              set widget_factory to None — the settings dialog will create an
              empty scrollable container and place the children as sections inside it.
           c. Collect all registrations whose path starts with "{tab_name}/"
              as children of that tab.
        3. Sort tabs by order (use the tab-level registration's order if it exists,
           otherwise use the minimum order among its children).
        4. Sort children within each tab by order.
        
        Returns list of:
        {
            "path": "detection",
            "title": "Detection",
            "widget_factory": Callable | None,
            "order": 50,
            "children": [
                {
                    "path": "detection/brightness",
                    "title": "Brightness Detection",
                    "widget_factory": Callable,
                    "order": 10,
                },
            ]
        }
        """
    
    def teardown_module(self, module_key: str) -> None:
        """Remove all registrations owned by a module."""
        self._registrations = {
            k: v for k, v in self._registrations.items() if v.owner != module_key
        }
```

---

## 6. WindowManager (`src/core/window_manager.py`)

The "proper way" for modules to create windows. Handles lazy instantiation, geometry persistence, and provides discovery for the Windows menu.

```python
@dataclass
class WindowRegistration:
    id: str                          # "health_monitor/display"
    factory: Callable[[], Any]       # Returns QWidget/QDialog/QMainWindow
    title: str = ""
    window_type: str = "panel"       # "panel" | "overlay" | "dialog" | "tool"
    owner: str = ""                  # Module key
    default_visible: bool = False
    remember_geometry: bool = True
    show_in_menu: bool = True
    singleton: bool = True
    instance: Any = None             # Lazily created

class WindowManager:
    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager
        self._registry: dict[str, WindowRegistration] = {}
    
    def register(
        self,
        id: str,
        factory: Callable,
        *,
        title: str = "",
        window_type: str = "panel",
        owner: str = "",
        default_visible: bool = False,
        remember_geometry: bool = True,
        show_in_menu: bool = True,
        singleton: bool = True,
    ) -> None:
        """Register a managed window. Factory is NOT called until show()."""
        self._registry[id] = WindowRegistration(
            id=id, factory=factory, title=title, window_type=window_type,
            owner=owner, default_visible=default_visible,
            remember_geometry=remember_geometry, show_in_menu=show_in_menu,
            singleton=singleton,
        )
    
    def show(self, id: str) -> None:
        """Show a window. Creates lazily on first call. Restores saved geometry."""
        entry = self._registry.get(id)
        if entry is None:
            return
        if entry.instance is None:
            entry.instance = entry.factory()
            entry.instance.setWindowTitle(entry.title or entry.id)
            if entry.remember_geometry:
                self._restore_geometry(entry)
        entry.instance.show()
        entry.instance.raise_()
    
    def hide(self, id: str) -> None:
        entry = self._registry.get(id)
        if entry and entry.instance:
            entry.instance.hide()
    
    def toggle(self, id: str) -> None:
        entry = self._registry.get(id)
        if entry and entry.instance and entry.instance.isVisible():
            self.hide(id)
        else:
            self.show(id)
    
    def is_visible(self, id: str) -> bool:
        entry = self._registry.get(id)
        return bool(entry and entry.instance and entry.instance.isVisible())
    
    def get(self, id: str) -> Any:
        """Get the window instance (None if not yet created)."""
        entry = self._registry.get(id)
        return entry.instance if entry else None
    
    def list_menu_entries(self) -> list[WindowRegistration]:
        """Return windows that should appear in the Windows menu, sorted by title."""
        return sorted(
            [r for r in self._registry.values() if r.show_in_menu],
            key=lambda r: r.title or r.id,
        )
    
    def show_defaults(self) -> None:
        """Show windows with default_visible=True (unless overridden by saved visibility)."""
        app_cfg = self._config.get("app")
        saved_geo = app_cfg.get("window_geometry", {})
        for entry in self._registry.values():
            saved = saved_geo.get(entry.id, {})
            if saved.get("visible", entry.default_visible):
                self.show(entry.id)
    
    def save_all_geometry(self) -> None:
        """Persist geometry for all created windows. Called on app exit.
        
        IMPORTANT: ConfigManager.get() returns a copy. We must read, modify, 
        and write back with config.set() for changes to persist.
        """
        geo = {}
        for entry in self._registry.values():
            if entry.instance and entry.remember_geometry:
                rect = entry.instance.geometry()
                geo[entry.id] = {
                    "x": rect.x(), "y": rect.y(),
                    "w": rect.width(), "h": rect.height(),
                    "visible": entry.instance.isVisible(),
                }
        # Read → modify → write back (get() returns a copy!)
        app_cfg = self._config.get("app")
        app_cfg["window_geometry"] = geo
        self._config.set("app", app_cfg)
    
    def teardown_module(self, module_key: str) -> None:
        """Close and remove all windows owned by a module."""
        to_remove = [k for k, v in self._registry.items() if v.owner == module_key]
        for id in to_remove:
            entry = self._registry[id]
            if entry.instance:
                entry.instance.close()
            del self._registry[id]
    
    def teardown(self) -> None:
        """Save geometry and close all windows. Called on app exit."""
        self.save_all_geometry()
        for entry in self._registry.values():
            if entry.instance:
                entry.instance.close()
                entry.instance = None
    
    def _restore_geometry(self, entry: WindowRegistration) -> None:
        app_cfg = self._config.get("app")
        saved = app_cfg.get("window_geometry", {}).get(entry.id)
        if saved and entry.instance:
            entry.instance.setGeometry(saved["x"], saved["y"], saved["w"], saved["h"])
```

---

## 7. Core (`src/core/core.py`)

Thin facade. Modules interact with Core to access all managers.

```python
class Core:
    def __init__(self, config: ConfigManager):
        self._config = config
        self._modules: dict[str, BaseModule] = {}
        self._hooks: dict[str, list[Callable]] = {}
        
        # Managers — modules access these through Core
        self.panels = PanelManager()
        self.settings = SettingsManager()
        self.windows = WindowManager(config)
    
    # --- Config ---
    def get_config(self, namespace: str) -> dict:
        return self._config.get(namespace)
    
    def save_config(self, namespace: str, data: dict) -> None:
        self._config.set(namespace, data)
    
    def update_config(self, namespace: str, updates: dict) -> None:
        self._config.update(namespace, updates)
    
    # --- Module access ---
    def get_module(self, key: str) -> BaseModule | None:
        return self._modules.get(key)
    
    def is_loaded(self, key: str) -> bool:
        return key in self._modules
    
    def register_module(self, key: str, module: BaseModule) -> None:
        """Called by ModuleManager during load(). Not for module use."""
        self._modules[key] = module
    
    # --- Services ---
    def get_service(self, module_key: str, service_name: str) -> Any:
        """Read a service value from another module. Returns None if unavailable."""
        mod = self._modules.get(module_key)
        if mod is None:
            return None
        try:
            return mod.get_service(service_name)
        except Exception:
            return None
    
    # --- Hooks ---
    def subscribe(self, hook: str, callback: Callable) -> None:
        """Subscribe to a hook. Hook name format: '{module_key}.{hook_name}'."""
        self._hooks.setdefault(hook, []).append(callback)
    
    def emit(self, hook: str, **kwargs) -> None:
        """Emit a hook. Exceptions per-subscriber are logged, not propagated."""
        import logging
        logger = logging.getLogger(__name__)
        for cb in self._hooks.get(hook, []):
            try:
                cb(**kwargs)
            except Exception as e:
                logger.exception("Hook %s subscriber failed: %s", hook, e)
```

---

## 8. Main Window (`src/ui/main_window.py`)

A shell that renders panels from PanelManager. Reference `/v1/src/ui/themes/__init__.py` and `/v1/modules/cooldown_rotation/status_widget.py` for the color palette and section styling.

**Layout:**
```
┌─ Toolbar ──────────────────────────────────────┐
│  [⚙ Settings]  [Windows ▾]   Status message    │
├─────────────────────────────────┬───────────────┤
│  Primary Area (scrollable)      │ Sidebar       │
│                                 │ (scrollable)  │
│  ┌───────────────────────────┐  │ ┌───────────┐│
│  │ ▾ DEMO PANEL              │  │ │ ▾ DEMO    ││
│  │ (content from module)     │  │ │  SIDEBAR  ││
│  └───────────────────────────┘  │ │ (content) ││
│  ┌───────────────────────────┐  │ └───────────┘│
│  │ ▾ ANOTHER PANEL           │  │              │
│  │ (content)                 │  │              │
│  └───────────────────────────┘  │              │
│                                 │              │
├─────────────────────────────────┴───────────────┤
│  Status bar                                     │
└─────────────────────────────────────────────────┘
```

**CollapsiblePanel** wraps each module widget:
- Header bar: dark bg (`#1e1e2e`), monospace uppercase title (`#666`), collapse arrow
- Content area: section bg (`#252535`), border (`#3a3a4a`), rounded corners
- Click header to toggle collapsed state

```python
class CollapsiblePanel(QFrame):
    """Wraps a module's widget with a collapsible header bar."""
    
    def __init__(self, title: str, content: QWidget, collapsible=True, collapsed=False, parent=None):
        # Header: QHBoxLayout with title label + arrow label ("▾" / "▸")
        # Content: the widget, hidden when collapsed
        # Click header toggles content visibility + swaps arrow character

class MainWindow(QMainWindow):
    settings_requested = pyqtSignal()  # Connected to settings_dialog.show_or_raise by main.py
    
    def __init__(self, core: Core):
        super().__init__()
        self._core = core
        self.setWindowTitle("arianagrande.gif")
        self.setMinimumSize(700, 550)
        self._build_ui()
        self._populate_panels()
    
    def _build_ui(self):
        # Toolbar: Settings button, Windows menu button, status message label (right-aligned)
        # Central: QSplitter horizontal
        #   Left (stretch 3): QScrollArea > QWidget > QVBoxLayout for primary panels
        #   Right (stretch 1, width ~220): QScrollArea > QWidget > QVBoxLayout for sidebar panels
        # Status bar at bottom
    
    def _populate_panels(self):
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
    
    def _build_windows_menu(self) -> QMenu:
        """Build the Windows dropdown from WindowManager. Called each time the menu button is clicked."""
        menu = QMenu(self)
        for entry in self._core.windows.list_menu_entries():
            action = menu.addAction(entry.title or entry.id)
            action.setCheckable(True)
            action.setChecked(self._core.windows.is_visible(entry.id))
            action.triggered.connect(
                lambda checked, id=entry.id: self._core.windows.toggle(id)
            )
        return menu
    
    def show_status_message(self, text: str, timeout_ms: int = 0):
        self._status_label.setText(text)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._status_label.setText(""))
```

Default window size 700x550. Sidebar ~220px. Use QSplitter so user can drag the divider.

---

## 9. Settings Dialog (`src/ui/settings_dialog.py`)

Non-modal dialog that builds tabs from the SettingsManager tree. Reference `/v1/src/ui/settings_dialog.py` for `_section_frame`, `_subsection_frame`, `_row_label` styling patterns.

```python
class SettingsDialog(QDialog):
    def __init__(self, core: Core, parent=None):
        super().__init__(parent)
        self._core = core
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 600)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        self._build_tabs()
    
    def _build_tabs(self):
        """Build all tabs from the settings tree."""
        for tab_info in self._core.settings.get_tabs():
            tab_widget = self._build_tab(tab_info)
            title = tab_info["title"] or tab_info["path"].replace("_", " ").title()
            self._tabs.addTab(tab_widget, title)
    
    def _build_tab(self, tab_info: dict) -> QWidget:
        """
        Build a tab's content.
        - If tab has widget_factory: call it for main content
        - If tab has children: add them as styled sections below
        - If tab has only children (no own widget): scroll area of sections
        """
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        
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
    
    def show_or_raise(self):
        if self.isVisible():
            self.raise_()
            self.activateWindow()
        else:
            self.show()
    
    def rebuild(self):
        """Rebuild all tabs. Call if modules loaded/unloaded at runtime."""
        while self._tabs.count():
            self._tabs.removeTab(0)
        self._build_tabs()
```

Implement `_section_frame(title, content)` as a standalone helper function. Wraps a widget in a styled QFrame: bg `#252535`, border `1px solid #3a3a4a`, radius 4px, monospace uppercase title label in `#666`.

---

## 10. Theme (`src/ui/themes/__init__.py`)

Reference `/v1/src/ui/themes/__init__.py` for the color palette. Build a complete QSS stylesheet covering all standard widgets. Key colors:

```python
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
    "text_title": "#666",
    "text_accent": "#66eeff",
}
```

Build a `build_stylesheet() -> str` function that returns the full QSS. Cover: QMainWindow, QDialog, QFrame, QLabel, QPushButton (normal/hover/pressed states), QSpinBox, QLineEdit, QComboBox (dropdown styling), QCheckBox, QSlider (groove + handle), QTabWidget + QTabBar (selected/unselected tabs), QScrollArea, QScrollBar (thin dark), QSplitter (subtle handle), QMenu (dark dropdown), QToolBar. Make it look polished — this is the app's skin.

---

## 11. Demo Module (`modules/demo/module.py`)

Proves the full registration pipeline works.

```python
from src.core.base_module import BaseModule

class DemoModule(BaseModule):
    name = "Demo"
    key = "demo"
    version = "1.0.0"
    description = "Test module — registers panels, settings, and a window"
    
    def setup(self, core):
        super().setup(core)
        
        # Primary panel
        core.panels.register(
            id=f"{self.key}/main_panel",
            area="primary",
            factory=self._build_main_panel,
            title="Demo Panel",
            owner=self.key,
            order=10,
        )
        
        # Sidebar panel
        core.panels.register(
            id=f"{self.key}/sidebar_panel",
            area="sidebar",
            factory=self._build_sidebar_panel,
            title="Demo Sidebar",
            owner=self.key,
            order=10,
        )
        
        # Own settings tab
        core.settings.register(
            path=self.key,
            factory=self._build_settings,
            title="Demo",
            owner=self.key,
        )
        
        # Inject a section into a shared "detection" tab
        # (demonstrates cross-module settings injection)
        core.settings.register(
            path="detection/demo_detector",
            factory=self._build_detection_settings,
            title="Demo Detector",
            owner=self.key,
            order=99,
        )
        
        # Managed window
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
```

`modules/demo/__init__.py`:
```python
from modules.demo.module import DemoModule
```

---

## 12. main.py (`src/main.py`)

```python
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


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
    
    # Config
    config = ConfigManager(CONFIG_PATH)
    config.load()
    
    # Core
    core = Core(config)
    
    # Modules
    module_manager = ModuleManager(core)
    module_manager.discover(MODULES_DIR)
    
    # Load enabled modules — fall back to all discovered if config missing/empty
    enabled = config.get("app").get("modules_enabled") or None
    module_manager.load(enabled)
    
    # UI
    window = MainWindow(core)
    settings_dialog = SettingsDialog(core, parent=window)
    window.settings_requested.connect(settings_dialog.show_or_raise)
    
    # Show managed windows with default_visible=True
    core.windows.show_defaults()
    
    window.show()
    exit_code = app.exec()
    
    # Shutdown
    core.windows.teardown()
    module_manager.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

---

## 13. Default Config (`config/default_config.json`)

```json
{
  "app": {
    "modules_enabled": ["demo"],
    "window_geometry": {}
  },
  "demo": {
    "message": "Hello from demo module"
  }
}
```

---

## Verification

When the app starts:

1. Main window appears with title "arianagrande.gif" and dark theme
2. Primary area shows "DEMO PANEL" in a collapsible section with content
3. Sidebar shows "DEMO SIDEBAR" panel
4. Clicking the collapse arrow hides/shows the panel content
5. Clicking "Settings" opens dialog with two tabs: "Demo" and "Detection"
6. "Demo" tab has a text input and a "Show Demo Popup" button
7. "Detection" tab has a section "Demo Detector" with italic text (auto-created container tab with one injected section)
8. Typing in the text input persists to `config/default_config.json`
9. "Show Demo Popup" opens a managed window
10. Move the popup, close app, restart — popup position is restored
11. "Windows" menu in toolbar shows "Demo Popup" with checkmark toggle
12. Console shows module discovery and lifecycle logs

---

## What This Phase Does NOT Include

- No capture system / screen grabbing (Phase 2)
- No frame processing / on_frame() (Phase 2)
- No overlay (Phase 2)
- No detection or automation logic (Phase 3+)
- No drag-to-reorder panels (future enhancement)
- No v1 code migration (later phases)

The shell is the skeleton. Modules are the muscles. This phase builds the skeleton.