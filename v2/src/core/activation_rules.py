"""Dynamic activation rule registry for priority items."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class ActivationRule:
    id: str
    label: str
    group: str
    group_label: str
    owner: str
    order: int = 50


class ActivationRuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, ActivationRule] = {}

    def register(
        self,
        id: str,
        label: str,
        group: str,
        group_label: str,
        owner: str,
        order: int = 50,
    ) -> None:
        self._rules[id] = ActivationRule(
            id=id, label=label, group=group,
            group_label=group_label, owner=owner, order=order,
        )

    def list_rules(self) -> list[ActivationRule]:
        return sorted(self._rules.values(), key=lambda r: (r.group_label, r.order))

    def list_grouped(self) -> dict[str, list[ActivationRule]]:
        groups: dict[str, list[ActivationRule]] = defaultdict(list)
        for rule in self.list_rules():
            groups[rule.group].append(rule)
        return dict(groups)

    def get(self, id: str) -> ActivationRule | None:
        return self._rules.get(id)

    def get_label(self, id: str) -> str:
        rule = self._rules.get(id)
        return rule.label if rule else id

    def teardown_module(self, module_key: str) -> None:
        self._rules = {k: v for k, v in self._rules.items() if v.owner != module_key}
