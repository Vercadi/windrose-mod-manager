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


@dataclass
class FrameworkAnalysis:
    category: str = "standard_mod"
    install_kind: str = "standard_mod"
    framework_name: str = ""
    detected_mod_name: str = ""
    likely_destinations: list[str] = field(default_factory=list)
    dependency_warnings: list[str] = field(default_factory=list)


def analyze_archive_framework(entries: Iterable[ArchiveEntry]) -> FrameworkAnalysis:
    entry_list = [entry for entry in entries if not entry.is_dir]
    names = [entry.pure_path.name.lower() for entry in entry_list]
    paths = [str(entry.pure_path).replace("\\", "/").lower() for entry in entry_list]
    joined_names = " ".join(names)

    has_binaries = any("/binaries/win64/" in path or path.startswith("r5/binaries/win64/") for path in paths)
    has_ue4ss_folder = any("/ue4ss/" in path or path.startswith("ue4ss/") for path in paths)
    has_ue4ss_core = any(name in UE4SS_CORE_NAMES for name in names)
    has_ue4ss_mod_tree = any("/ue4ss/mods/" in path or path.startswith("ue4ss/mods/") for path in paths)
    has_root_ue4ss_mod = _has_root_ue4ss_mod_shape(entry_list)
    has_windrose_plus = _looks_like_windrose_plus(paths)
    has_rcon_mod = _looks_like_rcon_mod(paths)

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
        analysis.likely_destinations = [r"R5\Binaries\Win64\ue4ss\Mods"]
        analysis.dependency_warnings.append(
            "Likely depends on the UE4SS runtime being installed first."
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
            "rcon_mod": False,
            "windrose_plus": False,
            "windrose_plus_package": False,
        }

    win64 = root / "R5" / "Binaries" / "Win64"
    mods_dir = win64 / "ue4ss" / "Mods"
    markers = [
        win64 / "UE4SS.dll",
        win64 / "ue4ss.dll",
        win64 / "UE4SS-settings.ini",
        win64 / "ue4ss-settings.ini",
        win64 / "dwmapi.dll",
        win64 / "dwmappi.dll",
        win64 / "ue4ss",
    ]
    windrose_plus_active = _folder_exists_case_insensitive(mods_dir, "WindrosePlus")
    windrose_plus_package = windrose_plus_active or _folder_exists_case_insensitive(root, "WindrosePlus")
    return {
        "configured": True,
        "ue4ss_runtime": any(path.exists() for path in markers),
        "rcon_mod": _folder_exists_case_insensitive(mods_dir, "WindroseRCON"),
        "windrose_plus": windrose_plus_active,
        "windrose_plus_package": windrose_plus_package,
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
        "rcon_mod": str(mods.joinpath("WindroseRCON")),
        "windrose_plus": str(mods.joinpath("WindrosePlus")),
        "windrose_plus_package": str(root.joinpath("WindrosePlus")),
    }


def _looks_like_windrose_plus(paths: list[str]) -> bool:
    return any("windroseplus/" in path or path.startswith("windroseplus/") for path in paths) or any(
        "windrose_plus" in path for path in paths
    )


def _looks_like_rcon_mod(paths: list[str]) -> bool:
    has_rcon_name = any("rcon" in path for path in paths)
    has_settings = any(path.endswith("/settings.ini") or path == "settings.ini" for path in paths)
    has_dll = any("/dlls/" in path or path.endswith("/main.dll") for path in paths)
    has_script = any("/scripts/" in path or path.endswith("/scripts/main.lua") for path in paths)
    return has_rcon_name and has_settings and (has_dll or has_script)


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
    direct = parent / folder_name
    if direct.exists():
        return True
    if not parent.exists():
        return False
    try:
        target = folder_name.lower()
        return any(child.is_dir() and child.name.lower() == target for child in parent.iterdir())
    except OSError:
        return False
