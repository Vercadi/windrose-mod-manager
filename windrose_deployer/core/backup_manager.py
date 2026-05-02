"""Backup and restore manager."""
from __future__ import annotations

import logging
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..utils.filesystem import ensure_dir, safe_delete
from ..utils.json_io import read_json, write_json
from ..utils.naming import timestamp_slug

log = logging.getLogger(__name__)

DEFAULT_MAX_BACKUPS_PER_SOURCE = 10


@dataclass
class BackupRecord:
    backup_id: str
    timestamp: str
    category: str  # "installs" | "server_config"
    source_path: str
    backup_path: str
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "backup_id": self.backup_id,
            "timestamp": self.timestamp,
            "category": self.category,
            "source_path": self.source_path,
            "backup_path": self.backup_path,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BackupRecord:
        return cls(
            backup_id=d.get("backup_id", ""),
            timestamp=d.get("timestamp", ""),
            category=d.get("category", "installs"),
            source_path=d.get("source_path", ""),
            backup_path=d.get("backup_path", ""),
            description=d.get("description", ""),
        )


class BackupManager:
    """Manages timestamped backups in an app-controlled directory."""

    def __init__(
        self,
        backup_root: Path,
        max_backups_per_source: int | None = DEFAULT_MAX_BACKUPS_PER_SOURCE,
    ):
        self.backup_root = backup_root
        self.max_backups_per_source = max_backups_per_source
        self.installs_dir = backup_root / "installs"
        self.server_config_dir = backup_root / "server_config"
        self.restore_vanilla_dir = backup_root / "restore_vanilla"
        self.metadata_dir = backup_root / "metadata"
        self._records_path = self.metadata_dir / "backup_records.json"
        self._records: list[BackupRecord] = []
        self._load_records()

    # ---------------------------------------------------------- public API

    def backup_file(
        self,
        source: Path,
        category: str = "installs",
        description: str = "",
    ) -> Optional[BackupRecord]:
        """Create a backup of *source* and return the record."""
        if not source.is_file():
            log.warning("Cannot back up non-existent file: %s", source)
            return None

        ts = timestamp_slug()
        cat_dir = self._category_dir(category)
        dest = cat_dir / f"{ts}_{source.name}"

        counter = 1
        while dest.exists():
            dest = cat_dir / f"{ts}_{source.stem}_{counter}{source.suffix}"
            counter += 1

        ensure_dir(cat_dir)
        shutil.copy2(source, dest)

        record = BackupRecord(
            backup_id=f"{category}_{dest.name}",
            timestamp=datetime.now().isoformat(),
            category=category,
            source_path=str(source),
            backup_path=str(dest),
            description=description or f"Backup of {source.name}",
        )
        self._append_record(record)
        log.info("Backed up %s -> %s", source, dest)
        return record

    def backup_directory(
        self,
        source: Path,
        category: str = "installs",
        description: str = "",
    ) -> Optional[BackupRecord]:
        """Create a recursive backup of *source* and return the record."""
        if not source.is_dir():
            log.warning("Cannot back up non-existent directory: %s", source)
            return None

        ts = timestamp_slug()
        cat_dir = self._category_dir(category)
        dest = cat_dir / f"{ts}_{source.name}"

        counter = 1
        while dest.exists():
            dest = cat_dir / f"{ts}_{source.name}_{counter}"
            counter += 1

        ensure_dir(cat_dir)
        shutil.copytree(source, dest)

        record = BackupRecord(
            backup_id=f"{category}_{dest.name}",
            timestamp=datetime.now().isoformat(),
            category=category,
            source_path=str(source),
            backup_path=str(dest),
            description=description or f"Backup of {source.name}",
        )
        self._append_record(record)
        log.info("Backed up directory %s -> %s", source, dest)
        return record

    def backup_bytes(
        self,
        *,
        source_path: str,
        filename: str,
        data: bytes,
        category: str = "installs",
        description: str = "",
    ) -> BackupRecord:
        """Persist raw bytes as a managed backup record."""
        ts = timestamp_slug()
        cat_dir = self._category_dir(category)
        suffix = Path(filename).suffix
        stem = Path(filename).stem or filename
        dest = cat_dir / f"{ts}_{filename}"

        counter = 1
        while dest.exists():
            dest = cat_dir / f"{ts}_{stem}_{counter}{suffix}"
            counter += 1

        ensure_dir(cat_dir)
        dest.write_bytes(data)

        record = BackupRecord(
            backup_id=f"{category}_{dest.name}",
            timestamp=datetime.now().isoformat(),
            category=category,
            source_path=source_path,
            backup_path=str(dest),
            description=description or f"Backup of {filename}",
        )
        self._append_record(record)
        log.info("Backed up raw bytes for %s -> %s", source_path, dest)
        return record

    def restore_backup(self, record: BackupRecord, dest_path: Path | None = None) -> bool:
        """Restore a backup to its original location or an explicit destination."""
        backup = Path(record.backup_path)
        dest = dest_path or Path(record.source_path)

        if not backup.exists():
            log.error("Backup file missing: %s", backup)
            return False

        ensure_dir(dest.parent)
        if backup.is_dir():
            if dest.exists():
                safe_delete(dest)
            shutil.copytree(backup, dest)
        else:
            shutil.copy2(backup, dest)
        log.info("Restored %s -> %s", backup, dest)
        return True

    def list_backups(
        self,
        category: Optional[str] = None,
        source_path: Path | str | None = None,
    ) -> list[BackupRecord]:
        records = list(self._records)
        if category:
            records = [r for r in records if r.category == category]
        if source_path is not None:
            source_str = str(source_path)
            records = [r for r in records if r.source_path == source_str]
        return records

    def get_backup(self, backup_id: str) -> Optional[BackupRecord]:
        for r in self._records:
            if r.backup_id == backup_id:
                return r
        return None

    def delete_backup(self, record: BackupRecord, *, delete_file: bool = True) -> bool:
        """Remove a backup record and optionally delete the backup file on disk."""
        removed = False
        if delete_file:
            backup_path = Path(record.backup_path)
            if backup_path.exists():
                removed = safe_delete(backup_path)
            else:
                removed = True

        original_count = len(self._records)
        identity = self._record_identity(record)
        self._records = [r for r in self._records if self._record_identity(r) != identity]
        if len(self._records) != original_count:
            self._save_records()
            return removed or not delete_file or not Path(record.backup_path).exists()
        return False

    def prune_retention(
        self,
        *,
        max_backups_per_source: int | None = None,
        category: str | None = None,
        source_path: Path | str | None = None,
        delete_files: bool = True,
    ) -> int:
        """Prune old backups and keep only the newest N per category+source."""
        limit = self.max_backups_per_source if max_backups_per_source is None else max_backups_per_source
        if limit is None:
            return 0
        if limit < 1:
            raise ValueError("max_backups_per_source must be at least 1 or None")

        filtered_source = str(source_path) if source_path is not None else None
        grouped: dict[tuple[str, str], list[tuple[int, BackupRecord]]] = defaultdict(list)
        for index, record in enumerate(self._records):
            if category is not None and record.category != category:
                continue
            if filtered_source is not None and record.source_path != filtered_source:
                continue
            grouped[(record.category, record.source_path)].append((index, record))

        removal_candidates: list[BackupRecord] = []
        for items in grouped.values():
            if len(items) <= limit:
                continue
            items.sort(key=lambda item: (item[1].timestamp, item[0]))
            overflow = len(items) - limit
            removal_candidates.extend(record for _index, record in items[:overflow])

        if not removal_candidates:
            return 0

        removed_keys: set[tuple[str, str, str, str]] = set()
        for record in removal_candidates:
            removable = True
            if delete_files:
                backup_path = Path(record.backup_path)
                if backup_path.exists():
                    removable = safe_delete(backup_path)
            if removable:
                removed_keys.add(self._record_identity(record))
            else:
                log.warning("Could not delete pruned backup file: %s", record.backup_path)

        if not removed_keys:
            return 0

        self._records = [r for r in self._records if self._record_identity(r) not in removed_keys]
        self._save_records()
        log.info("Pruned %d old backup(s) using retention limit %d", len(removed_keys), limit)
        return len(removed_keys)

    # ---------------------------------------------------------- internals

    def latest_backup(
        self,
        category: Optional[str] = None,
        source_path: Path | str | None = None,
    ) -> Optional[BackupRecord]:
        """Return the most recent backup by timestamp, optionally filtered."""
        candidates = self.list_backups(category, source_path)
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.timestamp)

    def _category_dir(self, category: str) -> Path:
        if category in ("server_config", "world_config", "remote_server_config", "remote_world_config"):
            return self.server_config_dir
        if category == "restore_vanilla":
            return self.restore_vanilla_dir
        return self.installs_dir

    def _load_records(self) -> None:
        if self._records_path.is_file():
            data = read_json(self._records_path)
            self._records = [BackupRecord.from_dict(r) for r in data.get("records", [])]
        else:
            self._records = []

    def _save_records(self) -> None:
        ensure_dir(self.metadata_dir)
        write_json(self._records_path, {"records": [r.to_dict() for r in self._records]})

    def _append_record(self, record: BackupRecord) -> None:
        self._records.append(record)
        self._prune_new_record_history(record)
        self._save_records()

    def _prune_new_record_history(self, record: BackupRecord) -> None:
        limit = self.max_backups_per_source
        if limit is None:
            return

        matching = [
            (index, existing)
            for index, existing in enumerate(self._records)
            if existing.category == record.category and existing.source_path == record.source_path
        ]
        if len(matching) <= limit:
            return

        matching.sort(key=lambda item: (item[1].timestamp, item[0]))
        overflow = len(matching) - limit
        removed_keys: set[tuple[str, str, str, str]] = set()
        for _index, existing in matching[:overflow]:
            backup_path = Path(existing.backup_path)
            if backup_path.exists() and not safe_delete(backup_path):
                log.warning("Could not delete retained-overflow backup file: %s", existing.backup_path)
                continue
            removed_keys.add(self._record_identity(existing))

        if removed_keys:
            self._records = [r for r in self._records if self._record_identity(r) not in removed_keys]
            log.info(
                "Applied backup retention for %s (%s): kept last %d",
                record.source_path,
                record.category,
                limit,
            )

    @staticmethod
    def _record_identity(record: BackupRecord) -> tuple[str, str, str, str]:
        return (
            record.backup_id,
            record.timestamp,
            record.source_path,
            record.backup_path,
        )
