# Phase 2 Changelog — Capture, Preview, Overlay + Tests

Everything built and refined after Phase 1 (the shell).

---

## Phase 2 Core Implementation

### New Packages & Files

```
v2/
  src/
    models/
      __init__.py
      geometry.py                 # BoundingBox dataclass
    capture/
      __init__.py
      screen_capture.py           # mss-based screen capture (copied from v1)
  modules/
    core_capture/
      __init__.py
      module.py                   # CoreCaptureModule
      capture_worker.py           # QThread frame grabbing loop
      preview_widget.py           # Live preview QLabel
      settings_widget.py          # Settings sub-widgets (3 classes)
      overlay.py                  # Transparent click-through overlay
  tests/
    __init__.py
    pytest.ini
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

### Modified Phase 1 Files

- **`src/core/base_module.py`** — Added `on_frame(frame: np.ndarray)` method for per-frame processing.
- **`src/core/module_manager.py`** — Added `process_frame(frame)` to call `on_frame` on all enabled modules.
- **`src/main.py`** — Added `core._module_manager = module_manager` bridge; added shutdown logic to stop capture before closing windows.
- **`config/default_config.json`** — Added `core_capture` defaults and enabled it in `modules_enabled`.

### What Was Built

1. **BoundingBox model** — Dataclass with `as_mss_region()`, `to_dict()`, `from_dict()`.
2. **ScreenCapture** — `mss` wrapper for grabbing screen regions. Copied from v1.
3. **CaptureWorker** — QThread that grabs frames at configurable FPS, emits `frame_captured` signal for the preview, and calls `module_manager.process_frame()` to distribute frames to all modules.
4. **PreviewWidget** — QLabel that receives QImage via QueuedConnection and displays scaled preview.
5. **CaptureOverlay** — Frameless, transparent, always-on-top, click-through window. Draws green bounding box and magenta slot outlines via QPainter.
6. **CoreCaptureModule** — Registers preview panel, controls panel, three settings subtabs under Detection, and the overlay window. Provides `capture_running`, `bounding_box`, `monitor_info` services.
7. **56 unit tests** across all Phase 1 managers and Phase 2 components.

---

## Post-Implementation Refinements

### Settings Moved to Detection Tab with Subtabs

All `core_capture` settings were moved from the "General" tab into the **Detection** tab as subtabs:

| Subtab | Widget Class | Path | Order |
|---|---|---|---|
| Display | `DisplayOverlaySettings` | `detection/display` | 0 |
| Capture Region | `CaptureRegionSettings` | `detection/capture_region` | 10 |
| Slot Layout | `SlotLayoutSettings` | `detection/slot_layout` | 20 |

This was the first real use of the settings subtab system built in Phase 1.

### Settings Widget Split into 3 Classes

The original monolithic `CoreCaptureSettings` was replaced by three focused widget classes, each with `_SaveMixin` for shared config read/write logic:

- **`CaptureRegionSettings`** — Top, Left, Width, Height in a 2x2 grid + Poll FPS below.
- **`SlotLayoutSettings`** — Count, Gap, Padding in a horizontal row.
- **`DisplayOverlaySettings`** — Monitor dropdown, Always on Top checkbox (inline), Show Capture Overlay checkbox, Show Active Screen Outline checkbox.

### Layout Polish

- **Side-by-side inputs**: Bounding box fields arranged in a 2-column `QGridLayout` (Top/Left on row 1, Width/Height on row 2, Poll FPS on row 3) instead of stacked vertically.
- **`_capped_row()` helper**: Wraps any layout in a max-width container so inputs don't spread too far on wide panels.
- **Vertical alignment**: All labels in `CaptureRegionSettings` use a consistent fixed width (`LW = 55`) so input fields align vertically across rows.
- **`_field_pair()` helper**: Packs a label + spinbox into a tight `QHBoxLayout` for use in horizontal arrangements (used by `SlotLayoutSettings`).
- **`_spin()` and `_label()` helpers**: Shared factory functions with consistent styling, min/max widths, and right-aligned labels.

### Display Subtab Ordering & Naming

- **Renamed** from "Display & Overlay" → **"Display"**.
- **Moved to order 0** so it appears first under Detection.
- **Always on Top** checkbox placed inline on the same row as the Monitor dropdown.

### Monitor & Poll FPS Placement

- **Monitor dropdown**: Lives in the Display subtab (with the overlay/display toggles).
- **Poll FPS**: Lives in the Capture Region subtab (with the bounding box coordinates).

### Overlay ↔ Windows Menu Sync

The "Show capture overlay" checkbox in Display settings and the "Capture Overlay" toggle in the Windows dropdown menu are now kept in sync bidirectionally.

**Infrastructure added:**

- **`WindowManager.on_visibility_changed(callback)`** — Registers a `callback(window_id, visible)` that fires after every `show()` or `hide()` call.
- **`WindowManager._notify_visibility()`** — Iterates registered callbacks on show/hide.
- **`Core._on_window_visibility_changed()`** — Bridges WindowManager callbacks into the hook system, emitting `"window.visibility_changed"` with `window_id` and `visible` kwargs.

**Settings widget wiring:**

- Checkbox toggled → saves config AND calls `core.windows.show/hide` to actually show/hide the overlay.
- Windows menu toggled → `window.visibility_changed` hook fires → checkbox updated (with `blockSignals` to prevent loops) → config synced.

### Files Changed (Post Phase 2 Core)

| File | What Changed |
|---|---|
| `src/core/window_manager.py` | Added `_visibility_callbacks`, `on_visibility_changed()`, `_notify_visibility()`. Show/hide call `_notify_visibility`. |
| `src/core/core.py` | Wires `windows.on_visibility_changed` → emits `"window.visibility_changed"` hook. |
| `modules/core_capture/module.py` | Settings registrations restructured (3 subtabs under `detection/`). Display moved to order 0. Title changes. |
| `modules/core_capture/settings_widget.py` | Split into 3 classes. Layout helpers added. Overlay checkbox syncs with WindowManager via hooks. |
| `tests/test_settings_manager.py` | Updated to reflect `detection/` subtab paths. |
| `tests/test_core_capture_module.py` | Updated to reflect `detection/display` path. |

---

## Current Settings Structure (core_capture)

```json
{
  "core_capture": {
    "monitor_index": 1,
    "polling_fps": 20,
    "bounding_box": { "top": 900, "left": 500, "width": 400, "height": 50 },
    "slots": { "count": 10, "gap": 2, "padding": 3 },
    "overlay": { "enabled": false, "show_active_screen_outline": false },
    "display": { "always_on_top": false }
  }
}
```

## Test Status

56 tests passing across:
- `test_config_manager.py`
- `test_panel_manager.py`
- `test_settings_manager.py`
- `test_window_manager.py`
- `test_module_manager.py`
- `test_bounding_box.py`
- `test_capture_worker.py`
- `test_core_capture_module.py`
