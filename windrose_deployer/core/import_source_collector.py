"""Collect supported mod import sources from files or shallow folders."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .archive_handler import SUPPORTED_EXTENSIONS
from .pak_bundle_importer import PAK_BUNDLE_EXTENSIONS

SUPPORTED_IMPORT_EXTENSIONS = set(SUPPORTED_EXTENSIONS) | set(PAK_BUNDLE_EXTENSIONS)


@dataclass
class ImportCollection:
    archive_files: list[Path] = field(default_factory=list)
    pak_files: list[Path] = field(default_factory=list)
    scanned_folders: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def supported_files(self) -> list[Path]:
        return [*self.archive_files, *self.pak_files]


def collect_importable_sources(
    paths: Iterable[Path],
    *,
    max_supported_files: int = 250,
) -> ImportCollection:
    """Return supported archive/pak sources from direct files and shallow folders.

    Folder scans include direct files and files one level below the selected
    folder. This catches common extracted mod folders without walking a whole
    drive by accident.
    """
    result = ImportCollection()
    seen: set[str] = set()
    supported_count = 0
    truncated = False

    def add_supported(file_path: Path) -> None:
        nonlocal supported_count, truncated
        key = _normalized_file(file_path)
        if key in seen:
            return
        seen.add(key)
        if supported_count >= max_supported_files:
            truncated = True
            return
        supported_count += 1
        suffix = file_path.suffix.lower()
        if suffix in SUPPORTED_EXTENSIONS:
            result.archive_files.append(file_path)
        elif suffix in PAK_BUNDLE_EXTENSIONS:
            result.pak_files.append(file_path)

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            result.scanned_folders.append(path)
            supported, unsupported_count = _scan_folder(path)
            if not supported:
                result.warnings.append(f"No supported mod files found in folder: {path.name}")
            for file_path in supported:
                add_supported(file_path)
            if unsupported_count:
                result.warnings.append(
                    f"Skipped {unsupported_count} unsupported file(s) while scanning {path.name}."
                )
            continue

        if path.is_file():
            suffix = path.suffix.lower()
            if suffix in SUPPORTED_IMPORT_EXTENSIONS:
                add_supported(path)
            else:
                result.warnings.append(f"Skipped unsupported file: {path.name}")
            continue

        result.warnings.append(f"Skipped missing file or folder: {path}")

    if truncated:
        result.warnings.append(
            f"Found more than {max_supported_files} supported mod file(s). "
            f"Imported the first {max_supported_files}; choose a smaller folder for the rest."
        )

    return result


def _scan_folder(folder: Path) -> tuple[list[Path], int]:
    supported: list[Path] = []
    unsupported_count = 0
    try:
        children = sorted(folder.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return [], 0

    nested_folders: list[Path] = []
    for child in children:
        if child.is_file():
            if child.suffix.lower() in SUPPORTED_IMPORT_EXTENSIONS:
                supported.append(child)
            else:
                unsupported_count += 1
            continue
        if child.is_dir():
            nested_folders.append(child)

    for child in nested_folders:
        try:
            grandchildren = sorted(child.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for grandchild in grandchildren:
            if not grandchild.is_file():
                continue
            if grandchild.suffix.lower() in SUPPORTED_IMPORT_EXTENSIONS:
                supported.append(grandchild)
            else:
                unsupported_count += 1

    return supported, unsupported_count


def _normalized_file(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path.absolute()).lower()
