# arianagrande.gif — Phase 3: Brightness Detection Module

## Prerequisites

Phase 1 (shell) and Phase 2 (core capture, preview, overlay) are complete. Frames flow from CaptureWorker → `module_manager.process_frame()` → each module's `on_frame()`. 56 tests passing.

## Goal

Build the **brightness detection module** — the core detection engine from v1. It receives frames, analyzes per-slot brightness against calibrated baselines, and publishes slot states (READY, ON_COOLDOWN, GCD, CASTING, UNKNOWN). This is the module that other systems (glow detection, automation) will read from.

When this phase is done:

- Frames arrive → brightness detection analyzes each slot → publishes states
- A slot status panel shows live per-slot states as colored indicators
- Settings allow threshold tuning (darken, trigger fraction, change fraction, detection region, etc.)
- Baselines can be calibrated (all at once or per-slot)
- Per-slot states are available as a service for future modules to consume
- All new code has tests

---

## Enable/Disable Model

There is **no global "go" button** for detection. The model is layered:

1. **Capture Start/Stop** (Phase 2) is the master switch. No frames → nothing detects.
2. **Module enabled** flag controls whether `on_frame()` is called. Each module gets an enable/disable toggle in its settings. `ModuleManager.process_frame()` already checks `mod.enabled`.
3. **Automation armed** is a future Phase 4+ concept — automation modules will have an explicit arm/disarm toggle because sending keystrokes is destructive. Detection modules don't need this — detection is passive.

**Flow:** Start Capture → frames flow → all enabled detection modules automatically start analyzing. No extra buttons needed.

If the user wants brightness-only (no glow), they disable the glow module. If they want glow-only, they disable brightness. If they want to pause everything, they stop capture.

---

## v1 Reference

The v1 SlotAnalyzer at `/v1/src/analysis/slot_analyzer.py` (972 lines) is the working implementation. It's monolithic — brightness, glow, cast bar ROI, and buff tracking are all interleaved. For Phase 3, extract **only the brightness detection parts**.

**Copy/adapt from v1:**
- `_recompute_slot_layout()` — slot config computation from bounding box + count/gap/padding
- `crop_slot()` — extract individual slot images from frame
- `_get_brightness_channel()` — BGR → grayscale
- `calibrate_baselines()` / `calibrate_single_slot()` — baseline calibration
- `get_baselines()` / `set_baselines()` — baseline get/set
- The per-slot analysis from `analyze_frame()`:
  - Darkened fraction computation (baseline comparison, detection region)
  - Change fraction computation (absolute delta)
  - Cooldown hysteresis (release threshold)
  - Cooldown minimum duration / GCD state
  - Cast candidate detection (intermediate brightness range)
  - State machine: READY / ON_COOLDOWN / GCD / CASTING / CHANNELING / UNKNOWN

**Do NOT include (belongs to future modules):**
- `_ring_mask()`, `_glow_signal()` → glow_detection module (Phase 5+)
- `_cast_bar_active()` → cast_bar module (Phase 5+)
- `_analyze_buffs()`, `_decode_gray_template()`, `_template_similarity()` → buff_tracking module (Phase 5+)
- All buff/glow runtime fields and state

**Models from v1 to copy into `/v2/src/models/`:**
- `SlotState` enum (READY, ON_COOLDOWN, CASTING, CHANNELING, LOCKED, GCD, UNKNOWN)
- `SlotConfig` dataclass (index, x_offset, y_offset, width, height)
- Simplified `SlotSnapshot` — only brightness-related fields for now

---

## New / Modified Files

```
/v2/
  src/
    models/
      __init__.py                 # Add SlotState, SlotConfig, SlotSnapshot
      geometry.py                 # Phase 2, unchanged
      slot.py                     # NEW: SlotState, SlotConfig, SlotSnapshot
  modules/
    brightness_detection/
      __init__.py
      module.py                   # BrightnessDetectionModule
      analyzer.py                 # SlotAnalyzer (brightness-only, adapted from v1)
      status_widget.py            # Per-slot state display panel
      settings_widget.py          # Threshold + calibration settings
  tests/
    ... (Phase 1 + 2 tests unchanged)
    test_slot_models.py           # SlotState, SlotConfig, SlotSnapshot
    test_analyzer.py              # SlotAnalyzer unit tests
    test_brightness_module.py     # Module registration, service, lifecycle
```

---

