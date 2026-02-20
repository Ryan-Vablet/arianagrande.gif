# arianagrande.gif — Phase 4: Automation Module

## Prerequisites

Phase 1 (shell), Phase 2 (core capture), Phase 3 (brightness detection) are complete. Slot states flow from brightness detection and are available as a service via `core.get_service("brightness_detection", "slot_states")`. 91 tests passing.

## Goal

Build the **automation module** — the brain that reads slot states and sends keys. When this phase is done:

- The user can configure priority lists (ordered slot + manual items)
- Multiple priority lists are supported (single target, AoE, etc.) with per-list hotkeys
- The automation engine evaluates priority and sends the correct key
- Auto-fire mode loops automatically; single-fire mode fires once per hotkey press
- Arm/disarm toggle protects against accidental key sending
- A priority list panel in the sidebar shows the current list with drag-and-drop reorder
- A spell queue catches non-priority keypresses and fires them at the next GCD
- All new code has tests

---

## Architecture Overview

### Enable/Disable Model

Recap the layered model, now with automation's "armed" layer:

1. **Capture Start/Stop** — master switch. No frames → nothing works.
2. **Module enabled** — per-module. Brightness detection must be enabled for states to flow.
3. **Automation armed** — the safety switch. Even if the module is enabled, no keys are sent unless armed. This is separate from module enable because:
   - Enabled + unarmed = module receives frames, shows priority status, displays what WOULD be pressed, but sends nothing. Great for debugging rotations.
   - Enabled + armed = keys are actually sent to the game.
   - Disabled = module doesn't process frames at all.

The arm/disarm toggle is controlled by a global hotkey (works when game is focused) and a button in the UI.

### Priority List Model

```
Automation Config
├── keybinds: ["1", "2", "3", ...]        ← per-slot, shared across all lists
├── slot_display_names: ["Fireball", ...]  ← per-slot, shared
├── active_list_id: "single_target"
├── priority_lists:
│   ├── {id: "single_target", name: "Single Target", toggle_bind: "f5", single_fire_bind: "f6",
│   │    priority_items: [{type:"slot", slot_index:0, activation_rule:"always"}, ...],
│   │    manual_actions: [{id:"trinket", name:"Trinket", keybind:"f1"}]}
│   └── {id: "aoe", name: "AoE", toggle_bind: "f7", single_fire_bind: "f8",
│        priority_items: [...], manual_actions: [...]}
```

**Keybinds** are per-slot and shared across all lists. They're your WoW action bar keybinds — they don't change when you switch lists. What changes is the priority ORDER and which slots are included.

**Each priority list has:**
- `id` / `name` — identity
- `toggle_bind` — global hotkey. Press to activate this list + arm auto-fire. Press again to disarm.
- `single_fire_bind` — global hotkey. Press to fire the next priority from THIS list once. Doesn't arm auto-fire.
- `priority_items` — ordered list of items. Each is either:
  - `{type: "slot", slot_index: int, activation_rule: "always"|"dot_refresh"|"require_glow"}`
  - `{type: "manual", action_id: str}` (references a manual_actions entry)
- `manual_actions` — `[{id, name, keybind}]` — actions not tied to monitored slots

**Switching lists:** Pressing a list's toggle_bind makes it active and arms automation. Pressing the active list's toggle_bind again disarms. This means you can have AoE on F7 — press F7 to switch to AoE and start firing, press F7 again to stop.

**Single-fire:** Pressing a list's single_fire_bind fires the next priority from that list ONE TIME, regardless of which list is currently "active." This allows one-shot macros: "press F8 to fire the next AoE priority once, then go back to whatever you were doing."

---

## v1 Reference

Port and adapt from these files:

