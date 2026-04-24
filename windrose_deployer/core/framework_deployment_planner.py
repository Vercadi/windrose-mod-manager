"""Path planning helpers for UE4SS and server-framework installs."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional

from ..models.app_paths import AppPaths
from ..models.archive_info import ArchiveEntry, ArchiveInfo
from ..models.mod_install import InstallTarget
from .target_resolver import strip_archive_prefix

FRAMEWORK_INSTALL_KINDS = {"ue4ss_runtime", "ue4ss_mod", "rcon_mod", "windrose_plus"}
UE4SS_CORE_FILE_NAMES = {
    "ue4ss.dll",
    "ue4ss-settings.ini",
    "ue4ss.ini",
    "dwmapi.dll",
    "dwmappi.dll",
    "xinput1_3.dll",
}
UE4SS_MOD_ROOT_MARKERS = {"scripts", "dlls", "enabled.txt", "settings.ini"}


def is_framework_install_kind(value: str | None) -> bool:
    return (value or "standard_mod") in FRAMEWORK_INSTALL_KINDS


def framework_install_root(paths: AppPaths, target: InstallTarget, install_kind: str) -> Optional[Path]:
    target_root = _target_root(paths, target)
    if target_root is None:
        return None
    if install_kind == "windrose_plus":
        if target == InstallTarget.CLIENT:
            return None
        return target_root
    win64 = target_root / "R5" / "Binaries" / "Win64"
    if install_kind == "ue4ss_runtime":
        return win64
    if install_kind in {"ue4ss_mod", "rcon_mod"}:
        return win64 / "ue4ss" / "Mods"
    return None


def remote_framework_install_root(remote_root: str, install_kind: str) -> str:
    root = PurePosixPath((remote_root or ".").replace("\\", "/"))
    if install_kind == "windrose_plus":
        return str(root)
    win64 = root.joinpath("R5", "Binaries", "Win64")
    if install_kind == "ue4ss_runtime":
        return str(win64)
    if install_kind in {"ue4ss_mod", "rcon_mod"}:
        return str(win64.joinpath("ue4ss", "Mods"))
    return str(root)


def framework_entry_relative_path(info: ArchiveInfo, entry: ArchiveEntry) -> str | None:
    if info.install_kind == "ue4ss_runtime":
        return _runtime_relative_path(info, entry)
    if info.install_kind in {"ue4ss_mod", "rcon_mod"}:
        return _ue4ss_mod_relative_path(info, entry)
    if info.install_kind == "windrose_plus":
        return _windrose_plus_relative_path(info, entry)
    return None


def _target_root(paths: AppPaths, target: InstallTarget) -> Optional[Path]:
    if target == InstallTarget.CLIENT:
        return paths.client_root
    if target == InstallTarget.SERVER:
        return paths.server_root
    if target == InstallTarget.DEDICATED_SERVER:
        return paths.dedicated_server_root
    return None


def _parts_after(parts: tuple[str, ...], marker: tuple[str, ...]) -> tuple[str, ...] | None:
    lowered = tuple(part.lower() for part in parts)
    marker_lowered = tuple(part.lower() for part in marker)
    length = len(marker_lowered)
    for index in range(0, len(parts) - length + 1):
        if lowered[index:index + length] == marker_lowered:
            return parts[index + length:]
    return None


def _stripped_parts(info: ArchiveInfo, entry: ArchiveEntry) -> tuple[str, ...]:
    stripped = strip_archive_prefix(entry.path, info.root_prefix)
    return PurePosixPath(stripped).parts


def _runtime_relative_path(info: ArchiveInfo, entry: ArchiveEntry) -> str | None:
    parts = PurePosixPath(entry.path).parts
    for marker in (("R5", "Binaries", "Win64"), ("Binaries", "Win64"), ("Win64",)):
        rel_parts = _parts_after(parts, marker)
        if rel_parts:
            return str(PurePosixPath(*rel_parts))

    stripped_parts = _stripped_parts(info, entry)
    if not stripped_parts:
        return None
    first = stripped_parts[0].lower()
    name = stripped_parts[-1].lower()
    if first == "ue4ss" or name in UE4SS_CORE_FILE_NAMES:
        return str(PurePosixPath(*stripped_parts))
    return None


def _ue4ss_mod_relative_path(info: ArchiveInfo, entry: ArchiveEntry) -> str | None:
    raw_parts = PurePosixPath(entry.path).parts
    after_mods = _parts_after(raw_parts, ("ue4ss", "Mods"))
    if after_mods:
        return str(PurePosixPath(*after_mods))

    stripped_parts = _stripped_parts(info, entry)
    if not stripped_parts:
        return None

    first = stripped_parts[0].lower()
    if first in UE4SS_MOD_ROOT_MARKERS:
        mod_name = PurePosixPath(info.root_prefix.rstrip("/")).name or PurePosixPath(info.archive_path).stem
        return str(PurePosixPath(mod_name, *stripped_parts))

    if _looks_like_ue4ss_mod_parts(stripped_parts):
        return str(PurePosixPath(*stripped_parts))

    return None


def _windrose_plus_relative_path(info: ArchiveInfo, entry: ArchiveEntry) -> str | None:
    stripped_parts = _stripped_parts(info, entry)
    if not stripped_parts:
        return None
    return str(PurePosixPath(*stripped_parts))


def _looks_like_ue4ss_mod_parts(parts: tuple[str, ...]) -> bool:
    if len(parts) < 2:
        return False
    lowered = tuple(part.lower() for part in parts)
    return (
        "scripts" in lowered
        or "dlls" in lowered
        or lowered[-1] in {"enabled.txt", "settings.ini"}
    )
