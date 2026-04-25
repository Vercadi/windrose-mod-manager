from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

from ..models.archive_info import ArchiveEntry


UE4SS_CORE_NAMES = {
    "ue4ss.dll",
    "ue4ss-settings.ini",
    "ue4ss.ini",
    "dwmapi.dll",
    "dwmappi.dll",
    "xinput1_3.dll",
}
UE4SS_MOD_MARKERS = {"enabled.txt", "settings.ini", "main.lua"}
UE4SS_MOD_FOLDER_MARKERS = {"scripts", "dlls"}
WINDROSE_PLUS_GENERATED_PAKS = {
    "windroseplus_multipliers_p.pak",
    "windroseplus_curvetables_p.pak",
}


@dataclass
class FrameworkAnalysis:
    category: str = "standard_mod"
    install_kind: str = "standard_mod"
    framework_name: str = ""
    detected_mod_name: str = ""
    likely_destinations: list[str] = field(default_factory=list)
    dependency_warnings: list[str] = field(default_factory=list)


def analyze_archive_framework(entries: Iterable[ArchiveEntry], *, archive_path: str = "") -> FrameworkAnalysis:
    entry_list = [entry for entry in entries if not entry.is_dir]
    names = [entry.pure_path.name.lower() for entry in entry_list]
    paths = [str(entry.pure_path).replace("\\", "/").lower() for entry in entry_list]
    joined_names = " ".join(names)
    source_name = Path(archive_path).name.lower()

    has_binaries = any("/binaries/win64/" in path or path.startswith("r5/binaries/win64/") for path in paths)
    has_ue4ss_folder = any("/ue4ss/" in path or path.startswith("ue4ss/") for path in paths)
    has_ue4ss_core = any(name in UE4SS_CORE_NAMES for name in names)
    has_ue4ss_mod_tree = any("/ue4ss/mods/" in path or path.startswith("ue4ss/mods/") for path in paths)
    has_root_ue4ss_mod = _has_root_ue4ss_mod_shape(entry_list)
    has_windrose_plus = _looks_like_windrose_plus(paths)
    has_rcon_mod = _looks_like_rcon_mod(paths, names, source_name)

    analysis = FrameworkAnalysis()

    if has_windrose_plus:
        analysis.category = "framework_mod"
        analysis.install_kind = "windrose_plus"
        analysis.framework_name = "WindrosePlus"
        analysis.detected_mod_name = "WindrosePlus"
        analysis.likely_destinations = [r"R5\Binaries\Win64\ue4ss\Mods", "server root"]
        analysis.dependency_warnings.append(
            "WindrosePlus requires UE4SS and is primarily a local Windows dedicated-server framework."
        )
        return analysis

    if has_rcon_mod:
        analysis.category = "framework_mod"
        analysis.install_kind = "rcon_mod"
        analysis.framework_name = "Windrose RCON"
        analysis.detected_mod_name = _detect_mod_name_from_paths(paths) or "WindroseRCON"
        analysis.likely_destinations = [r"R5\Binaries\Win64"]
        analysis.dependency_warnings.append(
            "Install on server targets only. Start the server once to generate windrosercon\\settings.ini, then configure port/password."
        )
        return analysis

    if has_ue4ss_core or (has_binaries and has_ue4ss_folder):
        analysis.category = "framework_runtime"
        analysis.install_kind = "ue4ss_runtime"
        analysis.framework_name = "UE4SS Runtime"
        analysis.likely_destinations = [r"R5\Binaries\Win64", "ue4ss/"]
        return analysis

    if has_ue4ss_mod_tree or has_root_ue4ss_mod or "ue4ss" in joined_names:
        analysis.category = "framework_mod"
        analysis.install_kind = "ue4ss_mod"
        analysis.framework_name = "UE4SS"
        analysis.detected_mod_name = _detect_mod_name_from_paths(paths)
        analysis.likely_destinations = ["ue4ss/Mods"]
        analysis.dependency_warnings.append(
            "Likely depends on the UE4SS runtime being installed first."
        )
        return analysis

    return analysis