## 1. Slot Models (`src/models/slot.py`)

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class SlotState(Enum):
    READY = "ready"
    ON_COOLDOWN = "on_cooldown"
    CASTING = "casting"
    CHANNELING = "channeling"
    LOCKED = "locked"         # Reserved for future: cast bar says "don't fire"
    GCD = "gcd"               # Brief cooldown confirmation period
    UNKNOWN = "unknown"       # No baseline calibrated


@dataclass
class SlotConfig:
    """Static pixel layout for one slot within the capture region."""
    index: int
    x_offset: int = 0      # Pixels from left edge of captured frame
    y_offset: int = 0      # Pixels from top edge of captured frame
    width: int = 40
    height: int = 40


@dataclass
class SlotSnapshot:
    """Analyzed state of one slot at a point in time."""
    index: int
    state: SlotState = SlotState.UNKNOWN
    darkened_fraction: float = 0.0   # Fraction of pixels darker than baseline
    changed_fraction: float = 0.0    # Fraction of pixels changed from baseline (absolute)
    timestamp: float = 0.0

    @property
    def is_ready(self) -> bool:
        return self.state == SlotState.READY

    @property
    def is_on_cooldown(self) -> bool:
        return self.state == SlotState.ON_COOLDOWN

    @property
    def is_casting(self) -> bool:
        return self.state in (SlotState.CASTING, SlotState.CHANNELING)
```

Update `src/models/__init__.py`:
```python
from .geometry import BoundingBox
from .slot import SlotState, SlotConfig, SlotSnapshot
```

**Note:** This SlotSnapshot is leaner than v1's — no glow fields, no cast timing fields. Those will be added by the glow and cast bar modules in future phases, or the snapshot can be extended then. Keep it minimal for now.

---

## 2. SlotAnalyzer (`modules/brightness_detection/analyzer.py`)

This is the brightness-only extraction from v1's `/v1/src/analysis/slot_analyzer.py`. Port the logic, clean up the interface, remove all glow/buff/cast-bar-ROI code.

```python
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from src.models import SlotState, SlotConfig, SlotSnapshot

logger = logging.getLogger(__name__)


@dataclass
class _SlotRuntime:
    """Per-slot temporal memory for state transitions."""
    state: SlotState = SlotState.UNKNOWN
    cooldown_candidate_started_at: Optional[float] = None
    cast_candidate_frames: int = 0
    cast_started_at: Optional[float] = None
    cast_ends_at: Optional[float] = None
    last_darkened_fraction: float = 0.0


