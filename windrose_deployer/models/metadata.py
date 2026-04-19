from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModMetadata:
    """Optional upstream/source metadata for archives and installs."""

    nexus_mod_url: str = ""
    nexus_mod_id: str = ""
    nexus_file_id: str = ""
    version_tag: str = ""
    source_label: str = ""
    author_label: str = ""

    def is_empty(self) -> bool:
        return not any(
            [
                self.nexus_mod_url,
                self.nexus_mod_id,
                self.nexus_file_id,
                self.version_tag,
                self.source_label,
                self.author_label,
            ]
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "nexus_mod_url": self.nexus_mod_url,
            "nexus_mod_id": self.nexus_mod_id,
            "nexus_file_id": self.nexus_file_id,
            "version_tag": self.version_tag,
            "source_label": self.source_label,
            "author_label": self.author_label,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "ModMetadata":
        data = data or {}
        return cls(
            nexus_mod_url=str(data.get("nexus_mod_url", "") or ""),
            nexus_mod_id=str(data.get("nexus_mod_id", "") or ""),
            nexus_file_id=str(data.get("nexus_file_id", "") or ""),
            version_tag=str(data.get("version_tag", "") or ""),
            source_label=str(data.get("source_label", "") or ""),
            author_label=str(data.get("author_label", "") or ""),
        )

    @classmethod
    def from_legacy_fields(cls, data: dict) -> "ModMetadata":
        return cls(
            nexus_mod_url=str(data.get("nexus_mod_url", "") or ""),
            nexus_mod_id=str(data.get("nexus_mod_id", "") or ""),
            nexus_file_id=str(data.get("nexus_file_id", "") or ""),
            version_tag=str(data.get("version_tag", "") or ""),
            source_label=str(data.get("source_label", "") or ""),
            author_label=str(data.get("author_label", "") or ""),
        )
