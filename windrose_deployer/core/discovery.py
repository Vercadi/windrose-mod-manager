"""Auto-detect Windrose installation paths."""
from __future__ import annotations

import ctypes
import logging
import os
import string
import time
from pathlib import Path
from typing import Optional

from ..models.app_paths import AppPaths

log = logging.getLogger(__name__)

GAME_FOLDER_NAME = "Windrose"
DEDICATED_SERVER_FOLDER_NAME = "Windrose Dedicated Server"
CLIENT_EXE = "Windrose.exe"
SERVER_EXE = "WindroseServer.exe"
SERVER_DESC = "ServerDescription.json"
LEGACY_SERVER_SUBPATH = Path("R5") / "Builds" / "WindowsServer"
SERVER_RUNTIME_SUBPATH = Path("R5")
SERVER_SAVE_SUBPATH = SERVER_RUNTIME_SUBPATH / "Saved"
LOCAL_APP_DATA_SUBPATH = Path("R5") / "Saved"


def _available_drive_roots() -> list[str]:
    if os.name != "nt":
        return [r"C:\\"]
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return [fr"{letter}:\\" for letter in "CDEFGH"]

    roots: list[str] = []
    for index, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << index):
            roots.append(fr"{letter}:\\")
    return roots or [r"C:\\"]


def _build_steam_common_dirs() -> list[str]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        key = str(path)
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    for env_key in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        base = os.environ.get(env_key)
        if base:
            _add(Path(base) / "Steam" / "steamapps" / "common")

    for drive_root in _available_drive_roots():
        root = Path(drive_root)
        _add(root / "SteamLibrary" / "steamapps" / "common")
        _add(root / "Steam" / "steamapps" / "common")

    return [str(path) for path in candidates]


STEAM_COMMON_DIRS: list[str] = _build_steam_common_dirs()


def discover_client_root() -> Optional[Path]:
    """Search common Steam library locations for the Windrose client."""
    for base in STEAM_COMMON_DIRS:
        candidate = Path(base) / GAME_FOLDER_NAME
        if _validate_client_root(candidate):
            log.info("Discovered client root: %s", candidate)
            return candidate
    log.warning("Could not auto-discover Windrose client root.")
    return None


def discover_dedicated_server_root() -> Optional[Path]:
    """Locate the standalone Steam dedicated-server install."""
    for base in STEAM_COMMON_DIRS:
        candidate = Path(base) / DEDICATED_SERVER_FOLDER_NAME
        if _validate_server_root(candidate):
            log.info("Discovered standalone dedicated server root: %s", candidate)
            return candidate
    log.warning("Could not auto-discover Windrose standalone dedicated server root.")
    return None


def discover_bundled_server_root(client_root: Optional[Path] = None) -> Optional[Path]:
    """Locate the legacy bundled WindowsServer runtime inside the client install."""
    if client_root is None:
        log.warning("Could not auto-discover bundled WindowsServer root because no client root is set.")
        return None

    candidate = legacy_server_root(client_root)
    if _validate_server_root(candidate):
        log.info("Discovered bundled WindowsServer root: %s", candidate)
        return candidate
    log.warning("Could not auto-discover bundled WindowsServer root.")
    return None


def discover_server_root(client_root: Optional[Path] = None) -> Optional[Path]:
    """Compatibility wrapper for the bundled WindowsServer target."""
    return discover_bundled_server_root(client_root)


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


def discover_local_save_root(
    dedicated_server_root: Optional[Path] = None,
    server_root: Optional[Path] = None,
) -> Optional[Path]:
    """Find the preferred local server save root.

    Prefer <dedicated_server_root>/R5/Saved when a standalone dedicated server
    install exists. Fall back to the bundled WindowsServer root, then to the
    older %LOCALAPPDATA%/R5/Saved path.
    """
    active_server_root = dedicated_server_root or server_root
    if active_server_root is not None:
        candidate = server_save_root(active_server_root)
        if candidate.parent.is_dir():
            log.info("Discovered local server save root: %s", candidate)
            return candidate

    candidate = default_local_save_root()
    if candidate is None:
        return None
    if candidate.is_dir():
        log.info("Discovered local appdata save root: %s", candidate)
        return candidate
    log.warning("Local save root not found: %s", candidate)
    return None


def discover_all(known_client: Optional[Path] = None) -> AppPaths:
    """Run full discovery and return an AppPaths with all found paths."""
    started_at = time.perf_counter()
    client = known_client if known_client and _validate_client_root(known_client) else discover_client_root()
    bundled_server = discover_bundled_server_root(client)
    dedicated_server = discover_dedicated_server_root()
    local_config = discover_local_config()
    local_save = discover_local_save_root(dedicated_server, bundled_server)

    paths = AppPaths(
        client_root=client,
        server_root=bundled_server,
        dedicated_server_root=dedicated_server,
        local_config=local_config,
        local_save_root=local_save,
    )
    log.info("Path discovery timing | discover_all: %.1f ms", (time.perf_counter() - started_at) * 1000.0)
    return paths


def legacy_server_root(client_root: Path) -> Path:
    return client_root / LEGACY_SERVER_SUBPATH


def server_description_path(server_root: Path) -> Path:
    return server_root / SERVER_RUNTIME_SUBPATH / SERVER_DESC


def server_save_root(server_root: Path) -> Path:
    return server_root / SERVER_SAVE_SUBPATH