- `/v1/src/automation/key_sender.py` (305 lines) — `KeySender.evaluate_and_send()`. Adapt to remove `AppConfig` dependency, use flat config.
- `/v1/src/automation/priority_rules.py` (179 lines) — Eligibility functions. Port directly.
- `/v1/src/automation/binds.py` (130 lines) — Keybind normalization. Port directly.
- `/v1/src/automation/global_hotkey.py` (230 lines) — `GlobalToggleListener`, `CaptureOneKeyThread`. Port directly.
- `/v1/src/automation/queue_listener.py` (192 lines) — `QueueListener`. Port directly.
- `/v1/src/ui/priority_panel.py` (861 lines) — `PriorityPanel`, `PriorityListWidget`, `PriorityItemWidget`. Port and simplify.

---

## New / Modified Files

```
/v2/
  src/
    automation/
      __init__.py
      binds.py                    # Keybind normalization (port from v1)
      priority_rules.py           # Eligibility helpers (port from v1)
  modules/
    automation/
      __init__.py
      module.py                   # AutomationModule
      key_sender.py               # KeySender engine
      queue_listener.py           # Spell queue (port from v1)
      global_hotkey.py            # Global hotkey listener (port from v1)
      priority_panel.py           # Sidebar panel: drag-and-drop priority list
      settings_widget.py          # Automation settings
      controls_widget.py          # Arm/disarm button + status for primary area
  tests/
    ... (existing tests unchanged)
    test_binds.py
    test_priority_rules.py
    test_key_sender.py
    test_automation_module.py
```

---

## 1. Keybind Utilities (`src/automation/binds.py`)

Port directly from `/v1/src/automation/binds.py`. These are shared utilities used by automation and any future module that handles keybinds. Lives in `src/automation/` (not inside the module) because other modules will import it too.

Key functions:
- `normalize_bind(bind: str) -> str` — canonicalize `"Control + 1"` → `"ctrl+1"`
- `normalize_key_token(token: str) -> str` — single key normalization
- `normalize_bind_from_parts(modifiers: set, primary: str) -> str`
- `is_modifier_token(token: str) -> bool`
- `parse_bind(bind: str) -> tuple[frozenset[str], str] | None`
- `format_bind_for_display(bind: str) -> str` — `"ctrl+1"` → `"Ctrl+1"`

Copy the v1 implementation as-is. It works.

---

## 2. Priority Rules (`src/automation/priority_rules.py`)

Port from `/v1/src/automation/priority_rules.py`. Eligibility checking functions:

- `normalize_activation_rule(raw) -> str` — "always", "dot_refresh", "require_glow"
- `normalize_ready_source(raw, item_type) -> str` — "slot", "always", "buff_present", "buff_missing"
- `dot_refresh_eligible(yellow_glow_ready, red_glow_ready) -> bool`
- `slot_item_is_eligible_for_state_dict(item, slot_state, buff_states) -> bool`
- `manual_item_is_eligible(item, buff_states) -> bool`

**Note on glow/buff fields:** These functions reference glow_ready, yellow_glow_ready, red_glow_ready, and buff states. Glow detection and buff tracking modules don't exist yet, but the priority rules should still handle them — they'll just get `False`/empty values until those modules are built. This forward-compatibility is important.

Port the v1 implementation directly. The logic is correct and well-tested.

---

## 3. KeySender (`modules/automation/key_sender.py`)

The engine that evaluates priority and sends keys. Adapted from `/v1/src/automation/key_sender.py`.