class SlotAnalyzer:
    """Analyzes per-slot brightness to detect cooldown states.
    
    Adapted from v1 SlotAnalyzer — brightness detection only.
    Glow, buff, and cast-bar ROI detection belong to other modules.
    """
    
    def __init__(self):
        self._slot_configs: list[SlotConfig] = []
        self._baselines: dict[int, np.ndarray] = {}   # slot_index -> grayscale baseline
        self._runtime: dict[int, _SlotRuntime] = {}
        self._frame_count: int = 0
        
        # Config values (set via update_config)
        self._slot_count: int = 10
        self._slot_gap: int = 2
        self._slot_padding: int = 3
        self._bbox_width: int = 400
        self._bbox_height: int = 50
        self._darken_threshold: int = 40
        self._trigger_fraction: float = 0.30
        self._change_fraction: float = 0.30
        self._change_ignore_slots: set[int] = set()
        self._detection_region: str = "top_left"  # "full" or "top_left"
        self._detection_region_overrides: dict[int, str] = {}
        self._cooldown_min_ms: int = 2000
        self._release_factor: float = 0.5  # Hysteresis: release at 50% of trigger
        
        # Cast candidate detection (brightness-based)
        self._cast_detection_enabled: bool = True
        self._cast_min_fraction: float = 0.05
        self._cast_max_fraction: float = 0.22
        self._cast_confirm_frames: int = 2
        self._cast_min_ms: int = 150
        self._cast_max_ms: int = 3000
        self._cast_cancel_grace_ms: int = 120
        self._channeling_enabled: bool = True
        
        self._recompute_layout()
    
    def update_config(self, cfg: dict) -> None:
        """
        Update analyzer from the module's config dict.
        
        Expected keys:
        - From core_capture config: bbox_width, bbox_height, slot_count, slot_gap, slot_padding
        - From brightness_detection config: darken_threshold, trigger_fraction, change_fraction,
          detection_region, cooldown_min_ms, cast_detection_enabled, cast_* thresholds
        
        Clears baselines if slot layout changed.
        """
        layout_changed = (
            cfg.get("slot_count", self._slot_count) != self._slot_count
            or cfg.get("slot_gap", self._slot_gap) != self._slot_gap
            or cfg.get("slot_padding", self._slot_padding) != self._slot_padding
            or cfg.get("bbox_width", self._bbox_width) != self._bbox_width
            or cfg.get("bbox_height", self._bbox_height) != self._bbox_height
        )
        
        self._slot_count = int(cfg.get("slot_count", self._slot_count))
        self._slot_gap = int(cfg.get("slot_gap", self._slot_gap))
        self._slot_padding = int(cfg.get("slot_padding", self._slot_padding))
        self._bbox_width = int(cfg.get("bbox_width", self._bbox_width))
        self._bbox_height = int(cfg.get("bbox_height", self._bbox_height))
        self._darken_threshold = int(cfg.get("darken_threshold", self._darken_threshold))
        self._trigger_fraction = float(cfg.get("trigger_fraction", self._trigger_fraction))
        self._change_fraction = float(cfg.get("change_fraction", self._change_fraction))
        self._change_ignore_slots = set(cfg.get("change_ignore_slots", []))
        self._detection_region = str(cfg.get("detection_region", self._detection_region))
        self._detection_region_overrides = dict(cfg.get("detection_region_overrides", {}))
        self._cooldown_min_ms = int(cfg.get("cooldown_min_ms", self._cooldown_min_ms))
        self._cast_detection_enabled = bool(cfg.get("cast_detection_enabled", True))
        self._cast_min_fraction = float(cfg.get("cast_min_fraction", self._cast_min_fraction))
        self._cast_max_fraction = float(cfg.get("cast_max_fraction", self._cast_max_fraction))
        self._cast_confirm_frames = int(cfg.get("cast_confirm_frames", self._cast_confirm_frames))
        self._cast_min_ms = int(cfg.get("cast_min_ms", self._cast_min_ms))
        self._cast_max_ms = int(cfg.get("cast_max_ms", self._cast_max_ms))
        self._cast_cancel_grace_ms = int(cfg.get("cast_cancel_grace_ms", self._cast_cancel_grace_ms))
        self._channeling_enabled = bool(cfg.get("channeling_enabled", True))
        
        self._recompute_layout()
        if layout_changed:
            self._baselines.clear()
            self._runtime = {i: _SlotRuntime() for i in range(self._slot_count)}
            logger.info("Layout changed — baselines cleared, recalibrate required")
    
    def _recompute_layout(self) -> None:
        """Calculate pixel regions for each slot.
        
        Port from v1 _recompute_slot_layout. Same math:
        slot_w = (total_width - (count-1)*gap) // count
        """
        # Port from v1: /v1/src/analysis/slot_analyzer.py lines 100-123
    
    # --- Cropping ---
    
    def crop_slot(self, frame: np.ndarray, slot: SlotConfig) -> np.ndarray:
        """Extract a single slot's padded image from frame.
        
        Port from v1: /v1/src/analysis/slot_analyzer.py lines 149-164
        Note: action_origin is (0,0) because frame IS the capture region.
        """
    
    @staticmethod
    def _get_brightness_channel(bgr_crop: np.ndarray) -> np.ndarray:
        """BGR → grayscale uint8 array.
        
        Port from v1: /v1/src/analysis/slot_analyzer.py lines 174-178
        """
    
    # --- Calibration ---
    
    def calibrate_baselines(self, frame: np.ndarray) -> None:
        """Calibrate all slot baselines from a single frame. 
        Call when all abilities are off cooldown.
        
        Port from v1: /v1/src/analysis/slot_analyzer.py lines 241-257
        Stores grayscale baseline per slot.
        """
    
    def calibrate_single_slot(self, frame: np.ndarray, slot_index: int) -> None:
        """Recalibrate one slot's baseline.
        
        Port from v1: /v1/src/analysis/slot_analyzer.py lines 259-274
        """
    
    def get_baselines(self) -> dict[int, np.ndarray]:
        """Return current baselines."""
        return dict(self._baselines)
    
    def set_baselines(self, baselines: dict[int, np.ndarray]) -> None:
        """Restore baselines (e.g., from saved config)."""
        self._baselines = dict(baselines)
    
    @property
    def has_baselines(self) -> bool:
        return len(self._baselines) > 0
    
    # --- Analysis ---
    
    def analyze_frame(self, frame: np.ndarray, cast_gate_active: bool = True) -> list[SlotSnapshot]:
        """
        Analyze all slots in a frame and return per-slot snapshots.
        
        Args:
            frame: BGR numpy array of the captured region.
            cast_gate_active: Whether the cast bar gate allows entering CASTING state.
                              If False, intermediate darkened fractions stay READY.
                              This is provided by the cast_bar module when it exists.
                              Default True = no gating (same as v1 without cast bar ROI).
        
        Returns:
            List of SlotSnapshot, one per slot.
        
        Algorithm per slot (port from v1 analyze_frame, lines 808-960):
        1. Crop slot from frame
        2. Get baseline for this slot (if None → UNKNOWN)
        3. Apply detection region (top_left quadrant or full)
        4. Compute darkened_fraction (pixels where brightness dropped > threshold)
        5. Compute changed_fraction (pixels where absolute brightness change > threshold)
        6. Apply cooldown logic:
           a. raw_cooldown = darkened_fraction >= trigger OR changed_fraction >= change_fraction
           b. Hysteresis: if currently ON_COOLDOWN, use lower release threshold
           c. Cooldown min duration: if cooldown just started, enter GCD state temporarily
        7. Apply cast logic (if cast_detection_enabled):
           a. If darkened_fraction is in [cast_min_fraction, cast_max_fraction] range,
              and cast_gate_active, count confirm frames → enter CASTING
           b. CASTING → CHANNELING after cast_max_ms
           c. Exit CASTING if fraction leaves range (with grace period)
        8. Return SlotSnapshot with state and fractions
        """
    
    def _determine_slot_state(
        self, slot_index: int, darkened_fraction: float, changed_fraction: float,
        is_raw_cooldown: bool, now: float, cast_gate_active: bool,
    ) -> SlotState:
        """
        State machine for one slot. Handles cooldown min duration, cast detection,
        channeling, and state transitions.
        
        Ports the combined logic of v1's cooldown hysteresis (lines 862-901)
        and _next_state_with_cast_logic (lines 607-754).
        """
