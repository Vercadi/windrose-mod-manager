"""Persistent manifest store — tracks all installed mods and deployment history."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from ..models.deployment_record import DeploymentRecord
from ..models.mod_install import ModInstall
from ..utils.filesystem import ensure_dir
from ..utils.json_io import read_json, write_json

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2


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
        """Add a mod to the manifest, generating a unique id on collision."""
        if mod.mod_id in self._mods:
            existing = self._mods[mod.mod_id]
            if set(existing.installed_files) != set(mod.installed_files):
                suffix = 2
                while f"{mod.mod_id}_{suffix}" in self._mods:
                    suffix += 1
                old_id = mod.mod_id
                mod.mod_id = f"{old_id}_{suffix}"
                log.warning("Mod id collision for '%s', renamed to '%s'", old_id, mod.mod_id)
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

    def remove_last_records(self, count: int) -> None:
        if count <= 0:
            return
        del self._history[-count:]
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
        file_version = data.get("schema_version", 1)

        for d in data.get("mods", []):
            try:
                if file_version < 2:
                    self._migrate_mod_v1_to_v2(d)
                mod = ModInstall.from_dict(d)
                self._mods[mod.mod_id] = mod
            except Exception as exc:
                log.warning("Skipping corrupt mod entry: %s", exc)

        for d in data.get("history", []):
            try:
                self._history.append(DeploymentRecord.from_dict(d))
            except Exception as exc:
                log.warning("Skipping corrupt history entry: %s", exc)

        if file_version < SCHEMA_VERSION:
            self._backup_before_migration(file_version)
            log.info("Migrated manifest from schema v%d to v%d", file_version, SCHEMA_VERSION)
            self._save()

        log.info("Loaded manifest: %d mods, %d history records", len(self._mods), len(self._history))

    def _backup_before_migration(self, old_version: int) -> None:
        """Copy the manifest file before rewriting it during schema migration."""
        backup_name = f"app_state.v{old_version}.bak.json"
        backup_path = self.data_dir / backup_name
        try:
            shutil.copy2(str(self._state_path), str(backup_path))
            log.info("Backed up pre-migration manifest to %s", backup_path)
        except Exception as exc:
            log.warning("Could not back up manifest before migration: %s", exc)

    @staticmethod
    def _migrate_mod_v1_to_v2(d: dict) -> None:
        """v1 used sanitized name as mod_id. v2 uses UUID.
        Generate a UUID for old entries that have name-style ids."""
        import uuid
        old_id = d.get("mod_id", "")
        if old_id and len(old_id) != 32:
            d["mod_id"] = uuid.uuid4().hex
            log.info("Migrated mod '%s' -> UUID %s", old_id, d["mod_id"])

    def _save(self) -> None:
        ensure_dir(self.data_dir)
        data = {
            "schema_version": SCHEMA_VERSION,
            "mods": [m.to_dict() for m in self._mods.values()],
            "history": [r.to_dict() for r in self._history],
        }
        write_json(self._state_path, data)