```python
class KeySender:
    """Evaluates priority list and sends the highest-priority ready keybind."""
    
    def __init__(self):
        self._last_send_time: float = 0.0
        self._suppress_priority_until: float = 0.0
        self._single_fire_pending: bool = False
        self._single_fire_list_id: str | None = None  # Which list the single fire targets
    
    def request_single_fire(self, list_id: str | None = None) -> None:
        """Arm a single key send. If list_id provided, fire from that specific list."""
        self._single_fire_pending = True
        self._single_fire_list_id = list_id
    
    def evaluate_and_send(
        self,
        slot_states: list[dict],
        priority_items: list[dict],
        keybinds: list[str],
        manual_actions: list[dict],
        armed: bool,
        *,
        min_interval_ms: int = 150,
        target_window_title: str = "",
        allow_cast_while_casting: bool = False,
        queue_window_ms: int = 120,
        gcd_ms: int = 1500,
        queued_override: dict | None = None,
        on_queued_sent: Callable | None = None,
        buff_states: dict | None = None,
        queue_fire_delay_ms: int = 100,
    ) -> dict | None:
        """
        Evaluate and optionally send a key.
        
        Returns dict describing what happened:
        - {"action": "sent", "keybind": "1", "slot_index": 0, ...}
        - {"action": "blocked", "reason": "casting"|"window", ...}
        - None if nothing to do
        
        Port logic from v1 KeySender.evaluate_and_send but remove AppConfig dependency.
        All config values are passed as keyword arguments.
        
        Algorithm:
        1. If not armed and no single_fire pending → return None
        2. Check min_interval timing
        3. Check target window focus
        4. Check for blocking cast (unless allow_cast_while_casting)
        5. Handle queued override (whitelist or tracked slot)
        6. Walk priority_items in order:
           a. For slot items: check slot_item_is_eligible (from priority_rules)
           b. For manual items: check manual_item_is_eligible
           c. First eligible item → send its keybind via `keyboard.send()`
        7. Return result dict or None
        """
```

**Key difference from v1:** No `AppConfig` parameter. All values passed explicitly. The module is responsible for reading config and passing the right values.

### Window Focus Check

Port `is_target_window_active()` from v1. On Windows, uses `ctypes` to check foreground window title. On other platforms, always returns True (game is assumed focused).

---

## 4. Queue Listener (`modules/automation/queue_listener.py`)

Port from `/v1/src/automation/queue_listener.py`. The spell queue catches keypresses that aren't in the priority list and queues them to fire at the next GCD.

**Concept:** You have Fireball on key `1` in priority. You manually press key `5` (Polymorph, not in priority). The queue catches this and fires it at the next GCD window, then resumes normal priority rotation.

Key classes:
- `QueueListener` — manages the queue state, timeout, thread-safe access
- `_QueueHookThread` — background thread using `keyboard.hook`

Port as-is. Adapt to read config from the module instead of `AppConfig`.

---

## 5. Global Hotkey Listener (`modules/automation/global_hotkey.py`)

Port from `/v1/src/automation/global_hotkey.py`. Two key classes:

### GlobalToggleListener

Listens for global hotkeys even when the app doesn't have focus. Used for:
- Per-list toggle binds (arm/disarm + activate list)
- Per-list single-fire binds

Uses `keyboard.hook` (low-level) instead of `keyboard.add_hotkey` because add_hotkey misses keys when other keys (W, right-click) are held during gameplay.

### CaptureOneKeyThread

Captures the next keypress for keybind recording in the UI. Start it, press a key, it emits the captured bind string.

Port both as-is from v1.

---

## 6. AutomationModule (`modules/automation/module.py`)