def is_legacy_server_root(path: Optional[Path], client_root: Optional[Path] = None) -> bool:
    if path is None:
        return False
    candidate = Path(path)
    if client_root is not None and candidate == legacy_server_root(client_root):
        return True
    suffix = [part.lower() for part in candidate.parts[-3:]]
    return suffix == ["r5", "builds", "windowsserver"]


def default_local_save_root() -> Optional[Path]:
    local = _local_appdata()
    if local is None:
        return None
    return local / LOCAL_APP_DATA_SUBPATH


def reconcile_paths(paths: AppPaths) -> tuple[AppPaths, bool]:
    """Reconcile saved paths with current discovery results.

    Existing installs may contain only one saved server root from the period
    where bundled WindowsServer and the standalone dedicated server app were
    collapsed into one setting. Split those safely, then fill in any missing
    paths from discovery.
    """
    started_at = time.perf_counter()
    current = AppPaths(
        client_root=paths.client_root,
        server_root=paths.server_root,
        dedicated_server_root=paths.dedicated_server_root,
        local_config=paths.local_config,
        local_save_root=paths.local_save_root,
        backup_dir=paths.backup_dir,
        data_dir=paths.data_dir,
    )
    changed = False

    current, migrated = _split_legacy_server_settings(current)
    changed = changed or migrated
    detected = AppPaths()

    needs_discovery = migrated
    needs_discovery = needs_discovery or current.client_root is None or not _validate_client_root(current.client_root)
    needs_discovery = needs_discovery or current.server_root is None or not _validate_server_root(current.server_root)
    needs_discovery = needs_discovery or current.dedicated_server_root is None or not _validate_server_root(current.dedicated_server_root)
    needs_discovery = needs_discovery or current.local_config is None or not current.local_config.is_dir()
    needs_discovery = needs_discovery or current.local_save_root is None
    needs_discovery = needs_discovery or (
        current.local_save_root is not None
        and not current.local_save_root.exists()
        and not current.local_save_root.parent.exists()
    )
    needs_discovery = needs_discovery or (
        current.local_save_root is not None
        and current.local_save_root == default_local_save_root()
    )

    if needs_discovery:
        detection_started_at = time.perf_counter()
        detected = discover_all(known_client=current.client_root)
        log.info(
            "Path discovery timing | reconcile_paths.detect: %.1f ms",
            (time.perf_counter() - detection_started_at) * 1000.0,
        )
    else:
        log.info("Path discovery timing | reconcile_paths.detect: skipped (saved paths already valid)")

    if detected.client_root and (
        current.client_root is None or not _validate_client_root(current.client_root)
    ):
        current.client_root = detected.client_root
        changed = True

    previous_server_root = current.server_root
    if detected.server_root and (
        current.server_root is None or not _validate_server_root(current.server_root)
    ):
        current.server_root = detected.server_root
        changed = True

    previous_dedicated_server_root = current.dedicated_server_root
    if detected.dedicated_server_root and (
        current.dedicated_server_root is None or not _validate_server_root(current.dedicated_server_root)
    ):
        current.dedicated_server_root = detected.dedicated_server_root
        changed = True

    if detected.local_config and (current.local_config is None or not current.local_config.is_dir()):
        current.local_config = detected.local_config
        changed = True

    if detected.local_save_root:
        should_update_save_root = False
        if current.local_save_root is None:
            should_update_save_root = True
        elif not current.local_save_root.exists() and not current.local_save_root.parent.exists():
            should_update_save_root = True
        elif (
            current.local_save_root != detected.local_save_root
            and current.local_save_root == default_local_save_root()
        ):
            should_update_save_root = True
        elif (
            previous_dedicated_server_root is not None
            and current.local_save_root == server_save_root(previous_dedicated_server_root)
            and current.local_save_root != detected.local_save_root
        ):
            should_update_save_root = True
        elif (
            previous_dedicated_server_root is None
            and previous_server_root is not None
            and current.local_save_root == server_save_root(previous_server_root)
            and current.local_save_root != detected.local_save_root
        ):
            should_update_save_root = True

        if should_update_save_root:
            current.local_save_root = detected.local_save_root
            changed = True

    log.info(
        "Path discovery timing | reconcile_paths.total: %.1f ms (changed=%s)",
        (time.perf_counter() - started_at) * 1000.0,
        changed,
    )
    return current, changed


def _split_legacy_server_settings(paths: AppPaths) -> tuple[AppPaths, bool]:
    """Migrate older settings where server_root was used for both meanings."""
    if paths.dedicated_server_root is not None or paths.server_root is None:
        return paths, False

    current_server_root = Path(paths.server_root)
    if not _validate_server_root(current_server_root):
        return paths, False
    if is_legacy_server_root(current_server_root, paths.client_root):
        return paths, False

    paths.dedicated_server_root = current_server_root
    bundled_root = legacy_server_root(paths.client_root) if paths.client_root else None
    if bundled_root is not None and _validate_server_root(bundled_root):
        paths.server_root = bundled_root
    else:
        paths.server_root = None
    return paths, True


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
    has_runtime = (path / SERVER_RUNTIME_SUBPATH).is_dir()
    return has_exe and has_runtime


def _local_appdata() -> Optional[Path]:
    val = os.environ.get("LOCALAPPDATA")
    if val:
        return Path(val)
    return None
