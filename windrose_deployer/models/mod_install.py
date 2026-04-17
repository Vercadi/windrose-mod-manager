from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class InstallTarget(Enum):
    CLIENT = "client"
    SERVER = "server"
    DEDICATED_SERVER = "dedicated_server"
    BOTH = "both"


@dataclass
class ModInstall:
    """Represents an installed mod tracked by the manifest."""
    mod_id: str
    display_name: str
    source_archive: str
    archive_hash: Optional[str] = None
    install_type: str = "pak_only"
    selected_variant: Optional[str] = None
    targets: list[str] = field(default_factory=list)
    installed_files: list[str] = field(default_factory=list)
    backed_up_files: list[str] = field(default_factory=list)
    backup_map: dict[str, str] = field(default_factory=dict)
    install_time: str = field(default_factory=lambda: datetime.now().isoformat())
    enabled: bool = True

    @property
    def file_count(self) -> int:
        return len(self.installed_files)

    def to_dict(self) -> dict:
        return {
            "mod_id": self.mod_id,
            "display_name": self.display_name,
            "source_archive": self.source_archive,
            "archive_hash": self.archive_hash,
            "install_type": self.install_type,
            "selected_variant": self.selected_variant,
            "targets": self.targets,
            "installed_files": self.installed_files,
            "backed_up_files": self.backed_up_files,
            "backup_map": self.backup_map,
            "install_time": self.install_time,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ModInstall:
        return cls(
            mod_id=d["mod_id"],
            display_name=d.get("display_name", d["mod_id"]),
            source_archive=d.get("source_archive", ""),
            archive_hash=d.get("archive_hash"),
            install_type=d.get("install_type", "pak_only"),
            selected_variant=d.get("selected_variant"),
            targets=d.get("targets", []),
            installed_files=d.get("installed_files", []),
            backed_up_files=d.get("backed_up_files", []),
            backup_map=d.get("backup_map", {}),
            install_time=d.get("install_time", ""),
            enabled=d.get("enabled", True),
        )
