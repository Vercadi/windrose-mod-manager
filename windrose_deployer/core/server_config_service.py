"""ServerDescription.json loading, editing, and saving."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..models.server_config import ServerConfig
from ..utils.json_io import read_json, write_json
from .backup_manager import BackupManager

log = logging.getLogger(__name__)


class ServerConfigService:
    """Safe read/write of ServerDescription.json with backup."""

    def __init__(self, backup_manager: BackupManager):
        self.backup = backup_manager

    def load(self, path: Path) -> Optional[ServerConfig]:
        """Load and parse ServerDescription.json."""
        if not path.is_file():
            log.error("ServerDescription.json not found: %s", path)
            return None

        data = read_json(path)
        if not data:
            log.error("Empty or invalid ServerDescription.json")
            return None

        config = ServerConfig.from_json_dict(data)
        log.info("Loaded server config: %s (server: %s)", path, config.server_name)
        return config

    def save(self, path: Path, config: ServerConfig) -> tuple[bool, list[str]]:
        """Validate, back up, and save the config.

        Returns (success, errors).
        """
        errors = config.validate()
        if errors:
            return False, errors

        record = self.backup.backup_file(
            path,
            category="server_config",
            description="Pre-save backup of ServerDescription.json",
        )
        if path.is_file() and record is None:
            log.warning("Could not back up ServerDescription.json before save — proceeding anyway")

        try:
            write_json(path, config.to_json_dict())
            log.info("Saved server config to %s", path)
            return True, []
        except Exception as exc:
            log.error("Failed to save server config: %s", exc)
            return False, [str(exc)]

    def restore_latest(self, path: Path) -> bool:
        """Restore the most recent backup of ServerDescription.json."""
        backups = self.backup.list_backups(category="server_config")
        if not backups:
            log.warning("No server config backups available")
            return False

        latest = backups[-1]
        return self.backup.restore_backup(latest)
