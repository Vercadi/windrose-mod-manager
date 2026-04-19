from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ..models.archive_info import ArchiveEntry


UE4SS_CORE_NAMES = {
    "ue4ss.dll",
    "ue4ss-settings.ini",
    "ue4ss.ini",
    "dwmapi.dll",
    "xinput1_3.dll",
}


@dataclass
class FrameworkAnalysis:
    category: str = "standard_mod"
    framework_name: str = ""
    likely_destinations: list[str] = field(default_factory=list)
    dependency_warnings: list[str] = field(default_factory=list)


def analyze_archive_framework(entries: Iterable[ArchiveEntry]) -> FrameworkAnalysis:
    names = [entry.pure_path.name.lower() for entry in entries if not entry.is_dir]
    paths = [str(entry.pure_path).replace("\\", "/").lower() for entry in entries if not entry.is_dir]
    joined_names = " ".join(names)

    has_binaries = any("/binaries/win64/" in path or path.startswith("r5/binaries/win64/") for path in paths)
    has_ue4ss_folder = any("/ue4ss/" in path or path.startswith("ue4ss/") for path in paths)
    has_ue4ss_core = any(name in UE4SS_CORE_NAMES for name in names)
    has_ue4ss_mod_tree = any("/ue4ss/mods/" in path or path.startswith("ue4ss/mods/") for path in paths)

    analysis = FrameworkAnalysis()

    if has_ue4ss_core or (has_binaries and has_ue4ss_folder):
        analysis.category = "framework_runtime"
        analysis.framework_name = "UE4SS Runtime"
        analysis.likely_destinations = [r"R5\Binaries\Win64", "ue4ss/"]
        return analysis

    if has_ue4ss_mod_tree or "ue4ss" in joined_names:
        analysis.category = "framework_mod"
        analysis.framework_name = "UE4SS"
        analysis.likely_destinations = ["ue4ss/Mods"]
        analysis.dependency_warnings.append(
            "Likely depends on the UE4SS runtime being installed first."
        )
        return analysis

    return analysis


def detect_framework_state(root: Path | None) -> dict[str, bool]:
    if root is None:
        return {"configured": False, "ue4ss_runtime": False}

    win64 = root / "R5" / "Binaries" / "Win64"
    markers = [
        win64 / "UE4SS.dll",
        win64 / "ue4ss.dll",
        win64 / "UE4SS-settings.ini",
        win64 / "ue4ss-settings.ini",
        win64 / "dwmapi.dll",
        root / "ue4ss",
    ]
    return {
        "configured": True,
        "ue4ss_runtime": any(path.exists() for path in markers),
    }