```python
class AutomationModule(QObject, BaseModule, metaclass=CombinedMeta):
    """Automation engine: reads slot states, evaluates priority, sends keys."""
    
    name = "Automation"
    key = "automation"
    version = "1.0.0"
    description = "Priority-based key sending with multiple lists, auto/single fire, spell queue"
    requires = ["core_capture"]
    optional = ["brightness_detection", "glow_detection", "cast_bar", "buff_tracking"]
    provides_services = ["armed", "active_list_id", "last_action"]
    hooks = ["key_sent", "armed_changed", "list_switched"]
    
    # Signals
    key_action_signal = pyqtSignal(dict)    # Key was sent or blocked
    armed_changed_signal = pyqtSignal(bool) # Armed state changed
    list_changed_signal = pyqtSignal(str)   # Active list ID changed
    
    def __init__(self):
        QObject.__init__(self)
        BaseModule.__init__(self)
        self._key_sender = None
        self._queue_listener = None
        self._hotkey_listener = None
        self._armed = False
        self._last_action: dict | None = None
    
    def setup(self, core):
        super().setup(core)
        from modules.automation.key_sender import KeySender
        
        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())
        
        self._key_sender = KeySender()
        
        # Arm/disarm + status panel (primary area)
        core.panels.register(
            id=f"{self.key}/controls",
            area="primary",
            factory=self._build_controls,
            title="Automation",
            owner=self.key,
            order=5,  # After preview (0), capture controls (1), before slot states (10)
        )
        
        # Priority list panel (sidebar)
        core.panels.register(
            id=f"{self.key}/priority",
            area="sidebar",
            factory=self._build_priority_panel,
            title="Priority",
            owner=self.key,
            order=0,  # First in sidebar
        )
        
        # Settings subtabs under automation
        core.settings.register(
            path="automation/general",
            factory=self._build_general_settings,
            title="General",
            owner=self.key,
            order=0,
        )
        core.settings.register(
            path="automation/keybinds",
            factory=self._build_keybind_settings,
            title="Keybinds",
            owner=self.key,
            order=10,
        )
        core.settings.register(
            path="automation/priority_lists",
            factory=self._build_list_settings,
            title="Priority Lists",
            owner=self.key,
            order=20,
        )
        core.settings.register(
            path="automation/queue",
            factory=self._build_queue_settings,
            title="Spell Queue",
            owner=self.key,
            order=30,
        )
    
    def ready(self):
        """Start the hotkey listener after all modules are set up."""
        self._start_hotkey_listener()
        self._start_queue_listener()
    
    def on_frame(self, frame) -> None:
        """Called per frame. Read slot states from brightness detection and evaluate priority."""
        if not self._key_sender:
            return
        
        cfg = self._get_merged_config()
        slot_states = self.core.get_service("brightness_detection", "slot_states") or []
        if not slot_states:
            return
        
        # Get active priority list
        active_list = self._get_active_list()
        if not active_list:
            return
        
        # Get optional data from other modules
        buff_states = self.core.get_service("buff_tracking", "buff_states")
        
        # Queue
        queued = self._queue_listener.get_queue() if self._queue_listener else None
        on_queued_sent = self._queue_listener.clear_queue if self._queue_listener else None
        
        result = self._key_sender.evaluate_and_send(
            slot_states=slot_states,
            priority_items=active_list.get("priority_items", []),
            keybinds=cfg.get("keybinds", []),
            manual_actions=active_list.get("manual_actions", []),
            armed=self._armed,
            min_interval_ms=cfg.get("min_press_interval_ms", 150),
            target_window_title=cfg.get("target_window_title", ""),
            allow_cast_while_casting=cfg.get("allow_cast_while_casting", False),
            queue_window_ms=cfg.get("queue_window_ms", 120),
            gcd_ms=cfg.get("gcd_ms", 1500),
            queued_override=queued,
            on_queued_sent=on_queued_sent,
            buff_states=buff_states,
            queue_fire_delay_ms=cfg.get("queue_fire_delay_ms", 100),
        )
        
        if result:
            self._last_action = result
            self.key_action_signal.emit(result)
            self.core.emit(f"{self.key}.key_sent", **result)
    
    # --- Arm/disarm ---
    
    def arm(self):
        if not self._armed:
            self._armed = True
            self.armed_changed_signal.emit(True)
            self.core.emit(f"{self.key}.armed_changed", armed=True)
    
    def disarm(self):
        if self._armed:
            self._armed = False
            self.armed_changed_signal.emit(False)
            self.core.emit(f"{self.key}.armed_changed", armed=False)
    
    def toggle_armed(self):
        if self._armed:
            self.disarm()
        else:
            self.arm()
    
    # --- List switching ---
    
    def switch_to_list(self, list_id: str):
        """Activate a priority list by ID."""
        cfg = self.core.get_config(self.key)
        lists = cfg.get("priority_lists", [])
        if any(pl.get("id") == list_id for pl in lists):
            cfg["active_list_id"] = list_id
            self.core.save_config(self.key, cfg)
            self.list_changed_signal.emit(list_id)
            self.core.emit(f"{self.key}.list_switched", list_id=list_id)
    
    def _get_active_list(self) -> dict | None:
        cfg = self.core.get_config(self.key)
        active_id = cfg.get("active_list_id", "")
        for pl in cfg.get("priority_lists", []):
            if pl.get("id") == active_id:
                return pl
        lists = cfg.get("priority_lists", [])
        return lists[0] if lists else None
    
    # --- Hotkey handling ---
    
    def _on_hotkey_triggered(self, bind: str):
        """Called when any registered global hotkey is pressed."""
        cfg = self.core.get_config(self.key)
        for pl in cfg.get("priority_lists", []):
            if pl.get("toggle_bind") == bind:
                if cfg.get("active_list_id") == pl["id"] and self._armed:
                    # Same list + already armed → disarm
                    self.disarm()
                else:
                    # Different list or not armed → switch + arm
                    self.switch_to_list(pl["id"])
                    self.arm()
                return
            if pl.get("single_fire_bind") == bind:
                # Single fire from this specific list
                self._key_sender.request_single_fire(list_id=pl["id"])
                return
    
    def _start_hotkey_listener(self):
        from modules.automation.global_hotkey import GlobalToggleListener
        
        def get_all_binds():
            cfg = self.core.get_config(self.key)
            binds = []
            for pl in cfg.get("priority_lists", []):
                tb = pl.get("toggle_bind", "")
                if tb:
                    binds.append(tb)
                sfb = pl.get("single_fire_bind", "")
                if sfb:
                    binds.append(sfb)
            return binds
        
        self._hotkey_listener = GlobalToggleListener(get_all_binds)
        self._hotkey_listener.triggered.connect(self._on_hotkey_triggered)
        self._hotkey_listener.start()
    
    def _start_queue_listener(self):
        from modules.automation.queue_listener import QueueListener
        self._queue_listener = QueueListener(
            get_config=lambda: self._get_merged_config_obj(),
        )
        self._queue_listener.start()
    
    # --- Services ---
    
    def get_service(self, name):
        if name == "armed":
            return self._armed
        if name == "active_list_id":
            cfg = self.core.get_config(self.key)
            return cfg.get("active_list_id", "")
        if name == "last_action":
            return self._last_action
        return None
    
    # --- Config ---
    
    def _default_config(self) -> dict:
        return {
            "armed": False,
            "min_press_interval_ms": 150,
            "gcd_ms": 1500,
            "target_window_title": "",
            "allow_cast_while_casting": False,
            "queue_window_ms": 120,
            "queue_whitelist": [],
            "queue_timeout_ms": 5000,
            "queue_fire_delay_ms": 100,
            "active_list_id": "default",
            "keybinds": [],
            "slot_display_names": [],
            "priority_lists": [
                {
                    "id": "default",
                    "name": "Default",
                    "toggle_bind": "",
                    "single_fire_bind": "",
                    "priority_items": [],
                    "manual_actions": [],
                }
            ],
        }
    
    def _get_merged_config(self) -> dict:
        return self.core.get_config(self.key)
    
    # --- Teardown ---
    
    def teardown(self):
        self.disarm()
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        if self._queue_listener:
            self._queue_listener.stop()
    
    # --- Widget builders (implementations in separate files) ---
    
    def _build_controls(self):
        from modules.automation.controls_widget import AutomationControls
        return AutomationControls(self.core, self)
    
    def _build_priority_panel(self):
        from modules.automation.priority_panel import PriorityPanel
        return PriorityPanel(self.core, self)
    
    def _build_general_settings(self):
        from modules.automation.settings_widget import GeneralSettings
        return GeneralSettings(self.core, self.key)
    
    def _build_keybind_settings(self):
        from modules.automation.settings_widget import KeybindSettings
        return KeybindSettings(self.core, self.key)
    
    def _build_list_settings(self):
        from modules.automation.settings_widget import PriorityListSettings
        return PriorityListSettings(self.core, self.key)
    
    def _build_queue_settings(self):
        from modules.automation.settings_widget import QueueSettings
        return QueueSettings(self.core, self.key)
```