```

**Key differences from v1:**
- No `AppConfig` dependency — takes a flat dict via `update_config()`
- No glow fields in `_SlotRuntime`
- No `_cast_bar_active()` method — cast gating is an input parameter (`cast_gate_active`)
- No buff analysis
- `action_origin` is always `(0,0)` because the frame IS the capture region
- `crop_slot` uses `(0,0)` origin instead of the v1 `_frame_action_origin_x/y`

---

## 3. BrightnessDetectionModule (`modules/brightness_detection/module.py`)

```python
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from src.core.base_module import BaseModule
import numpy as np


class BrightnessDetectionModule(QObject, BaseModule):
    """Brightness-based cooldown detection.
    
    Receives frames from core_capture, analyzes per-slot brightness 
    against baselines, publishes slot states.
    """
    # Need combined QObject + BaseModule metaclass for Qt signals
    # (same pattern as v1's CooldownRotationModule)
    
    name = "Brightness Detection"
    key = "brightness_detection"
    version = "1.0.0"
    description = "Detects slot cooldown states by comparing brightness to calibrated baselines"
    requires = ["core_capture"]
    optional = ["cast_bar"]     # If loaded, reads cast_gate_active from it
    provides_services = ["slot_states", "baselines_calibrated"]
    hooks = ["slot_states_updated"]
    
    # Signals (thread-safe bridge from on_frame worker thread to GUI)
    slot_states_updated_signal = pyqtSignal(list)  # list[dict] per-slot state
    
    def __init__(self):
        QObject.__init__(self)
        BaseModule.__init__(self)
        self._analyzer = None
        self._latest_states: list[dict] = []
    
    def setup(self, core):
        super().setup(core)
        from modules.brightness_detection.analyzer import SlotAnalyzer
        
        # Ensure default config
        cfg = core.get_config(self.key)
        if not cfg:
            core.save_config(self.key, self._default_config())
        
        # Create analyzer
        self._analyzer = SlotAnalyzer()
        self._sync_config_to_analyzer()
        
        # Register slot status panel
        core.panels.register(
            id=f"{self.key}/slot_status",
            area="primary",
            factory=self._build_status_widget,
            title="Slot States",
            owner=self.key,
            order=10,  # After preview (0) and controls (1)
        )
        
        # Register settings under detection tab
        core.settings.register(
            path="detection/brightness",
            factory=self._build_settings,
            title="Brightness Detection",
            owner=self.key,
            order=30,
        )
        
        core.settings.register(
            path="detection/calibration",
            factory=self._build_calibration_settings,
            title="Calibration",
            owner=self.key,
            order=40,
        )
    
    def ready(self):
        """Load saved baselines from config."""
        cfg = self.core.get_config(self.key)
        saved = cfg.get("slot_baselines")
        if saved and self._analyzer:
            try:
                decoded = self._decode_baselines(saved)
                if decoded:
                    self._analyzer.set_baselines(decoded)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Could not load baselines: %s", e)
    
    def on_frame(self, frame: np.ndarray) -> None:
        """Called from capture worker thread. Analyze frame, emit results via signal."""
        if self._analyzer is None:
            return
        
        # Optionally read cast gate from cast_bar module
        cast_gate = True
        if self.core.is_loaded("cast_bar"):
            gate = self.core.get_service("cast_bar", "cast_gate_active")
            if gate is not None:
                cast_gate = bool(gate)
        
        snapshots = self._analyzer.analyze_frame(frame, cast_gate_active=cast_gate)
        
        # Convert to dicts for signal (QueuedConnection needs serializable types)
        states = []
        for s in snapshots:
            states.append({
                "index": s.index,
                "state": s.state.value,
                "darkened_fraction": s.darkened_fraction,
                "changed_fraction": s.changed_fraction,
                "timestamp": s.timestamp,
            })
        
        self._latest_states = states
        self.slot_states_updated_signal.emit(states)
        self.core.emit(f"{self.key}.slot_states_updated", states=states)
    
    def get_service(self, name):
        if name == "slot_states":
            return self._latest_states
        if name == "baselines_calibrated":
            return self._analyzer.has_baselines if self._analyzer else False
        return None
    
    def on_config_changed(self, key, value):
        self._sync_config_to_analyzer()
    
    def _sync_config_to_analyzer(self):
        """Merge core_capture layout + own thresholds into analyzer config."""
        if not self._analyzer or not self.core:
            return
        cc_cfg = self.core.get_config("core_capture")
        bd_cfg = self.core.get_config(self.key)
        bb = cc_cfg.get("bounding_box", {})
        slots = cc_cfg.get("slots", {})
        merged = {
            "bbox_width": bb.get("width", 400),
            "bbox_height": bb.get("height", 50),
            "slot_count": slots.get("count", 10),
            "slot_gap": slots.get("gap", 2),
            "slot_padding": slots.get("padding", 3),
            **bd_cfg,  # brightness_detection config overrides
        }
        self._analyzer.update_config(merged)
    
    def _default_config(self) -> dict:
        return {
            "darken_threshold": 40,
            "trigger_fraction": 0.30,
            "change_fraction": 0.30,
            "change_ignore_slots": [],
            "detection_region": "top_left",
            "detection_region_overrides": {},
            "cooldown_min_ms": 2000,
            "cast_detection_enabled": True,
            "cast_min_fraction": 0.05,
            "cast_max_fraction": 0.22,
            "cast_confirm_frames": 2,
            "cast_min_ms": 150,
            "cast_max_ms": 3000,
            "cast_cancel_grace_ms": 120,
            "channeling_enabled": True,
            "slot_baselines": [],
            "slot_display_names": [],
        }
    
    # --- Calibration ---
    
    def calibrate_all_baselines(self) -> tuple[bool, str]:
        """Calibrate all slot baselines from a fresh capture."""
        if not self._analyzer:
            return False, "Analyzer not initialized"
        capture_mod = self.core.get_module("core_capture")
        if not capture_mod or not self.core.get_service("core_capture", "capture_running"):
            return False, "Capture not running"
        
        # Grab a single frame directly
        from src.capture.screen_capture import ScreenCapture
        from src.models import BoundingBox
        
        cc_cfg = self.core.get_config("core_capture")
        capture = ScreenCapture(monitor_index=int(cc_cfg.get("monitor_index", 1)))
        capture.start()
        try:
            bbox = BoundingBox.from_dict(cc_cfg.get("bounding_box", {}))
            frame = capture.grab_region(bbox)
            self._analyzer.calibrate_baselines(frame)
            self._save_baselines()
            return True, "Calibrated ✓"
        except Exception as e:
            return False, str(e)
        finally:
            capture.stop()
    
    def calibrate_single_slot(self, slot_index: int) -> tuple[bool, str]:
        """Calibrate one slot's baseline."""
        if not self._analyzer:
            return False, "Analyzer not initialized"
        
        from src.capture.screen_capture import ScreenCapture
        from src.models import BoundingBox
        
        cc_cfg = self.core.get_config("core_capture")
        capture = ScreenCapture(monitor_index=int(cc_cfg.get("monitor_index", 1)))
        capture.start()
        try:
            bbox = BoundingBox.from_dict(cc_cfg.get("bounding_box", {}))
            frame = capture.grab_region(bbox)
            self._analyzer.calibrate_single_slot(frame, slot_index)
            self._save_baselines()
            return True, f"Slot {slot_index} calibrated ✓"
        except Exception as e:
            return False, str(e)
        finally:
            capture.stop()
    
    def _save_baselines(self):
        """Encode baselines and persist to config."""
        if not self._analyzer:
            return
        encoded = self._encode_baselines(self._analyzer.get_baselines())
        cfg = self.core.get_config(self.key)
        cfg["slot_baselines"] = encoded
        self.core.save_config(self.key, cfg)
    
    @staticmethod
    def _encode_baselines(baselines: dict[int, np.ndarray]) -> list[dict]:
        """Encode numpy baselines for JSON storage.
        Port from v1 encode_baselines in main.py.
        Each baseline → {"index": i, "data": base64_string, "shape": [h, w]}
        """
        import base64
        result = []
        for idx, arr in baselines.items():
            b64 = base64.b64encode(arr.tobytes()).decode("ascii")
            result.append({"index": idx, "data": b64, "shape": list(arr.shape)})
        return result
    
    @staticmethod
    def _decode_baselines(data: list[dict]) -> dict[int, np.ndarray]:
        """Decode baselines from JSON config.
        Port from v1 decode_baselines in main.py.
        """
        import base64
        result = {}
        for item in data:
            idx = int(item["index"])
            shape = tuple(item["shape"])
            arr = np.frombuffer(base64.b64decode(item["data"]), dtype=np.uint8).reshape(shape)
            result[idx] = arr
        return result
    
    # --- Widget builders ---
    
    def _build_status_widget(self):
        from modules.brightness_detection.status_widget import SlotStatusWidget
        widget = SlotStatusWidget(self.core, self.key)
        self.slot_states_updated_signal.connect(
            widget.update_states, Qt.ConnectionType.QueuedConnection
        )
        return widget
    
    def _build_settings(self):
        from modules.brightness_detection.settings_widget import BrightnessSettings
        return BrightnessSettings(self.core, self.key)
    
    def _build_calibration_settings(self):
        from modules.brightness_detection.settings_widget import CalibrationSettings
        return CalibrationSettings(self.core, self.key, self)
