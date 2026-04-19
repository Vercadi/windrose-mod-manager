from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from .metadata import ModMetadata


@dataclass
class ProfileEntry:
    display_name: str
    source_archive: str
    targets: list[str] = field(default_factory=list)
    selected_variant: str = ""
    mod_id: str = ""
    enabled: bool = True
    component_entries: list[str] = field(default_factory=list)
    metadata: ModMetadata = field(default_factory=ModMetadata)

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "source_archive": self.source_archive,
            "targets": list(self.targets),
            "selected_variant": self.selected_variant,
            "mod_id": self.mod_id,
            "enabled": self.enabled,
            "component_entries": list(self.component_entries),
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileEntry":
        return cls(
            display_name=str(data.get("display_name", "") or ""),
            source_archive=str(data.get("source_archive", "") or ""),
            targets=list(data.get("targets", []) or []),
            selected_variant=str(data.get("selected_variant", "") or ""),
            mod_id=str(data.get("mod_id", "") or ""),
            enabled=bool(data.get("enabled", True)),
            component_entries=list(data.get("component_entries", []) or []),
            metadata=ModMetadata.from_dict(data.get("metadata")),
        )


@dataclass
class Profile:
    profile_id: str
    name: str
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    entries: list[ProfileEntry] = field(default_factory=list)
    server_settings_snapshot: dict = field(default_factory=dict)
    world_settings_snapshot: dict = field(default_factory=dict)

    @classmethod
    def new(cls, name: str, notes: str = "") -> "Profile":
        return cls(profile_id=uuid4().hex, name=name, notes=notes)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "notes": self.notes,
            "created_at": self.created_at,
            "entries": [entry.to_dict() for entry in self.entries],
            "server_settings_snapshot": self.server_settings_snapshot,
            "world_settings_snapshot": self.world_settings_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        if not data.get("name") and not data.get("profile_id"):
            raise ValueError("Profile entry is missing name/profile_id")
        return cls(
            profile_id=str(data.get("profile_id", "") or uuid4().hex),
            name=str(data.get("name", "Profile") or "Profile"),
            notes=str(data.get("notes", "") or ""),
            created_at=str(data.get("created_at", "") or datetime.now().isoformat()),
            entries=[ProfileEntry.from_dict(entry) for entry in data.get("entries", []) or []],
            server_settings_snapshot=dict(data.get("server_settings_snapshot", {}) or {}),
            world_settings_snapshot=dict(data.get("world_settings_snapshot", {}) or {}),
        )
