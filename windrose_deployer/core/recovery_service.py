"""Build user-facing recovery/history items from manifest history and backups."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from ..models.deployment_record import DeploymentRecord
from ..models.mod_install import ModInstall
from .backup_manager import BackupManager, BackupRecord
from .manifest_store import ManifestStore


@dataclass
class RecoveryItem:
    item_id: str
    timestamp: str
    title: str
    subtitle: str
    summary: str
    category: str
    action: str
    target: str
    files_affected: int = 0
    can_restore: bool = False
    can_undo: bool = False
    details: list[str] = field(default_factory=list)
    deployment_record: DeploymentRecord | None = None
    backup_record: BackupRecord | None = None


class RecoveryService:
    """Translate raw history/backups into a recovery-oriented timeline."""

    def __init__(self, manifest: ManifestStore, backup_manager: BackupManager):
        self.manifest = manifest
        self.backup = backup_manager

    def build_timeline(self) -> list[RecoveryItem]:
        mods_by_id = {mod.mod_id: mod for mod in self.manifest.list_mods()}
        history = self.manifest.list_history()
        items = self._history_items(history, mods_by_id)
        items.extend(self._backup_items(history))
        items.sort(key=lambda item: item.timestamp, reverse=True)
        return items

    def _history_items(
        self,
        history: list[DeploymentRecord],
        mods_by_id: dict[str, ModInstall],
    ) -> list[RecoveryItem]:
        items: list[RecoveryItem] = []
        for idx, record in enumerate(history):
            name = record.display_name or mods_by_id.get(record.mod_id, ModInstall(
                mod_id=record.mod_id,
                display_name=record.mod_id,
                source_archive=record.source_archive,
            )).display_name
            title = self._history_title(record.action, name)
            subtitle = self._target_label(record.target)
            details = [
                f"Action: {record.action}",
                f"Target: {subtitle}",
            ]
            if record.notes:
                details.append(f"Summary: {record.notes}")
            if record.source_archive:
                details.append(f"Source: {record.source_archive}")
            for deployed in record.files[:12]:
                if deployed.dest_path:
                    details.append(f"File: {deployed.dest_path}")

            items.append(
                RecoveryItem(
                    item_id=f"history:{idx}",
                    timestamp=record.timestamp,
                    title=title,
                    subtitle=subtitle,
                    summary=record.notes or f"{len(record.files)} file(s) affected",
                    category="history",
                    action=record.action,
                    target=record.target,
                    files_affected=len(record.files),
                    can_restore=record.action.startswith("save_"),
                    can_undo=self._can_undo_history(record, mods_by_id.get(record.mod_id)),
                    details=details,
                    deployment_record=record,
                )
            )
        return items

    def _backup_items(self, history: list[DeploymentRecord]) -> list[RecoveryItem]:
        items: list[RecoveryItem] = []
        for idx, record in enumerate(self.backup.list_backups()):
            if record.category == "installs":
                # File-level install backups are available in Advanced recovery details,
                # but they are too noisy for the primary action timeline.
                continue
            if self._has_nearby_history_backup(record, history):
                continue

            title = self._backup_title(record)
            details = [
                f"Source: {record.source_path}",
                f"Backup: {record.backup_path}",
            ]
            if record.description:
                details.append(f"Summary: {record.description}")

            items.append(
                RecoveryItem(
                    item_id=f"backup:{idx}",
                    timestamp=record.timestamp,
                    title=title,
                    subtitle=self._backup_category_label(record.category),
                    summary=record.description or Path(record.backup_path).name,
                    category="backup",
                    action="restore_backup",
                    target=record.category,
                    files_affected=1,
                    can_restore=True,
                    can_undo=False,
                    details=details,
                    backup_record=record,
                )
            )
        return items

    @staticmethod
    def _history_title(action: str, name: str) -> str:
        verbs = {
            "install": "Installed",
            "uninstall": "Uninstalled",
            "disable": "Disabled",
            "enable": "Enabled",
            "repair": "Repaired",
            "save_server_config": "Saved Dedicated Server Settings",
            "save_world_config": "Saved Dedicated World Settings",
            "save_remote_server_config": "Saved Hosted Server Settings",
            "save_remote_world_config": "Saved Hosted World Settings",
            "hosted_upload": "Uploaded to Hosted Server",
            "hosted_restart": "Ran Hosted Restart Command",
        }
        verb = verbs.get(action, action.replace("_", " ").title())
        if action.startswith("save_") or action == "hosted_restart":
            return verb
        return f"{verb} {name}"

    @staticmethod
    def _target_label(target: str) -> str:
        target = (target or "").strip()
        if target == "client":
            return "Client"
        if target == "server":
            return "Bundled Server"
        if target == "dedicated_server":
            return "Dedicated Server"
        if target == "both":
            return "Client + Bundled Server"
        if target == "hosted":
            return "Hosted Server"
        if "," in target:
            return (
                target
                .replace("dedicated_server", "Dedicated Server")
                .replace("client", "Client")
                .replace("server", "Bundled Server")
            )
        return target or "Unknown"

    @staticmethod
    def _backup_category_label(category: str) -> str:
        labels = {
            "server_config": "Dedicated Server",
            "world_config": "Dedicated World",
            "remote_server_config": "Hosted Server",
            "remote_world_config": "Hosted World",
        }
        return labels.get(category, category.replace("_", " ").title())

    @staticmethod
    def _backup_title(record: BackupRecord) -> str:
        title_map = {
            "server_config": "Saved Dedicated Server Settings",
            "world_config": "Saved Dedicated World Settings",
            "remote_server_config": "Saved Hosted Server Settings",
            "remote_world_config": "Saved Hosted World Settings",
        }
        return title_map.get(record.category, record.description or "Created Backup")

    @staticmethod
    def _has_nearby_history_backup(
        backup_record: BackupRecord,
        history_records: Iterable[DeploymentRecord],
    ) -> bool:
        action_map = {
            "server_config": "save_server_config",
            "world_config": "save_world_config",
            "remote_server_config": "save_remote_server_config",
            "remote_world_config": "save_remote_world_config",
        }
        expected_action = action_map.get(backup_record.category)
        if not expected_action:
            return False
        backup_time = RecoveryService._parse_time(backup_record.timestamp)
        if backup_time is None:
            return False
        for record in history_records:
            if record.action != expected_action:
                continue
            record_time = RecoveryService._parse_time(record.timestamp)
            if record_time is None:
                continue
            if abs((record_time - backup_time).total_seconds()) <= 5:
                return True
        return False

    @staticmethod
    def _parse_time(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    @staticmethod
    def _can_undo_history(record: DeploymentRecord, mod: Optional[ModInstall]) -> bool:
        if record.action == "install":
            return mod is not None
        if record.action in {"disable", "enable"}:
            return mod is not None
        return False
