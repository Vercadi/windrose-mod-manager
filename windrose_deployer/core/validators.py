"""Path and configuration validators."""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def validate_client_root(path: Path) -> tuple[bool, str]:
    if not path.is_dir():
        return False, f"Directory does not exist: {path}"
    if not (path / "Windrose.exe").is_file():
        return False, "Windrose.exe not found."
    if not (path / "R5").is_dir():
        return False, "R5 directory not found."
    return True, "Valid client root."


def validate_server_root(path: Path) -> tuple[bool, str]:
    if not path.is_dir():
        return False, f"Directory does not exist: {path}"
    if not (path / "WindroseServer.exe").is_file():
        return False, "WindroseServer.exe not found."
    if not (path / "R5").is_dir():
        return False, "R5 directory not found."
    return True, "Valid server root."


def validate_local_config(path: Path) -> tuple[bool, str]:
    if not path.is_dir():
        return False, f"Directory does not exist: {path}"
    has_engine = (path / "Engine.ini").is_file()
    has_game = (path / "GameUserSettings.ini").is_file()
    if not (has_engine or has_game):
        return False, "Neither Engine.ini nor GameUserSettings.ini found."
    return True, "Valid local config directory."


def validate_pak_target(path: Path) -> tuple[bool, str]:
    """Check that the parent Paks directory exists or can be created."""
    paks_dir = path if path.name != "~mods" else path.parent
    if paks_dir.is_dir():
        return True, "Pak target exists."
    if paks_dir.parent.is_dir():
        return True, "Pak target parent exists — target can be created."
    return False, f"Pak target parent structure missing: {paks_dir.parent}"
