# Task: Dynamic Activation Rule Registry

## Problem

The priority list context menu hardcodes three activation rules: Always, Glow Only, DoT Refresh. Glow and DoT detection modules don't exist yet, so those options shouldn't appear. And when new detection modules ARE added later, the automation module shouldn't need to be updated — each module should register its own rules.

## Solution

Add an `ActivationRuleRegistry` to Core. Modules register rules during `setup()`. The priority panel context menu reads the registry instead of hardcoding options.

## Requirements

### 1. ActivationRuleRegistry (`src/core/activation_rules.py`)

```python
@dataclass
class ActivationRule:
    id: str              # "always", "require_glow", "dot_refresh"
    label: str           # "Always", "Require Glow"
    group: str           # "brightness", "glow" — used for submenu grouping
    group_label: str     # "Brightness", "Glow" — display name for the submenu
    owner: str           # module key that registered it
    order: int = 50      # sort order within group

class ActivationRuleRegistry:
    def __init__(self):
        self._rules: dict[str, ActivationRule] = {}
    
    def register(self, id, label, group, group_label, owner, order=50):
        self._rules[id] = ActivationRule(id=id, label=label, group=group,
            group_label=group_label, owner=owner, order=order)
    
    def list_rules(self) -> list[ActivationRule]:
        """Return all rules sorted by group_label then order."""
        return sorted(self._rules.values(), key=lambda r: (r.group_label, r.order))
    
    def list_grouped(self) -> dict[str, list[ActivationRule]]:
        """Return {group: [rules]} for building nested menus."""
        from collections import defaultdict
        groups = defaultdict(list)
        for rule in self.list_rules():
            groups[rule.group].append(rule)
        return dict(groups)
    
    def get(self, id: str) -> ActivationRule | None:
        return self._rules.get(id)
    
    def get_label(self, id: str) -> str:
        """Get display label for a rule ID. Returns the ID itself if not registered."""
        rule = self._rules.get(id)
        return rule.label if rule else id
    
    def teardown_module(self, module_key: str):
        self._rules = {k: v for k, v in self._rules.items() if v.owner != module_key}
```

### 2. Wire into Core (`src/core/core.py`)

```python
from src.core.activation_rules import ActivationRuleRegistry

class Core:
    def __init__(self, config):
        # ... existing managers ...
        self.activation_rules = ActivationRuleRegistry()
```

### 3. Automation module registers "always" (`modules/automation/module.py`)

In `setup()`, after `super().setup(core)`:

```python
core.activation_rules.register(
    id="always",
    label="Always",
    group="general",
    group_label="General",
    owner=self.key,
    order=0,
)
```

This is the only rule that exists until glow/other modules are loaded.

### 4. Priority panel context menu uses registry (`modules/automation/priority_panel.py`)

Replace the hardcoded activation rule menu with a dynamic nested menu:

```python
def _build_activation_menu(self, parent_menu):
    """Build nested Activation submenu from registry."""
    activation_menu = parent_menu.addMenu("Activation")
    grouped = self._core.activation_rules.list_grouped()
    
    if len(grouped) == 1:
        # Only one group — no need for sub-submenus, show rules flat
        for rule in list(grouped.values())[0]:
            action = activation_menu.addAction(rule.label)
            action.setCheckable(True)
            action.setChecked(self._current_activation_rule == rule.id)
            action.triggered.connect(lambda checked, r=rule.id: self._set_activation_rule(r))
    else:
        # Multiple groups — create a submenu per group
        for group_key, rules in grouped.items():
            group_label = rules[0].group_label if rules else group_key
            submenu = activation_menu.addMenu(group_label)
            for rule in rules:
                action = submenu.addAction(rule.label)
                action.setCheckable(True)
                action.setChecked(self._current_activation_rule == rule.id)
                action.triggered.connect(lambda checked, r=rule.id: self._set_activation_rule(r))
    
    return activation_menu
```

Menu structure with only automation loaded:
```
Activation → Always ✓
```

Menu structure after glow and DoT modules are added (future):
```
Activation ─┬─ General
            ├─ Glow ─┬─── Activate
            │        └─── Settings
            ├─ DoT  ─┬─── Activate
            │        └─── Settings
            └─ (Future Options)
(Future Option)
```

### 5. Remove hardcoded rules

Remove any hardcoded "Glow Only" / "DoT Refresh" options from the priority panel. The only activation rules that appear are those registered in the registry.

Also update `priority_rules.py` — the eligibility functions (`_activation_allows`, etc.) should still handle all rule IDs gracefully. Unknown rule IDs should fall through to "always" behavior. No changes needed there since it already defaults to `True` for unknown rules.

### 6. Tests

Add to existing test files or create `tests/test_activation_rules.py`:

```python
# Test: register rule, list_rules returns it
# Test: list_grouped groups by group key
# Test: get returns registered rule
# Test: get_label returns label for known ID, ID itself for unknown
# Test: teardown_module removes only that module's rules
# Test: multiple groups sort correctly
# Test: single group returned flat from list_grouped
```

Update `test_automation_module.py`:
```python
# Test: setup registers "always" activation rule
# Test: activation_rules registry accessible via core
```

### 7. Priority rules display label

Wherever the priority panel currently shows the activation rule text on a `PriorityItemWidget` (the small label like "always" or "dot_refresh"), use `core.activation_rules.get_label(rule_id)` instead of raw ID strings. If a rule was saved but its module is no longer loaded, it degrades to showing the raw ID — which is fine.
