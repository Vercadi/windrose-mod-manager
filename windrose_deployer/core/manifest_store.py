"""Persistent manifest store — tracks all installed mods and deployment history."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..models.deployment_record import DeploymentRecord
from ..models.mod_install import ModInstall
from ..utils.filesystem import ensure_dir
from ..utils.json_io import read_json, write_json

log = logging.getLogger(__name__)


class ManifestStore:
    """JSON-backed store for mod installs and deployment records."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._state_path = data_dir / "app_state.json"
        self._mods: dict[str, ModInstall] = {}
        self._history: list[DeploymentRecord] = []
        self._load()

    # ---------------------------------------------------------- mods

    def get_mod(self, mod_id: str) -> Optional[ModInstall]:
        return self._mods.get(mod_id)

    def list_mods(self) -> list[ModInstall]:
        return list(self._mods.values())

    def add_mod(self, mod: ModInstall) -> None:
        self._mods[mod.mod_id] = mod
        self._save()

    def remove_mod(self, mod_id: str) -> Optional[ModInstall]:
        mod = self._mods.pop(mod_id, None)
        if mod:
            self._save()
        return mod

    def update_mod(self, mod: ModInstall) -> None:
        self._mods[mod.mod_id] = mod
        self._save()

    # ---------------------------------------------------------- history

    def add_record(self, record: DeploymentRecord) -> None:
        self._history.append(record)
        self._save()

    def list_history(self) -> list[DeploymentRecord]:
        return list(self._history)

    # ---------------------------------------------------------- file mapping

    def get_files_map(self) -> dict[str, list[str]]:
        """Return {dest_path: [mod_ids]} for conflict detection."""
        mapping: dict[str, list[str]] = {}
        for mod in self._mods.values():
            if not mod.enabled:
                continue
            for fp in mod.installed_files:
                mapping.setdefault(fp, []).append(mod.mod_id)
        return mapping

    # ---------------------------------------------------------- persistence

    def _load(self) -> None:
        if not self._state_path.is_file():
            return
        data = read_json(self._state_path)
        for d in data.get("mods", []):
            try:
                mod = ModInstall.from_dict(d)
                self._mods[mod.mod_id] = mod
            except Exception as exc:
                log.warning("Skipping corrupt mod entry: %s", exc)
        for d in data.get("history", []):
            try:
                self._history.append(DeploymentRecord.from_dict(d))
            except Exception as exc:
                log.warning("Skipping corrupt history entry: %s", exc)
        log.info("Loaded manifest: %d mods, %d history records", len(self._mods), len(self._history))

    def _save(self) -> None:
        ensure_dir(self.data_dir)
        data = {
            "mods": [m.to_dict() for m in self._mods.values()],
            "history": [r.to_dict() for r in self._history],
        }
        write_json(self._state_path, data)