---

## 7. Controls Widget (`modules/automation/controls_widget.py`)

Primary area panel showing arm/disarm button, status, active list name.

```python
class AutomationControls(QWidget):
    """Arm/disarm toggle button + status display."""
    
    def __init__(self, core, module_ref, parent=None):
        # Layout: [ARM/DISARM button] [Status label] [Active list label]
        # 
        # Button:
        #   Disarmed: gray bg, text "▶ ARM"
        #   Armed: red/green pulsing bg, text "⏹ DISARM"
        #   Bold, obvious state — user must always know if keys are being sent
        #
        # Status label: "Armed — sending keys" / "Disarmed" / "Disarmed — no baselines"
        # Active list label: "Single Target" (italic, right-aligned)
        #
        # Connect to module.armed_changed_signal and module.list_changed_signal
```

The arm button should be visually prominent. When armed, the entire row should have a noticeable accent (red border, or green glow) so the user always knows the app is actively sending keystrokes.

---

## 8. Priority Panel (`modules/automation/priority_panel.py`)

The sidebar panel showing the active priority list. Drag-and-drop reorderable. Reference `/v1/src/ui/priority_panel.py` for the item widget design.

```python
class PriorityPanel(QWidget):
    """Sidebar panel: shows active priority list with drag-and-drop reorder."""
    
    def __init__(self, core, module_ref, parent=None):
        # Header: "PRIORITY" label + active list name (italic)
        # List area: QScrollArea containing PriorityItemWidget rows
        # Footer: "+ add slot" / "+ add manual" buttons
        #
        # Subscribes to module.slot_states_updated (from brightness detection)
        # to update per-item state colors
    
    def refresh_from_config(self):
        """Rebuild the item list from config."""
        cfg = self._core.get_config("automation")
        active_list = self._get_active_list(cfg)
        keybinds = cfg.get("keybinds", [])
        display_names = cfg.get("slot_display_names", [])
        
        # Clear existing items
        # For each priority_item in active_list:
        #   Create PriorityItemWidget showing [keybind] display_name
        # Connect drag-and-drop reorder signals
    
    def update_states(self, slot_states: list[dict]):
        """Update per-item state indicators (green=ready, red=cooldown, etc)."""
        # Match slot_states to priority items by slot_index
        # Update each PriorityItemWidget's background/border color


class PriorityItemWidget(QFrame):
    """One row in the priority list. Shows [key] name + state. Draggable."""
    
    def __init__(self, item_data: dict, rank: int, keybind: str, display_name: str, parent=None):
        # Layout: [keybind] display_name [activation_rule] [time_since_fired]
        # 
        # Fixed height ~40px
        # Drag: mousePressEvent → start drag with MIME data
        # Drop: parent PriorityListWidget handles drop → reorder items → save config
        #
        # Right-click context menu:
        #   - Activation rule: Always / DoT Refresh / Require Glow
        #   - Remove from priority
        #   (Activation rules won't do anything until glow module exists,
        #    but the UI and data model should support them now)
    
    def update_state(self, state: str):
        """Update visual state (background color)."""
        # Same color scheme as SlotStatusWidget in Phase 3
```

