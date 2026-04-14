"""Resolve deployment target paths for a given mod install."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..models.app_paths import AppPaths
from ..models.archive_info import ArchiveInfo
from ..models.mod_install import InstallTarget

log = logging.getLogger(__name__)


def resolve_pak_target(paths: AppPaths, target: InstallTarget) -> list[Path]:
    """Return the list of pak target directories for the given install target."""
    targets: list[Path] = []
    if target in (InstallTarget.CLIENT, InstallTarget.BOTH):
        if paths.client_mods:
            targets.append(paths.client_mods)
    if target in (InstallTarget.SERVER, InstallTarget.BOTH):
        if paths.server_mods:
            targets.append(paths.server_mods)
    return targets


def resolve_loose_target(paths: AppPaths, target: InstallTarget, info: ArchiveInfo) -> list[Path]:
    """Return the list of root directories for loose-file deployment."""
    targets: list[Path] = []
    if target in (InstallTarget.CLIENT, InstallTarget.BOTH):
        if paths.client_root:
            targets.append(paths.client_root)
    if target in (InstallTarget.SERVER, InstallTarget.BOTH):
        if paths.server_root:
            targets.append(paths.server_root)
    return targets


def strip_archive_prefix(entry_path: str, prefix: str) -> str:
    """Remove a leading archive prefix from an entry path."""
    if prefix and entry_path.startswith(prefix):
        return entry_path[len(prefix):]
    return entry_path
