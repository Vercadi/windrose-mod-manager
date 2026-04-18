from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable, Optional


class InstallTarget(Enum):
    CLIENT = "client"
    SERVER = "server"
    DEDICATED_SERVER = "dedicated_server"
    BOTH = "both"


TARGET_DISPLAY_LABELS = {
    "client": "Client",
    "server": "Local Server",
    "dedicated_server": "Dedicated Server",
    "hosted": "Hosted Server",
    "both": "Client + Local Server",
}


def expand_target_values(targets: Iterable[str]) -> set[str]:
    expanded = {value for value in targets if value and value != "both"}
    has_both = any(value == "both" for value in targets)
    if has_both:
        expanded.update({"client", "server"})
    return expanded


def target_value_label(target: str) -> str:
    normalized = (target or "").strip()
    return TARGET_DISPLAY_LABELS.get(normalized, normalized.replace("_", " ").title() or "Unknown")


def install_target_label(target: InstallTarget) -> str:
    return target_value_label(target.value)


def summarize_target_values(targets: Iterable[str]) -> str:
    expanded = expand_target_values(targets)
    if not expanded:
        return "Hosted Server"
    if expanded == {"client", "server"}:
        return "Client + Local Server"
    if expanded == {"client", "dedicated_server"}:
        return "Client + Dedicated Server"
    ordered = [
        TARGET_DISPLAY_LABELS[key]
        for key in ("client", "server", "dedicated_server", "hosted")
        if key in expanded
    ]
    return " + ".join(ordered) if ordered else "Unknown"


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