### Drag and Drop

Use Qt's drag-and-drop with MIME type `application/x-priority-item`. When a user drags an item to a new position:

1. `PriorityItemWidget.mouseMoveEvent` starts a `QDrag` with the item's index
2. `PriorityListWidget.dropEvent` reads the source and target indices
3. Reorder `priority_items` in the active list
4. Save updated config
5. Rebuild the list

### Adding Items

"+ add slot" opens a small dialog listing all slot indices not yet in the priority list. User clicks one to add it at the bottom.

"+ add manual" opens a dialog to create a manual action (name + keybind) and adds it to both `manual_actions` and `priority_items`.

---

## 9. Settings Widgets (`modules/automation/settings_widget.py`)

Four settings classes under the "Automation" tab:

### GeneralSettings (automation/general)

```python
class GeneralSettings(QWidget):
    # - Min Press Interval (QSpinBox, 50-2000 ms, default 150)
    # - GCD Duration (QSpinBox, 500-5000 ms, default 1500)
    # - Target Window Title (QLineEdit, default "" = send to any window)
    #     "Only send keys when this window is focused (leave empty for any)"
    # - Allow Cast While Casting (QCheckBox, default False)
```

### KeybindSettings (automation/keybinds)

```python
class KeybindSettings(QWidget):
    """Per-slot keybind assignment + display names."""
    # Shows one row per slot:
    #   [Slot 0] [Keybind button: "1"] [Display name: QLineEdit "Fireball"]
    #   [Slot 1] [Keybind button: "2"] [Display name: QLineEdit "Frostbolt"]
    #   ...
    #
    # Keybind button: click to record, then press a key.
    #   Uses CaptureOneKeyThread from global_hotkey.py
    #   Shows "Press a key..." while recording
    #   Displays format_bind_for_display() result when set
    #
    # Number of rows = slot count from core_capture config
```

