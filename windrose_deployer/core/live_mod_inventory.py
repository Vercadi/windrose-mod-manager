"""Helpers for comparing manifest installs against live mods-folder contents."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from ..models.mod_install import ModInstall, expand_target_values

DISABLED_SUFFIX = ".disabled"
_UE5_BUNDLE_EXTS = {".pak", ".utoc", ".ucas"}
_UE5_EXT_ORDER = {".pak": 0, ".utoc": 1, ".ucas": 2}


@dataclass
class LiveModsFolderSnapshot:
    folder: Optional[Path]
    exists: bool = False
    warning: Optional[str] = None
    live_files: list[str] = field(default_factory=list)
    managed_present_files: list[str] = field(default_factory=list)
    unmanaged_files: list[str] = field(default_factory=list)
    missing_managed_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LiveModBundle:
    display_name: str
    file_names: tuple[str, ...]

    @property
    def file_count(self) -> int:
        return len(self.file_names)


def snapshot_live_mods_folder(
    mods_dir: Optional[Path],
    mods: Iterable[ModInstall],
    *,
    target: str,
) -> LiveModsFolderSnapshot:
    managed_set: set[str] = set()
    if mods_dir is not None:
        for mod in mods:
            if not mod.enabled:
                continue
            if target not in expand_target_values(mod.targets):
                continue
            for file_path in mod.installed_files:
                canonical = _canonical_manifest_path(file_path)
                path = Path(canonical)
                if _is_in_folder(path, mods_dir):
                    managed_set.add(path.name)

    if mods_dir is None:
        return LiveModsFolderSnapshot(
            folder=None,
            warning="Mods folder is not configured.",
            missing_managed_files=sorted(managed_set),
        )

    if not mods_dir.exists():
        return LiveModsFolderSnapshot(
            folder=mods_dir,
            exists=False,
            warning=f"Mods folder not found: {mods_dir}",
            missing_managed_files=sorted(managed_set),
        )

    live_names = sorted(
        entry.name
        for entry in mods_dir.iterdir()
        if entry.is_file() and not entry.name.endswith(DISABLED_SUFFIX)
    )
    live_set = set(live_names)

    return LiveModsFolderSnapshot(
        folder=mods_dir,
        exists=True,
        live_files=live_names,
        managed_present_files=sorted(live_set & managed_set),
        unmanaged_files=sorted(live_set - managed_set),
        missing_managed_files=sorted(managed_set - live_set),
    )


def _canonical_manifest_path(path_str: str) -> str:
    if path_str.endswith(DISABLED_SUFFIX):
        return path_str[: -len(DISABLED_SUFFIX)]
    return path_str


def bundle_live_file_names(file_names: Iterable[str]) -> list[LiveModBundle]:
    grouped: dict[tuple[str, str], list[str]] = {}
    display_names: dict[tuple[str, str], str] = {}
    for name in sorted(set(file_names), key=_file_sort_key):
        key, display_name = _bundle_key(name)
        grouped.setdefault(key, []).append(name)
        display_names.setdefault(key, display_name)
    bundles = [
        LiveModBundle(
            display_name=display_names[key],
            file_names=tuple(sorted(names, key=_file_sort_key)),
        )
        for key, names in grouped.items()
    ]
    return sorted(bundles, key=lambda bundle: bundle.display_name.lower())


def _is_in_folder(path: Path, folder: Path) -> bool:
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def _bundle_key(name: str) -> tuple[tuple[str, str], str]:
    path = Path(name)
    ext = path.suffix.lower()
    if ext in _UE5_BUNDLE_EXTS:
        return ("ue5", path.stem.lower()), path.stem or path.name
    return ("file", path.name.lower()), path.stem or path.name


def _file_sort_key(name: str) -> tuple[str, int, str]:
    path = Path(name)
    ext = path.suffix.lower()
    return (
        path.stem.lower(),
        _UE5_EXT_ORDER.get(ext, len(_UE5_EXT_ORDER)),
        path.name.lower(),
    )
