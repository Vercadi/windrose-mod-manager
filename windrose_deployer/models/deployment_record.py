from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DeployedFile:
    """A single file written by a deployment operation."""
    source_archive_path: str
    dest_path: str
    backup_path: Optional[str] = None
    was_overwrite: bool = False


@dataclass
class DeploymentRecord:
    """Tracks a single deployment action for undo/restore."""
    mod_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    files: list[DeployedFile] = field(default_factory=list)
    target: str = ""  # "client", "server", or "both"
    action: str = "install"  # "install" | "uninstall" | "disable" | "enable" | ...
    display_name: str = ""
    source_archive: str = ""
    archive_hash: Optional[str] = None
    install_kind: str = "standard_mod"
    layout_kind: str = ""
    target_root_hint: str = ""
    selected_variant: Optional[str] = None
    selected_entries: list[str] = field(default_factory=list)
    installed_archive_entries: list[str] = field(default_factory=list)
    layout_warnings: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "mod_id": self.mod_id,
            "timestamp": self.timestamp,
            "target": self.target,
            "action": self.action,
            "display_name": self.display_name,
            "source_archive": self.source_archive,
            "archive_hash": self.archive_hash,
            "install_kind": self.install_kind,
            "layout_kind": self.layout_kind,
            "target_root_hint": self.target_root_hint,
            "selected_variant": self.selected_variant,
            "selected_entries": self.selected_entries,
            "installed_archive_entries": self.installed_archive_entries,
            "layout_warnings": self.layout_warnings,
            "notes": self.notes,
            "files": [
                {
                    "source_archive_path": f.source_archive_path,
                    "dest_path": f.dest_path,
                    "backup_path": f.backup_path,
                    "was_overwrite": f.was_overwrite,
                }
                for f in self.files
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> DeploymentRecord:
        files = [
            DeployedFile(
                source_archive_path=f["source_archive_path"],
                dest_path=f["dest_path"],
                backup_path=f.get("backup_path"),
                was_overwrite=f.get("was_overwrite", False),
            )
            for f in d.get("files", [])
        ]
        return cls(
            mod_id=d["mod_id"],
            timestamp=d.get("timestamp", ""),
            files=files,
            target=d.get("target", ""),
            action=d.get("action", "install"),
            display_name=d.get("display_name", ""),
            source_archive=d.get("source_archive", ""),
            archive_hash=d.get("archive_hash"),
            install_kind=d.get("install_kind", "standard_mod"),
            layout_kind=d.get("layout_kind", ""),
            target_root_hint=d.get("target_root_hint", ""),
            selected_variant=d.get("selected_variant"),
            selected_entries=d.get("selected_entries", []),
            installed_archive_entries=d.get("installed_archive_entries", []),
            layout_warnings=d.get("layout_warnings", []),
            notes=d.get("notes", ""),
        )