### PriorityListSettings (automation/priority_lists)

```python
class PriorityListSettings(QWidget):
    """Manage multiple priority lists: create, rename, delete, set hotkeys."""
    # List of priority lists (QListWidget or vertical layout)
    # Each row: [Name] [Toggle Bind button] [Single Fire Bind button] [Delete button]
    # 
    # [+ New List] button at bottom
    # 
    # Toggle Bind: click to record hotkey for this list's toggle
    # Single Fire Bind: click to record hotkey for this list's single fire
    #
    # Cannot delete the last remaining list.
    # Active list is highlighted.
```

### QueueSettings (automation/queue)

```python
class QueueSettings(QWidget):
    # - Queue Timeout (QSpinBox, 1000-30000 ms, default 5000)
    # - Queue Fire Delay (QSpinBox, 0-500 ms, default 100)
    # - Queue Whitelist (QTextEdit or QListWidget, one key per line)
    #     "Keys in this list will be queued when pressed, even if not bound to a slot"
```

---

## 10. Update Default Config

```json
{
  "app": {
    "modules_enabled": ["core_capture", "brightness_detection", "automation", "demo"],
    "window_geometry": {}
  },
  "core_capture": { "..." : "..." },
  "brightness_detection": { "..." : "..." },
  "automation": {
    "min_press_interval_ms": 150,
    "gcd_ms": 1500,
    "target_window_title": "",
    "allow_cast_while_casting": false,
    "queue_window_ms": 120,
    "queue_whitelist": [],
    "queue_timeout_ms": 5000,
    "queue_fire_delay_ms": 100,
    "active_list_id": "default",
    "keybinds": [],
    "slot_display_names": [],
    "priority_lists": [
      {
        "id": "default",
        "name": "Default",
        "toggle_bind": "",
        "single_fire_bind": "",
        "priority_items": [],
        "manual_actions": []
      }
    ]
  },
  "demo": { "message": "Hello from demo module" }
}
```

---

## 11. Single-Fire Behavior Detail

When `single_fire_bind` is pressed for a list:

1. `GlobalToggleListener` emits the bind
2. Module's `_on_hotkey_triggered` matches it to a list
3. Calls `key_sender.request_single_fire(list_id=...)`
4. On the NEXT `on_frame` call:
   - If `_single_fire_pending` is True:
     - Load the specified list's priority_items (even if it's not the "active" list)
     - Evaluate priority against current slot states
     - Send the first eligible key
     - Clear `_single_fire_pending`
   - This happens even if automation is not armed (single-fire bypasses arm state)

This means single-fire works like a smart hotkey: "press this to fire the best available ability from this rotation."

**Important:** The `evaluate_and_send` method needs to accept the single-fire state. When `_single_fire_pending` is True, skip the `armed` check. The key_sender already has this logic in v1 (checks `single_fire_pending` separately from `automation_enabled`).

---

## 12. Tests

### `tests/test_binds.py`