def detect_framework_state(root: Path | None) -> dict[str, bool]:
    if root is None:
        return {
            "configured": False,
            "ue4ss_runtime": False,
            "ue4ss_partial": False,
            "rcon_mod": False,
            "rcon_configured": False,
            "rcon_missing_password": False,
            "windrose_plus": False,
            "windrose_plus_package": False,
            "windrose_plus_generated_paks": False,
            "windrose_plus_install_script": False,
            "windrose_plus_launch_wrapper": False,
            "windrose_plus_dashboard_launcher": False,
            "windrose_plus_config": False,
            "windrose_plus_partial": False,
        }

    win64 = root / "R5" / "Binaries" / "Win64"
    mods_dir = win64 / "ue4ss" / "Mods"
    injector_markers = [
        win64 / "dwmapi.dll",
        win64 / "dwmappi.dll",
        win64 / "xinput1_3.dll",
    ]
    core_markers = [
        win64 / "UE4SS.dll",
        win64 / "ue4ss.dll",
        win64 / "UE4SS-settings.ini",
        win64 / "ue4ss-settings.ini",
        win64 / "ue4ss" / "UE4SS.dll",
        win64 / "ue4ss" / "UE4SS-settings.ini",
    ]
    runtime_injector_present = any(path.exists() for path in injector_markers)
    runtime_core_present = any(path.exists() for path in core_markers)
    runtime_present = runtime_injector_present or runtime_core_present
    ue4ss_mods_present = _ue4ss_mods_present(mods_dir)
    windrose_plus_active = _folder_exists_case_insensitive(mods_dir, "WindrosePlus")
    windrose_plus_package_dir = _folder_exists_case_insensitive(root, "WindrosePlus") or _folder_exists_case_insensitive(root, "windrose_plus")
    windrose_plus_package = windrose_plus_active or windrose_plus_package_dir
    install_script = root / "install.ps1"
    launch_wrapper = root / "StartWindrosePlusServer.bat"
    dashboard_launcher = root / "windrose_plus" / "start_dashboard.bat"
    windrose_plus_config = root / "windrose_plus.json"
    generated_paks = _has_generated_windrose_plus_paks(root)
    rcon_primary_settings = win64 / "windrosercon" / "settings.ini"
    rcon_legacy_settings = mods_dir / "WindroseRCON" / "settings.ini"
    rcon_installed = (
        (win64 / "version.dll").is_file()
        or _dir_has_files(win64 / "windrosercon")
        or _folder_has_files_case_insensitive(mods_dir, "WindroseRCON")
    )
    rcon_configured, rcon_missing_password = _rcon_settings_state(rcon_primary_settings)
    if not rcon_configured:
        rcon_configured, rcon_missing_password = _rcon_settings_state(rcon_legacy_settings)
    windrose_plus_any = any(
        [
            windrose_plus_active,
            windrose_plus_package_dir,
            install_script.is_file(),
            launch_wrapper.is_file(),
            dashboard_launcher.is_file(),
            windrose_plus_config.is_file(),
            generated_paks,
        ]
    )
    return {
        "configured": True,
        "ue4ss_runtime": runtime_present,
        "ue4ss_partial": (runtime_present and not (runtime_injector_present and runtime_core_present)) or (ue4ss_mods_present and not runtime_present),
        "rcon_mod": rcon_installed,
        "rcon_configured": rcon_configured,
        "rcon_missing_password": rcon_missing_password,
        "windrose_plus": windrose_plus_active,
        "windrose_plus_package": windrose_plus_package,
        "windrose_plus_generated_paks": generated_paks,
        "windrose_plus_install_script": install_script.is_file(),
        "windrose_plus_launch_wrapper": launch_wrapper.is_file(),
        "windrose_plus_dashboard_launcher": dashboard_launcher.is_file(),
        "windrose_plus_config": windrose_plus_config.is_file(),
        "windrose_plus_partial": windrose_plus_any and not (windrose_plus_active and launch_wrapper.is_file()),
    }


def remote_framework_paths(remote_root: str) -> dict[str, str]:
    root = PurePosixPath((remote_root or ".").replace("\\", "/"))
    win64 = root.joinpath("R5", "Binaries", "Win64")
    mods = win64.joinpath("ue4ss", "Mods")
    return {
        "win64": str(win64),
        "ue4ss_mods": str(mods),
        "ue4ss_runtime_marker": str(win64.joinpath("dwmapi.dll")),
        "ue4ss_runtime_folder": str(win64.joinpath("ue4ss")),
        "ue4ss_runtime_dwmapi": str(win64.joinpath("dwmapi.dll")),
        "ue4ss_runtime_dwmappi": str(win64.joinpath("dwmappi.dll")),
        "ue4ss_runtime_xinput": str(win64.joinpath("xinput1_3.dll")),
        "ue4ss_runtime_dll": str(win64.joinpath("UE4SS.dll")),
        "ue4ss_runtime_settings": str(win64.joinpath("UE4SS-settings.ini")),
        "ue4ss_runtime_folder_dll": str(win64.joinpath("ue4ss", "UE4SS.dll")),
        "ue4ss_runtime_folder_settings": str(win64.joinpath("ue4ss", "UE4SS-settings.ini")),
        "rcon_mod": str(win64.joinpath("version.dll")),
        "rcon_dll": str(win64.joinpath("version.dll")),
        "rcon_config_dir": str(win64.joinpath("windrosercon")),
        "rcon_settings": str(win64.joinpath("windrosercon", "settings.ini")),
        "rcon_legacy_mod": str(mods.joinpath("WindroseRCON")),
        "rcon_legacy_settings": str(mods.joinpath("WindroseRCON", "settings.ini")),
        "windrose_plus": str(mods.joinpath("WindrosePlus")),
        "windrose_plus_package": str(root.joinpath("WindrosePlus")),
        "windrose_plus_package_folder": str(root.joinpath("windrose_plus")),
        "windrose_plus_config": str(root.joinpath("windrose_plus.json")),
        "windrose_plus_launch_wrapper": str(root.joinpath("StartWindrosePlusServer.bat")),
        "windrose_plus_dashboard_launcher": str(root.joinpath("windrose_plus", "start_dashboard.bat")),
        "windrose_plus_generated_multipliers": str(root.joinpath("R5", "Content", "Paks", "WindrosePlus_Multipliers_P.pak")),
        "windrose_plus_generated_curvetables": str(root.joinpath("R5", "Content", "Paks", "WindrosePlus_CurveTables_P.pak")),
        "windrose_plus_generated_multipliers_mods": str(root.joinpath("R5", "Content", "Paks", "~mods", "WindrosePlus_Multipliers_P.pak")),
        "windrose_plus_generated_curvetables_mods": str(root.joinpath("R5", "Content", "Paks", "~mods", "WindrosePlus_CurveTables_P.pak")),
    }


