"""Known framework config helpers for UE4SS, RCON, and WindrosePlus."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .backup_manager import BackupManager


@dataclass(frozen=True)
class FrameworkConfigSpec:
    key: str
    label: str
    relative_path: Path
    guidance: str


KNOWN_CONFIGS: dict[str, FrameworkConfigSpec] = {
    "ue4ss_settings": FrameworkConfigSpec(
        key="ue4ss_settings",
        label="UE4SS-settings.ini",
        relative_path=Path("R5") / "Binaries" / "Win64" / "ue4ss" / "UE4SS-settings.ini",
        guidance="Save requires restarting the game/server.",
    ),
    "rcon_settings": FrameworkConfigSpec(
        key="rcon_settings",
        label="WindroseRCON settings.ini",
        relative_path=Path("R5") / "Binaries" / "Win64" / "windrosercon" / "settings.ini",
        guidance="Start the server once after installing version.dll to generate this file. Save requires restarting the server.",
    ),
    "windrose_plus_json": FrameworkConfigSpec(
        key="windrose_plus_json",
        label="windrose_plus.json",
        relative_path=Path("windrose_plus.json"),
        guidance=(
            "Common fields: multipliers.stack_size, inventory_size, harvest_yield, loot, xp; "
            "rcon.enabled, rcon.port, rcon.password; server.http_port. "
            "Save requires restart; multiplier changes should be applied through Rebuild WindrosePlus Overrides "
            "or the WindrosePlus launch wrapper."
        ),
    ),
    "windrose_plus_ini": FrameworkConfigSpec(
        key="windrose_plus_ini",
        label="windrose_plus.ini",
        relative_path=Path("windrose_plus.ini"),
        guidance="Save requires rebuilding WindrosePlus overrides before launch.",
    ),
    "windrose_plus_food_ini": FrameworkConfigSpec(
        key="windrose_plus_food_ini",
        label="windrose_plus.food.ini",
        relative_path=Path("windrose_plus.food.ini"),
        guidance="Save requires rebuilding WindrosePlus overrides before launch.",
    ),
    "windrose_plus_weapons_ini": FrameworkConfigSpec(
        key="windrose_plus_weapons_ini",
        label="windrose_plus.weapons.ini",
        relative_path=Path("windrose_plus.weapons.ini"),
        guidance="Save requires rebuilding WindrosePlus overrides before launch.",
    ),
    "windrose_plus_gear_ini": FrameworkConfigSpec(
        key="windrose_plus_gear_ini",
        label="windrose_plus.gear.ini",
        relative_path=Path("windrose_plus.gear.ini"),
        guidance="Save requires rebuilding WindrosePlus overrides before launch.",
    ),
    "windrose_plus_entities_ini": FrameworkConfigSpec(
        key="windrose_plus_entities_ini",
        label="windrose_plus.entities.ini",
        relative_path=Path("windrose_plus.entities.ini"),
        guidance="Save requires rebuilding WindrosePlus overrides before launch.",
    ),
}


@dataclass(frozen=True)
class WindrosePlusPaths:
    root: Path
    install_script: Path
    build_script: Path
    launch_wrapper: Path
    dashboard_launcher: Path
    folder: Path
    generated_multipliers_pak: Path
    generated_curvetables_pak: Path


class FrameworkConfigService:
    def __init__(self, backup_manager: BackupManager):
        self.backup = backup_manager

    @staticmethod
    def config_path(root: Path | None, key: str) -> Path | None:
        spec = KNOWN_CONFIGS.get(key)
        if root is None or spec is None:
            return None
        return root / spec.relative_path

    @staticmethod
    def config_spec(key: str) -> FrameworkConfigSpec | None:
        return KNOWN_CONFIGS.get(key)

    @staticmethod
    def windrose_plus_paths(root: Path | None) -> WindrosePlusPaths | None:
        if root is None:
            return None
        folder = root / "windrose_plus"
        return WindrosePlusPaths(
            root=root,
            install_script=root / "install.ps1",
            build_script=folder / "tools" / "WindrosePlus-BuildPak.ps1",
            launch_wrapper=root / "StartWindrosePlusServer.bat",
            dashboard_launcher=folder / "start_dashboard.bat",
            folder=folder,
            generated_multipliers_pak=root / "R5" / "Content" / "Paks" / "WindrosePlus_Multipliers_P.pak",
            generated_curvetables_pak=root / "R5" / "Content" / "Paks" / "WindrosePlus_CurveTables_P.pak",
        )

    def read_config(self, root: Path | None, key: str) -> tuple[Path | None, str]:
        path = self.config_path(root, key)
        if path is None or not path.is_file():
            return path, ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if key == "windrose_plus_json":
            return path, _format_json_text(text)
        return path, text

    def save_config(self, root: Path | None, key: str, text: str) -> Path:
        path = self.config_path(root, key)
        if path is None:
            raise ValueError("Target root is not configured.")
        if key == "windrose_plus_json":
            text = _format_json_text(text, validate=True)
        if path.exists():
            self.backup.backup_file(
                path,
                category="framework_config",
                description=f"Pre-save backup of {path.name}",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_windrose_plus_install(self, root: Path | None) -> subprocess.CompletedProcess[str]:
        paths = self.windrose_plus_paths(root)
        if paths is None or not paths.install_script.is_file():
            raise FileNotFoundError("WindrosePlus install.ps1 was not found in the selected server root.")
        return _run_powershell(paths.install_script, [], cwd=paths.root)

    def run_windrose_plus_rebuild(self, root: Path | None) -> subprocess.CompletedProcess[str]:
        paths = self.windrose_plus_paths(root)
        if paths is None or not paths.build_script.is_file():
            raise FileNotFoundError("WindrosePlus-BuildPak.ps1 was not found. Run the WindrosePlus install first.")
        return _run_powershell(paths.build_script, ["-ServerDir", str(paths.root), "-RemoveStalePak"], cwd=paths.root)


def _run_powershell(script: Path, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(script), *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def _format_json_text(text: str, *, validate: bool = False) -> str:
    try:
        return json.dumps(json.loads(text or "{}"), indent=2, ensure_ascii=False) + "\n"
    except json.JSONDecodeError as exc:
        if validate:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        return text
