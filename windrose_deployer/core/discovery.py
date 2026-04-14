"""Auto-detect Windrose installation paths."""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from ..models.app_paths import AppPaths

log = logging.getLogger(__name__)

STEAM_COMMON_DIRS: list[str] = [
    r"C:\Program Files (x86)\Steam\steamapps\common",
    r"C:\Program Files\Steam\steamapps\common",
    r"D:\Steam\steamapps\common",
    r"D:\SteamLibrary\steamapps\common",
    r"E:\Steam\steamapps\common",
    r"E:\SteamLibrary\steamapps\common",
    r"F:\Steam\steamapps\common",
    r"F:\SteamLibrary\steamapps\common",
    r"G:\Steam\steamapps\common",
    r"G:\SteamLibrary\steamapps\common",
]

GAME_FOLDER_NAME = "Windrose"
CLIENT_EXE = "Windrose.exe"
SERVER_EXE = "WindroseServer.exe"
SERVER_DESC = "ServerDescription.json"
LOCAL_APP_DATA_SUBPATH = Path("R5") / "Saved"


def discover_client_root() -> Optional[Path]:
    """Search common Steam library locations for the Windrose client."""
    for base in STEAM_COMMON_DIRS:
        candidate = Path(base) / GAME_FOLDER_NAME
        if _validate_client_root(candidate):
            log.info("Discovered client root: %s", candidate)
            return candidate
    log.warning("Could not auto-discover Windrose client root.")
    return None


def discover_server_root(client_root: Optional[Path] = None) -> Optional[Path]:
    """Locate the dedicated server install relative to the client root."""
    if client_root is None:
        return None
    candidate = client_root / "R5" / "Builds" / "WindowsServer"
    if _validate_server_root(candidate):
        log.info("Discovered server root: %s", candidate)
        return candidate
    log.warning("Server root not found under client root.")
    return None


def discover_local_config() -> Optional[Path]:
    """Find the local config directory (%LOCALAPPDATA%/R5/Saved/Config/Windows)."""
    local = _local_appdata()
    if local is None:
        return None
    candidate = local / "R5" / "Saved" / "Config" / "Windows"
    if candidate.is_dir():
        log.info("Discovered local config: %s", candidate)
        return candidate
    log.warning("Local config directory not found: %s", candidate)
    return None


def discover_local_save_root() -> Optional[Path]:
    """Find the local save root (%LOCALAPPDATA%/R5/Saved)."""
    local = _local_appdata()
    if local is None:
        return None
    candidate = local / "R5" / "Saved"
    if candidate.is_dir():
        log.info("Discovered local save root: %s", candidate)
        return candidate
    log.warning("Local save root not found: %s", candidate)
    return None


def discover_all(known_client: Optional[Path] = None) -> AppPaths:
    """Run full discovery and return an AppPaths with all found paths."""
    client = known_client if known_client and _validate_client_root(known_client) else discover_client_root()
    server = discover_server_root(client)
    local_config = discover_local_config()
    local_save = discover_local_save_root()

    return AppPaths(
        client_root=client,
        server_root=server,
        local_config=local_config,
        local_save_root=local_save,
    )


# ------------------------------------------------------------------ helpers


def _validate_client_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    has_exe = (path / CLIENT_EXE).is_file()
    has_r5 = (path / "R5").is_dir()
    return has_exe and has_r5


def _validate_server_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    has_exe = (path / SERVER_EXE).is_file()
    return has_exe


def _local_appdata() -> Optional[Path]:
    val = os.environ.get("LOCALAPPDATA")
    if val:
        return Path(val)
    return None
