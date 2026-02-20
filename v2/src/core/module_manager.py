from __future__ import annotations

import importlib
import inspect
import logging
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from src.core.base_module import BaseModule

logger = logging.getLogger(__name__)


class ModuleManager:
    def __init__(self, core: Any) -> None:
        self.core = core
        self._discovered: dict[str, type[BaseModule]] = {}
        self.modules: dict[str, BaseModule] = {}
        self._load_order: list[str] = []

    def discover(self, modules_dir: Path) -> list[str]:
        if not modules_dir.is_dir():
            logger.warning("Modules directory does not exist: %s", modules_dir)
            return []

        if str(modules_dir.parent) not in sys.path:
            sys.path.insert(0, str(modules_dir.parent))

        for candidate in sorted(modules_dir.iterdir()):
            if not candidate.is_dir():
                continue
            if not (candidate / "__init__.py").exists():
                continue

            module_name = f"modules.{candidate.name}"
            try:
                mod = importlib.import_module(module_name)
            except Exception as e:
                logger.error("Failed to import %s: %s", module_name, e)
                continue

            found = False
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, BaseModule)
                    and attr is not BaseModule
                    and attr.key
                ):
                    if attr.key in self._discovered:
                        logger.warning(
                            "Duplicate module key '%s' from %s — keeping first",
                            attr.key, module_name,
                        )
                    else:
                        self._discovered[attr.key] = attr
                        logger.info(
                            "Discovered module: %s (%s) from %s",
                            attr.name, attr.key, module_name,
                        )
                        found = True
                    break

            if not found:
                logger.debug("No BaseModule subclass with key found in %s", module_name)

        return list(self._discovered.keys())

    def load(self, enabled_keys: list[str] | None = None) -> None:
        if enabled_keys is None:
            enabled_keys = list(self._discovered.keys())

        to_load = {k: self._discovered[k] for k in enabled_keys if k in self._discovered}

        for key in list(to_load.keys()):
            cls = to_load[key]
            for req in cls.requires:
                if req not in to_load and req not in self._discovered:
                    logger.warning(
                        "Module '%s' requires '%s' which is not available — skipping",
                        key, req,
                    )
                    del to_load[key]
                    break

        order = self._topological_sort(to_load)

        for key in order:
            cls = to_load[key]
            try:
                instance = cls()
                self.modules[key] = instance
                self.core.register_module(key, instance)
                logger.info("Instantiated module: %s", key)
            except Exception as e:
                logger.exception("Failed to instantiate module '%s': %s", key, e)

        for key in order:
            if key not in self.modules:
                continue
            try:
                self.modules[key].setup(self.core)
                logger.info("Setup complete: %s", key)
            except Exception as e:
                logger.exception("setup() failed for module '%s': %s", key, e)

        for key in order:
            if key not in self.modules:
                continue
            try:
                self.modules[key].ready()
                logger.debug("ready() complete: %s", key)
            except Exception as e:
                logger.exception("ready() failed for module '%s': %s", key, e)

        self._load_order = [k for k in order if k in self.modules]
        logger.info("Module load order: %s", self._load_order)

    def get(self, key: str) -> BaseModule | None:
        return self.modules.get(key)

    def shutdown(self) -> None:
        for key in reversed(self._load_order):
            mod = self.modules.get(key)
            if mod is None:
                continue
            try:
                mod.teardown()
                logger.info("Teardown complete: %s", key)
            except Exception as e:
                logger.exception("teardown() failed for module '%s': %s", key, e)

    def _topological_sort(self, to_load: dict[str, type[BaseModule]]) -> list[str]:
        in_degree: dict[str, int] = {k: 0 for k in to_load}
        dependents: dict[str, list[str]] = defaultdict(list)

        for key, cls in to_load.items():
            deps = [d for d in (cls.requires + cls.optional) if d in to_load]
            in_degree[key] = len(deps)
            for dep in deps:
                dependents[dep].append(key)

        queue: deque[str] = deque(k for k, d in in_degree.items() if d == 0)
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(to_load):
            cycle_members = set(to_load.keys()) - set(result)
            logger.error("Dependency cycle detected among modules: %s — skipping them", cycle_members)

        return result