def _looks_like_windrose_plus(paths: list[str]) -> bool:
    return any("windroseplus/" in path or path.startswith("windroseplus/") for path in paths) or any(
        "windrose_plus" in path for path in paths
    )


def _looks_like_rcon_mod(paths: list[str], names: list[str], source_name: str) -> bool:
    has_rcon_name = any("rcon" in path for path in paths)
    has_settings = any(path.endswith("/settings.ini") or path == "settings.ini" for path in paths)
    has_dll = any("/dlls/" in path or path.endswith("/main.dll") for path in paths)
    has_script = any("/scripts/" in path or path.endswith("/scripts/main.lua") for path in paths)
    has_root_version_dll = "version.dll" in names
    has_rcon_source_name = "rcon" in source_name or "windrosercon" in source_name
    return (has_rcon_name and has_settings and (has_dll or has_script)) or (has_root_version_dll and has_rcon_source_name)


def _has_root_ue4ss_mod_shape(entries: list[ArchiveEntry]) -> bool:
    paths = [entry.pure_path for entry in entries]
    lower_parts = [tuple(part.lower() for part in path.parts) for path in paths]
    if any("scripts" in parts or "dlls" in parts for parts in lower_parts):
        return any(path.name.lower() in UE4SS_MOD_MARKERS for path in paths)
    return False


def _detect_mod_name_from_paths(paths: list[str]) -> str:
    for path in paths:
        parts = PurePosixPath(path).parts
        lowered = [part.lower() for part in parts]
        if "mods" in lowered:
            index = lowered.index("mods")
            if index + 1 < len(parts):
                return parts[index + 1]
        if "scripts" in lowered:
            index = lowered.index("scripts")
            if index > 0:
                return parts[index - 1]
    return ""


def _folder_exists_case_insensitive(parent: Path, folder_name: str) -> bool:
    return _find_case_insensitive_dir(parent, folder_name) is not None


def _find_case_insensitive_dir(parent: Path, folder_name: str) -> Path | None:
    direct = parent / folder_name
    if direct.is_dir():
        return direct
    if not parent.exists():
        return None
    try:
        target = folder_name.lower()
        return next((child for child in parent.iterdir() if child.is_dir() and child.name.lower() == target), None)
    except OSError:
        return None


def _folder_has_files_case_insensitive(parent: Path, folder_name: str) -> bool:
    folder = _find_case_insensitive_dir(parent, folder_name)
    if folder is None:
        return False
    return _dir_has_files(folder)


def _dir_has_files(folder: Path) -> bool:
    if not folder.is_dir():
        return False
    try:
        return any(child.is_file() for child in folder.rglob("*"))
    except OSError:
        return False


def _ue4ss_mods_present(mods_dir: Path) -> bool:
    if not mods_dir.is_dir():
        return False
    try:
        for child in mods_dir.iterdir():
            if child.is_file() and child.name.lower() != "mods.txt":
                return True
            if child.is_dir() and any(item.is_file() for item in child.rglob("*")):
                return True
    except OSError:
        return False
    return False


def _has_generated_windrose_plus_paks(root: Path) -> bool:
    for mods_dir in (root / "R5" / "Content" / "Paks", root / "R5" / "Content" / "Paks" / "~mods"):
        if not mods_dir.exists():
            continue
        try:
            if any(child.is_file() and child.name.lower() in WINDROSE_PLUS_GENERATED_PAKS for child in mods_dir.iterdir()):
                return True
        except OSError:
            continue
    return False


def _rcon_settings_state(path: Path) -> tuple[bool, bool]:
    if not path.is_file():
        return False, False
    try:
        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip().lower()] = value.strip()
        password = values.get("password", "")
        return True, password == "" or password.lower() == "changeme"
    except OSError:
        return True, True