```

**Note on QObject + BaseModule metaclass:** Both QObject (for signals) and ABC use metaclasses. You need a combined metaclass. V1 solved this — check how `CooldownRotationModule` in `/v1/modules/cooldown_rotation/module.py` handles it. The simplest approach:

```python
from abc import ABCMeta
from PyQt6.QtCore import QObject

class CombinedMeta(type(QObject), ABCMeta):
    pass

class BrightnessDetectionModule(QObject, BaseModule, metaclass=CombinedMeta):
    ...
```

---

## 4. Slot Status Widget (`modules/brightness_detection/status_widget.py`)

Shows per-slot states as a horizontal row of colored indicators (like v1's slot buttons). Reference `/v1/modules/cooldown_rotation/status_widget.py` for styling.

```python
class SlotStatusWidget(QWidget):
    """Horizontal row of slot state indicators."""
    
    def __init__(self, core, module_key, parent=None):
        super().__init__(parent)
        self._core = core
        self._key = module_key
        self._slot_buttons: list[QPushButton] = []
        self._build_ui()
    
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        
        # Read slot count from core_capture config
        cc_cfg = self._core.get_config("core_capture")
        slot_count = cc_cfg.get("slots", {}).get("count", 10)
        
        for i in range(slot_count):
            btn = QPushButton(f"{i}")
            btn.setFixedSize(32, 32)
            btn.setFlat(True)
            btn.setStyleSheet(self._style_for_state("unknown"))
            self._slot_buttons.append(btn)
            layout.addWidget(btn)
        
        layout.addStretch()
    
    def update_states(self, states: list[dict]) -> None:
        """Slot: receives per-slot state dicts from module signal."""
        for state_dict in states:
            idx = state_dict.get("index", -1)
            if 0 <= idx < len(self._slot_buttons):
                slot_state = state_dict.get("state", "unknown")
                btn = self._slot_buttons[idx]
                btn.setStyleSheet(self._style_for_state(slot_state))
                # Tooltip: show darkened fraction
                frac = state_dict.get("darkened_fraction", 0)
                btn.setToolTip(f"Slot {idx}: {slot_state}\nDarkened: {frac:.1%}")
    
    def _style_for_state(self, state: str) -> str:
        """Return QSS for a slot button based on state."""
        colors = {
            "ready": "#22bb44",       # Green
            "on_cooldown": "#cc3333", # Red
            "casting": "#ee8822",     # Orange
            "channeling": "#dd7711",  # Darker orange
            "gcd": "#ddbb33",         # Yellow
            "locked": "#888888",      # Gray
            "unknown": "#444455",     # Dark gray
        }
        color = colors.get(state, "#444455")
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                font-family: monospace;
            }}
        """
```

---

## 5. Settings Widgets (`modules/brightness_detection/settings_widget.py`)

Two widget classes:

### BrightnessSettings

Thresholds and detection parameters. Goes under `detection/brightness`.

```python
class BrightnessSettings(QWidget):
    """Brightness detection threshold settings."""
    
    def __init__(self, core, module_key, parent=None):
        # Fields:
        # - Enable brightness detection (QCheckBox) → controls module.enabled
        # - Darken Threshold (QSpinBox, 1-255, default 40)
        #     "Pixel counts as darkened if brightness dropped by this much"
        # - Trigger Fraction (QDoubleSpinBox, 0.01-1.0, default 0.30)
        #     "Slot is ON_COOLDOWN when this fraction of pixels are darkened"
        # - Change Fraction (QDoubleSpinBox, 0.01-1.0, default 0.30)
        #     "Slot is ON_COOLDOWN when this fraction of pixels changed (absolute)"
        # - Detection Region (QComboBox: "Top-Left Quadrant", "Full Slot")
        #     "Which part of each slot to analyze"
        # - Cooldown Min Duration (QSpinBox, 0-10000 ms, default 2000)
        #     "Minimum time before a cooldown is confirmed (filters GCD flicker)"
        # 
        # Cast Detection group:
        # - Enable Cast Detection (QCheckBox)
        # - Cast Min Fraction (QDoubleSpinBox)
        # - Cast Max Fraction (QDoubleSpinBox)
        # - Cast Confirm Frames (QSpinBox)
        # - Cast Min Duration (QSpinBox, ms)
        # - Cast Max Duration (QSpinBox, ms)
        # - Cancel Grace Period (QSpinBox, ms)
        # - Enable Channeling (QCheckBox)
```

### CalibrationSettings

Calibrate button + per-slot calibration. Goes under `detection/calibration`.

```python
class CalibrationSettings(QWidget):
    """Baseline calibration controls."""
    
    def __init__(self, core, module_key, module_ref, parent=None):
        # module_ref = BrightnessDetectionModule instance (for calling calibrate methods)
        
        # "Calibrate All Baselines" button
        #   Click → module_ref.calibrate_all_baselines()
        #   Shows success/failure message
        #
        # Per-slot row: one small "Recalibrate" button per slot
        #   Click → module_ref.calibrate_single_slot(i)
        #
        # Status label showing "Baselines: calibrated (10/10 slots)" or "Not calibrated"
```

---

## 6. Update Default Config

In `config/default_config.json`, add brightness_detection and enable it:

```json
{
  "app": {
    "modules_enabled": ["core_capture", "brightness_detection", "demo"],
    "window_geometry": {}
  },
  "core_capture": { ... },
  "brightness_detection": {
    "darken_threshold": 40,
    "trigger_fraction": 0.30,
    "change_fraction": 0.30,
    "change_ignore_slots": [],
    "detection_region": "top_left",
    "detection_region_overrides": {},
    "cooldown_min_ms": 2000,
    "cast_detection_enabled": true,
    "cast_min_fraction": 0.05,
    "cast_max_fraction": 0.22,
    "cast_confirm_frames": 2,
    "cast_min_ms": 150,
    "cast_max_ms": 3000,
    "cast_cancel_grace_ms": 120,
    "channeling_enabled": true,
    "slot_baselines": [],
    "slot_display_names": []
  },
  "demo": { "message": "Hello from demo module" }
}
```

---

## 7. Config Change Propagation

When settings change in either core_capture (slot layout) or brightness_detection (thresholds), the analyzer needs to update. Wire this:

- In `BrightnessDetectionModule.setup()`, subscribe to core_capture config changes:

```python
core.subscribe("config.core_capture.changed", lambda **kw: self._sync_config_to_analyzer())
```

- When brightness_detection settings save, call `_sync_config_to_analyzer()` directly.

**Note:** The hook system doesn't currently have a per-namespace config change hook. For now, have the settings widgets call a refresh method on the module after saving. A proper `config.{namespace}.changed` hook can be added later if needed.

A simpler approach: the settings widget calls `module._sync_config_to_analyzer()` after every save. Since the settings widget has access to `core`, it can also call `core.get_module("brightness_detection")` to get the module reference. Or the settings widget can accept a callback.

---

## 8. Tests

### `tests/test_slot_models.py`

```python
# Test: SlotState enum values
# Test: SlotConfig defaults
# Test: SlotSnapshot.is_ready, is_on_cooldown, is_casting properties
# Test: SlotSnapshot default state is UNKNOWN
```

### `tests/test_analyzer.py`

This is the most important test file — it validates the core detection logic.

```python
# Setup: create a SlotAnalyzer, configure with known layout

# --- Layout ---
# Test: _recompute_layout creates correct SlotConfigs for 10 slots
# Test: layout with different gap/padding values
# Test: layout change clears baselines

# --- Cropping ---
# Test: crop_slot extracts correct region from a synthetic frame
# Test: crop_slot with padding insets correctly

# --- Brightness ---
# Test: _get_brightness_channel returns grayscale
# Test: identical frame to baseline → darkened_fraction ≈ 0
# Test: fully darkened frame → darkened_fraction ≈ 1.0

# --- Calibration ---
# Test: calibrate_baselines stores one baseline per slot
# Test: calibrate_single_slot updates only that slot
# Test: has_baselines returns True after calibration
# Test: set_baselines / get_baselines roundtrip

# --- State determination ---
# Test: no baseline → UNKNOWN
# Test: frame matching baseline → READY (darkened_fraction < threshold)
# Test: darkened frame → ON_COOLDOWN (darkened_fraction >= threshold)
# Test: intermediate fraction → CASTING (if cast detection enabled)
# Test: cooldown min duration → GCD before confirming ON_COOLDOWN
# Test: hysteresis: ON_COOLDOWN slot needs lower fraction to release to READY
# Test: cast_gate_active=False suppresses CASTING state
# Test: channeling: CASTING transitions to CHANNELING after max duration
# Test: detection_region "top_left" uses only top-left quadrant

# Use synthetic numpy frames:
#   - "ready" frame: same as baseline
#   - "cooldown" frame: darken all pixels by threshold+10
#   - "casting" frame: darken by amount in cast range
#   - "partial" frame: darken only half the pixels
```

### `tests/test_brightness_module.py`

```python
# Test: setup registers panels and settings
# Test: default config created if missing
# Test: get_service("slot_states") returns latest states
# Test: get_service("baselines_calibrated") returns False initially
# Test: _encode_baselines / _decode_baselines roundtrip
# Test: _sync_config_to_analyzer merges core_capture + brightness configs
# Test: on_frame with a synthetic frame updates _latest_states
```

---

## Verification

With all three modules loaded (core_capture, brightness_detection, demo):

1. Start capture → preview shows live screen grab
2. "SLOT STATES" panel appears below capture controls with 10 gray (UNKNOWN) indicators
3. Open Settings → Detection tab now has subtabs: Display, Capture Region, Slot Layout, Brightness Detection, Calibration
4. Click "Calibrate All Baselines" in Calibration settings (with abilities off cooldown in game)
5. Slot indicators change from gray (UNKNOWN) to green (READY)
6. Use an ability in game → that slot turns red (ON_COOLDOWN)
7. Ability comes off cooldown → slot returns to green (READY)
8. Cast a spell → slot briefly turns orange (CASTING)
9. Adjust darken threshold slider → detection sensitivity changes live
10. Switch detection region to "Full Slot" → behavior changes accordingly
11. All tests pass: `cd v2 && pytest`

---

## What This Phase Does NOT Include

- No glow detection (Phase 5+: separate module, ring mask, saturation analysis)
- No cast bar ROI detection (Phase 5+: separate module, motion analysis on cast bar region)
- No buff tracking (Phase 5+: separate module, template matching)
- No automation / key sending (Phase 4)
- No priority lists or keybinds (Phase 4)
- No overlay rendering of slot states (future: brightness module can extend overlay via hooks)

The brightness detection module sees. The automation module (Phase 4) acts on what it sees.