```python
# Test: normalize_bind("Control + 1") → "ctrl+1"
# Test: normalize_bind("Shift+F1") → "shift+f1"
# Test: normalize_bind("alt+ctrl+a") → "ctrl+alt+a" (canonical order)
# Test: normalize_bind("") → ""
# Test: normalize_bind("ctrl") → "" (modifier only, no primary)
# Test: is_modifier_token("ctrl") → True
# Test: is_modifier_token("a") → False
# Test: format_bind_for_display("ctrl+1") → "Ctrl+1"
# Test: format_bind_for_display("f5") → "F5"
# Test: parse_bind("ctrl+a") → (frozenset({"ctrl"}), "a")
# Test: normalize_key_token("Left Ctrl") → "ctrl"
# Test: normalize_key_token("esc") → "escape"
```

### `tests/test_priority_rules.py`

```python
# Test: normalize_activation_rule("always") → "always"
# Test: normalize_activation_rule("garbage") → "always"
# Test: normalize_ready_source("slot", "slot") → "slot"
# Test: normalize_ready_source("", "manual") → "always"
# Test: dot_refresh_eligible(False, False) → True (no glow = eligible)
# Test: dot_refresh_eligible(True, False) → False (yellow only = blocked)
# Test: dot_refresh_eligible(False, True) → True (red = eligible)
# Test: slot_item_is_eligible with ready slot → True
# Test: slot_item_is_eligible with cooldown slot → False
# Test: slot_item_is_eligible with activation_rule="require_glow" and no glow → False
# Test: manual_item_is_eligible with ready_source="always" → True
# Test: manual_item_is_eligible with buff_present and no buff data → False
```

### `tests/test_key_sender.py`

```python
# NOTE: Mock keyboard.send to avoid actual key sending in tests.
# 
# Test: not armed, no single_fire → returns None
# Test: armed, no ready slots → returns None
# Test: armed, one ready slot in priority → sends correct key, returns sent dict
# Test: priority order respected (higher priority fires first)
# Test: min_interval_ms throttles sends
# Test: target_window_title blocks when wrong window (mock is_target_window_active)
# Test: blocking cast returns blocked dict
# Test: single_fire_pending sends once then clears
# Test: single_fire bypasses armed check
# Test: queued_override sends queued key when GCD ready
# Test: suppress_priority_until prevents priority send after queued send
# Test: manual action sends when eligible
```

### `tests/test_automation_module.py`

```python
# Test: setup registers panels and settings
# Test: default config created if missing
# Test: arm/disarm toggle
# Test: switch_to_list changes active list
# Test: get_service returns correct values
# Test: on_frame with armed + ready slots → key_action_signal emitted
# Test: on_frame with disarmed → no signal
# Test: _on_hotkey_triggered with toggle_bind → arms + switches
# Test: _on_hotkey_triggered with same toggle_bind when armed → disarms
# Test: _on_hotkey_triggered with single_fire_bind → requests single fire
# Test: teardown disarms and stops listeners
```

---

## Verification

With all modules loaded:

1. Main window shows: Live Preview, Capture Controls, **Automation** (arm button), Slot States
2. Sidebar shows: **Priority** panel (empty list initially)
3. Settings has new "Automation" tab with subtabs: General, Keybinds, Priority Lists, Spell Queue
4. Set keybinds in Keybinds settings → each slot gets a key assignment
5. Add slots to priority list (via "+ add slot") → they appear in the Priority sidebar panel
6. Drag to reorder priority items → order persists
7. Start capture, calibrate baselines → slot states go green
8. Click ARM → button turns red/green, status shows "Armed — sending keys"
9. With WoW focused, the next ready slot's key is sent → "Last Action" updates
10. Click DISARM → key sending stops
11. Set toggle_bind on a priority list → press that key in-game → automation arms
12. Press single_fire_bind → one key fires, then stops
13. Create a second priority list (AoE), set its hotkey → press it to switch
14. All tests pass: `cd v2 && pytest`

---

## What This Phase Does NOT Include

- No profiles (future module: snapshots all config)
- No glow-aware priority rules firing (rules exist but glow module not built yet)
- No buff-aware priority rules (buff module not built yet)
- No overlay rendering of priority state
- No import/export of configurations
- No "last action history" panel (can add later as polish)

The automation module acts. Phase 5+ will add glow, cast bar, buff tracking modules that provide richer data for smarter decisions.
