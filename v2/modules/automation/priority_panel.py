"""Priority list sidebar panel — drag-and-drop reorderable items."""
from __future__ import annotations

import logging
from typing import Any, Optional

from PyQt6.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.automation.priority_rules import normalize_activation_rule

logger = logging.getLogger(__name__)

MIME_PRIORITY_ITEM = "application/x-priority-item"
DRAG_THRESHOLD_PX = 5

_STATE_COLORS = {
    "ready": "#88ff88",
    "on_cooldown": "#ff6666",
    "casting": "#a0c7ff",
    "channeling": "#ffd37a",
    "gcd": "#ffaa44",
    "locked": "#cccccc",
    "unknown": "#666666",
}


class PriorityItemWidget(QFrame):
    """One row in the priority list. Shows [key] name. Draggable."""

    def __init__(
        self,
        item_data: dict,
        rank: int,
        keybind: str,
        display_name: str,
        core: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item_data = item_data
        self._rank = rank
        self._keybind = keybind or "?"
        self._display_name = display_name or "Unidentified"
        self._core = core
        self._state = "unknown"
        self._drag_start: QPoint | None = None

        self.setObjectName("priorityItem")
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "#priorityItem { background: #2a2a2a; border: 1px solid #3a3a3a;"
            " border-radius: 3px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        self._key_label = QLabel(f"[{self._keybind.lower()}]")
        self._key_label.setStyleSheet("color: #aaa; font-family: monospace; font-size: 11px;")
        self._key_label.setFixedWidth(40)
        self._key_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._key_label)

        self._name_label = QLabel(self._display_name)
        self._name_label.setStyleSheet("color: #ccc; font-size: 11px;")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._name_label, 1)

        rule_id = normalize_activation_rule(item_data.get("activation_rule"))
        rule_text = self._get_rule_display(rule_id)
        self._rule_label = QLabel(rule_text)
        self._rule_label.setStyleSheet("font-family: monospace; font-size: 9px; color: #d3a75b;")
        self._rule_label.setFixedWidth(40)
        self._rule_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._rule_label)

        self._state_dot = QLabel("\u25CF")
        self._state_dot.setFixedWidth(14)
        self._state_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._state_dot)

        self.update_state("unknown")

    def _get_rule_display(self, rule_id: str) -> str:
        if rule_id == "always":
            return ""
        if self._core and hasattr(self._core, "activation_rules"):
            return self._core.activation_rules.get_label(rule_id)
        return rule_id

    @property
    def item_data(self) -> dict:
        return self._item_data

    def update_state(self, state: str) -> None:
        self._state = state
        color = _STATE_COLORS.get(state, "#666")
        self._state_dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        name_color = _STATE_COLORS.get(state, "#ccc") if state != "unknown" else "#ccc"
        self._name_label.setStyleSheet(f"color: {name_color}; font-size: 11px;")

    # --- Drag support ---

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return super().mouseMoveEvent(event)
        if (event.position().toPoint() - self._drag_start).manhattanLength() < DRAG_THRESHOLD_PX:
            return super().mouseMoveEvent(event)
        mime = QMimeData()
        mime.setData(MIME_PRIORITY_ITEM, str(self._rank).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start = None

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        item_type = str(self._item_data.get("type", "")).lower()
        if item_type not in ("slot", "manual"):
            return
        menu = QMenu(self)
        rule_actions: dict[object, str] = {}
        if item_type == "slot" and self._core and hasattr(self._core, "activation_rules"):
            current = normalize_activation_rule(self._item_data.get("activation_rule"))
            grouped = self._core.activation_rules.list_grouped()
            if len(grouped) <= 1:
                for rules in grouped.values():
                    for rule in rules:
                        act = menu.addAction(f"Activation: {rule.label}")
                        act.setCheckable(True)
                        act.setChecked(current == rule.id)
                        rule_actions[act] = rule.id
            else:
                activation_menu = menu.addMenu("Activation")
                for group_key, rules in grouped.items():
                    group_label = rules[0].group_label if rules else group_key
                    submenu = activation_menu.addMenu(group_label)
                    for rule in rules:
                        act = submenu.addAction(rule.label)
                        act.setCheckable(True)
                        act.setChecked(current == rule.id)
                        rule_actions[act] = rule.id
            menu.addSeparator()
        remove_action = menu.addAction("Remove")
        chosen = menu.exec(event.globalPos())
        if chosen is None:
            return
        panel = self._find_panel()
        if not panel:
            return
        if chosen == remove_action:
            panel._remove_item(self._rank)
        elif chosen in rule_actions:
            panel._set_activation_rule(self._rank, rule_actions[chosen])

    def _find_panel(self) -> Optional["PriorityPanel"]:
        p = self.parent()
        while p is not None:
            if isinstance(p, PriorityPanel):
                return p
            p = p.parent()
        return None


class _DropScrollArea(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        p = self.parentWidget()
        if p and p.acceptDrops():
            p.dragEnterEvent(event)
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        p = self.parentWidget()
        if p and p.acceptDrops():
            p.dragMoveEvent(event)
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        p = self.parentWidget()
        if p and p.acceptDrops():
            p.dropEvent(event)
        else:
            super().dropEvent(event)


class PriorityPanel(QWidget):
    """Sidebar panel: shows active priority list with drag-and-drop reorder."""

    def __init__(self, core: Any, module_ref: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core = core
        self._module = module_ref
        self.setAcceptDrops(True)
        self._item_widgets: list[PriorityItemWidget] = []
        self._build_ui()
        self.refresh_from_config()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("PRIORITY")
        title.setStyleSheet(
            "font-family: monospace; font-size: 10px; color: #7a7a8e;"
            " font-weight: bold; letter-spacing: 1.5px;"
        )
        header.addWidget(title)
        header.addStretch()
        self._list_name_label = QLabel("")
        self._list_name_label.setStyleSheet("font-size: 11px; color: #aaa; font-style: italic;")
        header.addWidget(self._list_name_label)
        layout.addLayout(header)

        self._scroll = _DropScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        btn_row = QHBoxLayout()
        btn_add_slot = QPushButton("+ slot")
        btn_add_slot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_slot.setToolTip("Add a slot to the priority list")
        btn_add_slot.clicked.connect(self._on_add_slot)
        btn_row.addWidget(btn_add_slot)

        btn_add_manual = QPushButton("+ manual")
        btn_add_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_manual.setToolTip("Add an action not tied to a monitored slot")
        btn_add_manual.clicked.connect(self._on_add_manual)
        btn_row.addWidget(btn_add_manual)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh_from_config(self, _list_id: str = "") -> None:
        cfg = self._core.get_config(self._module.key)
        active_list = self._resolve_active_list(cfg)
        if not active_list:
            self._list_name_label.setText("")
            self._clear_items()
            return

        self._list_name_label.setText(active_list.get("name", ""))
        keybinds = cfg.get("keybinds", [])
        display_names = cfg.get("slot_display_names", [])
        manual_actions = active_list.get("manual_actions", [])
        manual_by_id = {
            str(a.get("id", "")).lower(): a for a in manual_actions
        }

        self._clear_items()
        for rank, item in enumerate(active_list.get("priority_items", [])):
            item_type = str(item.get("type", "")).lower()
            if item_type == "slot":
                idx = item.get("slot_index", 0)
                kb = keybinds[idx] if idx < len(keybinds) else "?"
                name = display_names[idx] if idx < len(display_names) and display_names[idx].strip() else f"Slot {idx + 1}"
            elif item_type == "manual":
                aid = str(item.get("action_id", "")).lower()
                action = manual_by_id.get(aid)
                kb = str(action.get("keybind", "")).strip() if action else "?"
                name = str(action.get("name", "")).strip() if action else "Manual"
            else:
                continue

            w = PriorityItemWidget(item, rank, kb, name, core=self._core, parent=self._list_container)
            self._list_layout.insertWidget(self._list_layout.count() - 1, w)
            self._item_widgets.append(w)

    def update_states(self, states: list[dict]) -> None:
        by_index = {s.get("index"): s.get("state", "unknown") for s in states}
        for w in self._item_widgets:
            item = w.item_data
            if str(item.get("type", "")).lower() == "slot":
                idx = item.get("slot_index")
                w.update_state(by_index.get(idx, "unknown"))

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_PRIORITY_ITEM):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_PRIORITY_ITEM):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if not mime.hasFormat(MIME_PRIORITY_ITEM):
            return
        from_rank = int(mime.data(MIME_PRIORITY_ITEM).data().decode())

        pos = event.position().toPoint()
        local = self._list_container.mapFrom(self, pos)
        drop_rank = len(self._item_widgets)
        for i, w in enumerate(self._item_widgets):
            if local.y() < w.y() + w.height() // 2:
                drop_rank = i
                break

        cfg = self._core.get_config(self._module.key)
        active_list = self._resolve_active_list(cfg)
        if not active_list:
            return
        items = active_list.get("priority_items", [])
        if from_rank < 0 or from_rank >= len(items):
            return
        moved = items.pop(from_rank)
        items.insert(drop_rank, moved)
        active_list["priority_items"] = items
        self._save_lists(cfg)
        self.refresh_from_config()
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Add / remove
    # ------------------------------------------------------------------

    def _on_add_slot(self) -> None:
        cfg = self._core.get_config(self._module.key)
        active_list = self._resolve_active_list(cfg)
        if not active_list:
            return
        cc_cfg = self._core.get_config("core_capture")
        slot_count = cc_cfg.get("slots", {}).get("count", 10)
        existing = {
            item.get("slot_index")
            for item in active_list.get("priority_items", [])
            if str(item.get("type", "")).lower() == "slot"
        }
        available = [i for i in range(slot_count) if i not in existing]
        if not available:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Slot")
        dlg_layout = QVBoxLayout(dlg)
        lw = QListWidget()
        keybinds = cfg.get("keybinds", [])
        display_names = cfg.get("slot_display_names", [])
        for idx in available:
            kb = keybinds[idx] if idx < len(keybinds) else ""
            name = display_names[idx] if idx < len(display_names) and display_names[idx].strip() else f"Slot {idx + 1}"
            label = f"[{kb or '?'}] {name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            lw.addItem(item)
        dlg_layout.addWidget(lw)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        dlg_layout.addWidget(buttons)
        if dlg.exec() == QDialog.DialogCode.Accepted and lw.currentItem():
            slot_idx = lw.currentItem().data(Qt.ItemDataRole.UserRole)
            active_list.setdefault("priority_items", []).append(
                {"type": "slot", "slot_index": slot_idx, "activation_rule": "always"}
            )
            self._save_lists(cfg)
            self.refresh_from_config()

    def _on_add_manual(self) -> None:
        cfg = self._core.get_config(self._module.key)
        active_list = self._resolve_active_list(cfg)
        if not active_list:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Manual Action")
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.addWidget(QLabel("Name:"))
        name_edit = QLineEdit()
        dlg_layout.addWidget(name_edit)
        dlg_layout.addWidget(QLabel("Keybind:"))
        kb_edit = QLineEdit()
        dlg_layout.addWidget(kb_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        dlg_layout.addWidget(buttons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name_val = name_edit.text().strip()
            kb_val = kb_edit.text().strip()
            if not name_val or not kb_val:
                return
            import uuid
            action_id = uuid.uuid4().hex[:8]
            active_list.setdefault("manual_actions", []).append(
                {"id": action_id, "name": name_val, "keybind": kb_val}
            )
            active_list.setdefault("priority_items", []).append(
                {"type": "manual", "action_id": action_id}
            )
            self._save_lists(cfg)
            self.refresh_from_config()

    def _remove_item(self, rank: int) -> None:
        cfg = self._core.get_config(self._module.key)
        active_list = self._resolve_active_list(cfg)
        if not active_list:
            return
        items = active_list.get("priority_items", [])
        if 0 <= rank < len(items):
            items.pop(rank)
            active_list["priority_items"] = items
            self._save_lists(cfg)
            self.refresh_from_config()

    def _set_activation_rule(self, rank: int, rule: str) -> None:
        cfg = self._core.get_config(self._module.key)
        active_list = self._resolve_active_list(cfg)
        if not active_list:
            return
        items = active_list.get("priority_items", [])
        if 0 <= rank < len(items):
            items[rank]["activation_rule"] = normalize_activation_rule(rule)
            self._save_lists(cfg)
            self.refresh_from_config()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_items(self) -> None:
        for w in self._item_widgets:
            w.deleteLater()
        self._item_widgets.clear()

    def _resolve_active_list(self, cfg: dict) -> dict | None:
        active_id = cfg.get("active_list_id", "")
        for pl in cfg.get("priority_lists", []):
            if pl.get("id") == active_id:
                return pl
        lists = cfg.get("priority_lists", [])
        return lists[0] if lists else None

    def _save_lists(self, cfg: dict) -> None:
        self._core.save_config(self._module.key, cfg)
