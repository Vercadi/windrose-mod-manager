from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Optional


class ArchiveType(Enum):
    PAK_ONLY = "pak_only"
    LOOSE_FILES = "loose_files"
    MIXED = "mixed"
    MULTI_VARIANT_PAK = "multi_variant_pak"
    UNKNOWN = "unknown"


@dataclass
class ArchiveEntry:
    """A single entry inside an archive."""
    path: str
    is_dir: bool = False
    size: int = 0

    @property
    def pure_path(self) -> PurePosixPath:
        return PurePosixPath(self.path)

    @property
    def suffix(self) -> str:
        return self.pure_path.suffix.lower()

    @property
    def is_pak(self) -> bool:
        return self.suffix == ".pak"

    @property
    def is_utoc(self) -> bool:
        return self.suffix == ".utoc"

    @property
    def is_ucas(self) -> bool:
        return self.suffix == ".ucas"

    @property
    def is_unreal_asset(self) -> bool:
        return self.is_pak or self.is_utoc or self.is_ucas


@dataclass
class VariantGroup:
    """A group of mutually exclusive pak variants detected in an archive."""
    base_name: str
    variants: list[ArchiveEntry] = field(default_factory=list)

    @property
    def variant_names(self) -> list[str]:
        return [PurePosixPath(v.path).name for v in self.variants]


@dataclass
class ArchiveInfo:
    """Full analysis of an archive's contents."""
    archive_path: str
    archive_type: ArchiveType = ArchiveType.UNKNOWN
    entries: list[ArchiveEntry] = field(default_factory=list)
    pak_entries: list[ArchiveEntry] = field(default_factory=list)
    loose_entries: list[ArchiveEntry] = field(default_factory=list)
    companion_entries: list[ArchiveEntry] = field(default_factory=list)
    variant_groups: list[VariantGroup] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dependency_warnings: list[str] = field(default_factory=list)
    suggested_target: Optional[str] = None
    content_category: str = "standard_mod"
    install_kind: str = "standard_mod"
    framework_name: str = ""
    likely_destinations: list[str] = field(default_factory=list)
    root_prefix: str = ""

    @property
    def total_files(self) -> int:
        return len([e for e in self.entries if not e.is_dir])

    @property
    def has_variants(self) -> bool:
        return len(self.variant_groups) > 0

    def to_dict(self) -> dict:
        return {
            "archive_path": self.archive_path,
            "archive_type": self.archive_type.value,
            "total_files": self.total_files,
            "pak_count": len(self.pak_entries),
            "loose_count": len(self.loose_entries),
            "companion_count": len(self.companion_entries),
            "variant_groups": len(self.variant_groups),
            "warnings": self.warnings,
            "dependency_warnings": self.dependency_warnings,
            "suggested_target": self.suggested_target,
            "content_category": self.content_category,
            "install_kind": self.install_kind,
            "framework_name": self.framework_name,
            "likely_destinations": list(self.likely_destinations),
            "root_prefix": self.root_prefix,
        }
