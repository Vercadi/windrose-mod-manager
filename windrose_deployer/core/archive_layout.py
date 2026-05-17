"""Archive layout classification helpers.

This module sits one layer above the older ``ArchiveInfo`` buckets.  The
inspector still records pak/loose/framework facts, while this layer answers the
user-facing planning question: what kind of package is this, what is actually
installable, and where should it probably go?
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Iterable

from ..models.archive_info import ArchiveEntry, ArchiveInfo, VariantGroup
from .framework_deployment_planner import framework_entry_relative_path


class ArchiveLayoutKind(str, Enum):
    STANDARD_PAK = "standard_pak_archive"
    MULTI_PAK_BUNDLE = "multi_pak_bundle"
    MULTI_VARIANT_PAK = "multi_variant_pak_archive"
    UE4SS_MOD = "ue4ss_mod_archive"
    UE4SS_RUNTIME = "ue4ss_runtime_archive"
    UE4SS_SHIM_RUNTIME = "ue4ss_shim_runtime_archive"
    CONFIG_ONLY = "config_only_archive"
    MIXED = "mixed_archive"
    UNKNOWN = "unknown_archive"


@dataclass(frozen=True)
class ArchiveComponentGroup:
    """A deployable group that should stay together when selected."""

    name: str
    entries: tuple[ArchiveEntry, ...] = field(default_factory=tuple)
    required: bool = True
    reason: str = ""

    @property
    def entry_paths(self) -> tuple[str, ...]:
        return tuple(entry.path for entry in self.entries)


@dataclass(frozen=True)
class ArchiveLayout:
    """Classification result shared by reports, diagnostics, and future UI."""

    kind: ArchiveLayoutKind
    installable_files: tuple[ArchiveEntry, ...] = field(default_factory=tuple)
    support_files: tuple[ArchiveEntry, ...] = field(default_factory=tuple)
    config_files: tuple[ArchiveEntry, ...] = field(default_factory=tuple)
    target_root_hint: str = ""
    requires_user_choice: bool = False
    variant_groups: tuple[VariantGroup, ...] = field(default_factory=tuple)
    component_groups: tuple[ArchiveComponentGroup, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def installable_paths(self) -> tuple[str, ...]:
        return tuple(entry.path for entry in self.installable_files)


CONFIG_SUFFIXES = {".ini", ".json", ".cfg", ".conf", ".toml", ".yaml", ".yml"}
CONFIG_NAMES = {"enabled.txt", "mods.txt", "settings.ini", "ue4ss-settings.ini", "ue4ss.ini"}
SUPPORT_NAMES = {
    "changelog.md",
    "changelog.txt",
    "icon.png",
    "license",
    "license.md",
    "license.txt",
    "manifest.json",
    "readme.md",
    "readme.txt",
    "thunderstore.toml",
}
SUPPORT_SUFFIXES = {".md"}
UE4SS_SHIM_NAMES = {"dwmapi.dll", "dwmappi.dll", "xinput1_3.dll"}
UE4SS_CORE_NAMES = {"ue4ss.dll", "ue4ss-settings.ini", "ue4ss.ini"}


def classify_archive_layout(info: ArchiveInfo) -> ArchiveLayout:
    """Return a richer layout classification for an inspected archive."""
    files = tuple(entry for entry in info.entries if not entry.is_dir)
    support_files = tuple(entry for entry in files if is_support_file(entry))
    config_files = tuple(entry for entry in files if is_config_file(entry))
    warnings: list[str] = []

    if info.install_kind == "ue4ss_runtime":
        return _classify_ue4ss_runtime(info, files, support_files, config_files, warnings)
    if info.install_kind == "ue4ss_mod":
        return _classify_ue4ss_mod(info, files, support_files, config_files, warnings)

    pak_installables = tuple(info.pak_entries + info.companion_entries)
    component_groups = tuple(_pak_component_groups(info))
    loose_installables = tuple(
        entry
        for entry in info.loose_entries
        if entry not in support_files and entry not in config_files
    )

    if info.variant_groups:
        warnings.append("Variant archive: choose one variant, or explicitly choose all variants for bundle-style packages.")
        if loose_installables or config_files:
            warnings.append("Variant archive also contains loose/config files; review destinations before installing.")
        return ArchiveLayout(
            kind=ArchiveLayoutKind.MULTI_VARIANT_PAK,
            installable_files=pak_installables + loose_installables,
            support_files=support_files,
            config_files=config_files,
            target_root_hint="paks",
            requires_user_choice=True,
            variant_groups=tuple(info.variant_groups),
            component_groups=component_groups,
            warnings=tuple(_dedupe(warnings)),
        )

    if info.pak_entries:
        if loose_installables or config_files:
            warnings.append("Mixed archive layout: contains pak files plus loose/config files.")
            warnings.append("Review destinations before installing so support/config files are not deployed accidentally.")
            return ArchiveLayout(
                kind=ArchiveLayoutKind.MIXED,
                installable_files=pak_installables + loose_installables,
                support_files=support_files,
                config_files=config_files,
                target_root_hint="manual-review",
                requires_user_choice=True,
                component_groups=component_groups,
                warnings=tuple(_dedupe(warnings)),
            )
        kind = ArchiveLayoutKind.MULTI_PAK_BUNDLE if len(info.pak_entries) > 1 else ArchiveLayoutKind.STANDARD_PAK
        return ArchiveLayout(
            kind=kind,
            installable_files=pak_installables,
            support_files=support_files,
            config_files=config_files,
            target_root_hint="paks",
            requires_user_choice=False,
            component_groups=component_groups,
            warnings=tuple(_dedupe(warnings)),
        )

    if files and len(config_files) + len(support_files) == len(files) and config_files:
        warnings.append("Config-only archive: use a config workflow or review paths before writing files.")
        return ArchiveLayout(
            kind=ArchiveLayoutKind.CONFIG_ONLY,
            installable_files=tuple(),
            support_files=support_files,
            config_files=config_files,
            target_root_hint="config",
            requires_user_choice=True,
            warnings=tuple(_dedupe(warnings)),
        )

    if loose_installables:
        warnings.append("Loose-file archive: review root-relative destinations before installing.")
        return ArchiveLayout(
            kind=ArchiveLayoutKind.MIXED,
            installable_files=loose_installables,
            support_files=support_files,
            config_files=config_files,
            target_root_hint=info.suggested_target or "root",
            requires_user_choice=True,
            warnings=tuple(_dedupe(warnings)),
        )

    if support_files:
        warnings.append("Metadata/support-only archive: no installable Windrose files were found.")
    else:
        warnings.append("No installable Windrose files were found.")
    return ArchiveLayout(
        kind=ArchiveLayoutKind.UNKNOWN,
        installable_files=tuple(),
        support_files=support_files,
        config_files=config_files,
        target_root_hint="none",
        requires_user_choice=False,
        warnings=tuple(_dedupe(warnings)),
    )


def is_config_file(entry: ArchiveEntry) -> bool:
    name = entry.pure_path.name.lower()
    if name in SUPPORT_NAMES:
        return False
    return name in CONFIG_NAMES or entry.suffix in CONFIG_SUFFIXES


def is_support_file(entry: ArchiveEntry) -> bool:
    name = entry.pure_path.name.lower()
    return name in SUPPORT_NAMES or entry.suffix in SUPPORT_SUFFIXES


def layout_display_name(kind: ArchiveLayoutKind | str) -> str:
    value = kind.value if isinstance(kind, ArchiveLayoutKind) else str(kind)
    labels = {
        ArchiveLayoutKind.STANDARD_PAK.value: "Standard Pak Archive",
        ArchiveLayoutKind.MULTI_PAK_BUNDLE.value: "Multi Pak Bundle",
        ArchiveLayoutKind.MULTI_VARIANT_PAK.value: "Multi Variant Pak",
        ArchiveLayoutKind.UE4SS_MOD.value: "UE4SS Mod Archive",
        ArchiveLayoutKind.UE4SS_RUNTIME.value: "UE4SS Runtime Archive",
        ArchiveLayoutKind.UE4SS_SHIM_RUNTIME.value: "UE4SS Shim Runtime Archive",
        ArchiveLayoutKind.CONFIG_ONLY.value: "Config Only Archive",
        ArchiveLayoutKind.MIXED.value: "Mixed Archive",
        ArchiveLayoutKind.UNKNOWN.value: "Unknown Archive",
    }
    return labels.get(value, value.replace("_", " ").title())


def _classify_ue4ss_runtime(
    info: ArchiveInfo,
    files: tuple[ArchiveEntry, ...],
    support_files: tuple[ArchiveEntry, ...],
    config_files: tuple[ArchiveEntry, ...],
    warnings: list[str],
) -> ArchiveLayout:
    installable = tuple(entry for entry in files if framework_entry_relative_path(info, entry) is not None)
    kind = ArchiveLayoutKind.UE4SS_SHIM_RUNTIME if _looks_like_ue4ss_shim(info, files) else ArchiveLayoutKind.UE4SS_RUNTIME
    if kind == ArchiveLayoutKind.UE4SS_SHIM_RUNTIME:
        warnings.append("UE4SS shim/runtime archive detected; install to R5/Binaries/Win64 only when replacing the runtime is intended.")
    else:
        warnings.append("UE4SS runtime archive detected; install to R5/Binaries/Win64 for the selected target.")
    if len(installable) != len([entry for entry in files if entry not in support_files]):
        warnings.append("Some runtime archive files look like support files and will not be treated as runtime payload.")
    return ArchiveLayout(
        kind=kind,
        installable_files=installable,
        support_files=support_files,
        config_files=config_files,
        target_root_hint=r"R5\Binaries\Win64",
        requires_user_choice=False,
        component_groups=(
            ArchiveComponentGroup(
                name="UE4SS runtime",
                entries=installable,
                reason="Runtime files must stay together.",
            ),
        ) if installable else tuple(),
        warnings=tuple(_dedupe(warnings)),
    )


def _classify_ue4ss_mod(
    info: ArchiveInfo,
    files: tuple[ArchiveEntry, ...],
    support_files: tuple[ArchiveEntry, ...],
    config_files: tuple[ArchiveEntry, ...],
    warnings: list[str],
) -> ArchiveLayout:
    installable = tuple(entry for entry in files if framework_entry_relative_path(info, entry) is not None)
    if not installable:
        warnings.append("UE4SS mod markers were detected, but no installable UE4SS mod files could be mapped.")
    return ArchiveLayout(
        kind=ArchiveLayoutKind.UE4SS_MOD,
        installable_files=installable,
        support_files=support_files,
        config_files=config_files,
        target_root_hint=r"R5\Binaries\Win64\ue4ss\Mods",
        requires_user_choice=False,
        component_groups=(
            ArchiveComponentGroup(
                name=_ue4ss_mod_group_name(info, installable),
                entries=installable,
                reason="UE4SS mod files deploy under ue4ss/Mods.",
            ),
        ) if installable else tuple(),
        warnings=tuple(_dedupe(warnings)),
    )


def _pak_component_groups(info: ArchiveInfo) -> list[ArchiveComponentGroup]:
    companions_by_stem: dict[str, list[ArchiveEntry]] = {}
    for entry in info.companion_entries:
        companions_by_stem.setdefault(entry.pure_path.stem, []).append(entry)

    groups: list[ArchiveComponentGroup] = []
    for pak in info.pak_entries:
        members = [pak, *companions_by_stem.get(pak.pure_path.stem, [])]
        groups.append(
            ArchiveComponentGroup(
                name=pak.pure_path.stem,
                entries=tuple(members),
                reason="Pak and Unreal companion files must stay together.",
            )
        )
    return groups


def _looks_like_ue4ss_shim(info: ArchiveInfo, files: Iterable[ArchiveEntry]) -> bool:
    source_name = Path(info.archive_path).name.lower()
    names = {entry.pure_path.name.lower() for entry in files}
    paths = {str(entry.pure_path).replace("\\", "/").lower() for entry in files}
    if "shim" in source_name or any("shim" in path for path in paths):
        return True
    has_shim_loader = bool(names & UE4SS_SHIM_NAMES)
    has_core = bool(names & UE4SS_CORE_NAMES) or any("/ue4ss/" in path or path.startswith("ue4ss/") for path in paths)
    return has_shim_loader and not has_core


def _ue4ss_mod_group_name(info: ArchiveInfo, installable: tuple[ArchiveEntry, ...]) -> str:
    for entry in installable:
        parts = PurePosixPath(entry.path).parts
        lowered = [part.lower() for part in parts]
        if "mods" in lowered:
            index = lowered.index("mods")
            if index + 1 < len(parts):
                return parts[index + 1]
    root = PurePosixPath(info.root_prefix.rstrip("/")).name
    return root or Path(info.archive_path).stem


def _dedupe(lines: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in lines:
        line = str(raw).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result
