"""Discover, load, save, and back up WorldDescription.json files."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..models.world_config import WorldConfig
from ..utils.json_io import read_json, write_json
from .backup_manager import BackupManager

log = logging.getLogger(__name__)


class WorldConfigService:
    """Manages WorldDescription.json files for server worlds."""

    def __init__(self, backup_manager: BackupManager):
        self.backup = backup_manager

    def discover_worlds(self, local_save_root: Optional[Path] = None) -> list[Path]:
        """Find all WorldDescription.json files under the save profiles tree.

        Search path: <local_save_root>/SaveProfiles/*/RocksDB/*/Worlds/*/WorldDescription.json
        """
        results: list[Path] = []
        if not local_save_root or not local_save_root.is_dir():
            return results

        profiles_dir = local_save_root / "SaveProfiles"
        if not profiles_dir.is_dir():
            return results

        for profile in profiles_dir.iterdir():
            if not profile.is_dir():
                continue
            rocksdb = profile / "RocksDB"
            if not rocksdb.is_dir():
                continue
            for version_dir in rocksdb.iterdir():
                if not version_dir.is_dir():
                    continue
                worlds_dir = version_dir / "Worlds"
                if not worlds_dir.is_dir():
                    continue
                for world_dir in worlds_dir.iterdir():
                    wd = world_dir / "WorldDescription.json"
                    if wd.is_file():
                        results.append(wd)
                        log.info("Discovered world: %s", wd)

        log.info("Found %d world(s)", len(results))
        return results

    def find_world_by_island_id(
        self,
        island_id: str,
        local_save_root: Optional[Path] = None,
    ) -> Optional[Path]:
        """Find the WorldDescription.json that matches a given WorldIslandId."""
        for path in self.discover_worlds(local_save_root):
            data = read_json(path)
            wd = data.get("WorldDescription", {})
            wid = wd.get("islandId", wd.get("IslandId", ""))
            if wid.upper() == island_id.upper():
                return path
        return None

    def load(self, path: Path) -> Optional[WorldConfig]:
        """Load a WorldDescription.json into a WorldConfig model."""
        if not path.is_file():
            log.error("WorldDescription.json not found: %s", path)
            return None

        data = read_json(path)
        if not data:
            log.error("Empty or invalid WorldDescription.json: %s", path)
            return None

        config = WorldConfig.from_json_dict(data, file_path=str(path))
        log.info("Loaded world config: %s (name: %s, preset: %s)",
                 path, config.world_name, config.world_preset_type)
        return config

    def save(self, path: Path, config: WorldConfig) -> tuple[bool, list[str]]:
        """Validate, back up, and save the world config.

        Returns (success, errors).
        """
        errors = config.validate()
        if errors:
            return False, errors

        record = self.backup.backup_file(
            path,
            category="server_config",
            description=f"Pre-save backup of WorldDescription.json ({config.world_name})",
        )
        if path.is_file() and record is None:
            log.warning("Could not back up WorldDescription.json before save")

        try:
            write_json(path, config.to_json_dict())
            log.info("Saved world config to %s", path)
            return True, []
        except Exception as exc:
            log.error("Failed to save world config: %s", exc)
            return False, [str(exc)]
