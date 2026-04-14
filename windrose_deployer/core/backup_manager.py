"""Backup and restore manager."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..utils.filesystem import ensure_dir, safe_copy
from ..utils.json_io import read_json, write_json
from ..utils.naming import timestamp_slug

log = logging.getLogger(__name__)


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
        return cls(**d)


class BackupManager:
    """Manages timestamped backups in an app-controlled directory."""

    def __init__(self, backup_root: Path):
        self.backup_root = backup_root
        self.installs_dir = backup_root / "installs"
        self.server_config_dir = backup_root / "server_config"
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
            backup_id=f"{category}_{ts}_{source.name}",
            timestamp=datetime.now().isoformat(),
            category=category,
            source_path=str(source),
            backup_path=str(dest),
            description=description or f"Backup of {source.name}",
        )
        self._records.append(record)
        self._save_records()
        log.info("Backed up %s -> %s", source, dest)
        return record

    def restore_backup(self, record: BackupRecord) -> bool:
        """Restore a backup to its original location."""
        backup = Path(record.backup_path)
        dest = Path(record.source_path)

        if not backup.is_file():
            log.error("Backup file missing: %s", backup)
            return False

        ensure_dir(dest.parent)
        shutil.copy2(backup, dest)
        log.info("Restored %s -> %s", backup, dest)
        return True

    def list_backups(self, category: Optional[str] = None) -> list[BackupRecord]:
        if category:
            return [r for r in self._records if r.category == category]
        return list(self._records)

    def get_backup(self, backup_id: str) -> Optional[BackupRecord]:
        for r in self._records:
            if r.backup_id == backup_id:
                return r
        return None

    # ---------------------------------------------------------- internals

    def _category_dir(self, category: str) -> Path:
        if category == "server_config":
            return self.server_config_dir
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
