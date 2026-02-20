from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, path: Path):
        self._path = path
        self._root: dict = {}

    def load(self) -> None:
        if not self._path.exists():
            logger.info("Config file not found at %s, starting with empty config", self._path)
            return
        try:
            text = self._path.read_text(encoding="utf-8")
            self._root = json.loads(text)
            logger.info("Loaded config from %s", self._path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load config from %s: %s — starting fresh", self._path, e)
            self._root = {}

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._root, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to save config to %s: %s", self._path, e)

    def get_root(self) -> dict:
        return self._root

    def get(self, namespace: str) -> dict:
        return dict(self._root.get(namespace, {}))

    def set(self, namespace: str, data: dict) -> None:
        self._root[namespace] = data
        self.save()

    def update(self, namespace: str, updates: dict) -> None:
        section = self._root.setdefault(namespace, {})
        section.update(updates)
        self.save()
