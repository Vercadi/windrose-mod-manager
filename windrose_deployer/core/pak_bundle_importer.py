"""Import loose pak/IoStore companion files as one manager-owned source."""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ..utils.filesystem import ensure_dir
from ..utils.naming import sanitize_mod_id

PAK_BUNDLE_EXTENSIONS = {".pak", ".utoc", ".ucas"}
_PAK_BUNDLE_ORDER = {".pak": 0, ".utoc": 1, ".ucas": 2}


@dataclass
class PakBundleImport:
    archive_path: Path
    display_name: str
    source_files: list[Path]


@dataclass
class PakBundleImportResult:
    created_archives: list[PakBundleImport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def is_pak_bundle_file(path: Path) -> bool:
    """Return True when *path* is a raw pak/IoStore companion file."""
    return path.suffix.lower() in PAK_BUNDLE_EXTENSIONS


def import_pak_bundles(paths: Iterable[Path], output_dir: Path) -> PakBundleImportResult:
    """Group selected loose pak companions and wrap each group in a zip source.

    The rest of the app already has well-tested archive install/repair/hosted
    paths. Creating one internal zip per pak bundle keeps loose-file imports on
    that safe path while presenting them as normal inactive mods in the UI.
    """
    result = PakBundleImportResult()
    selected_files = [Path(path) for path in paths if is_pak_bundle_file(Path(path))]
    if not selected_files:
        return result

    expanded_files, warnings = _expand_with_companions(selected_files)
    result.warnings.extend(warnings)

    groups: dict[tuple[str, str], list[Path]] = {}
    for file_path in expanded_files:
        key = (_normalized_parent(file_path), file_path.stem.lower())
        groups.setdefault(key, []).append(file_path)

    ensure_dir(output_dir)
    for files in groups.values():
        unique_files = _sorted_unique(files)
        pak_files = [file_path for file_path in unique_files if file_path.suffix.lower() == ".pak"]
        if not pak_files:
            names = ", ".join(file_path.name for file_path in unique_files[:3])
            result.warnings.append(f"Skipped {names}: companion files need the matching .pak file.")
            continue

        display_name = pak_files[0].stem
        digest = _bundle_digest(unique_files)
        archive_path = output_dir / f"{sanitize_mod_id(display_name)}-{digest[:12]}.zip"
        if not archive_path.exists():
            _write_bundle_zip(unique_files, archive_path)
        result.created_archives.append(
            PakBundleImport(
                archive_path=archive_path,
                display_name=display_name,
                source_files=unique_files,
            )
        )

    return result


def _expand_with_companions(paths: list[Path]) -> tuple[list[Path], list[str]]:
    expanded: dict[str, Path] = {}
    warnings: list[str] = []
    for path in paths:
        if not path.is_file():
            warnings.append(f"Skipped missing file: {path}")
            continue
        siblings = _matching_companions(path)
        if not siblings:
            expanded[_normalized_file(path)] = path
            continue
        for sibling in siblings:
            expanded[_normalized_file(sibling)] = sibling
    return list(expanded.values()), warnings


def _matching_companions(path: Path) -> list[Path]:
    try:
        return [
            candidate
            for candidate in path.parent.iterdir()
            if candidate.is_file()
            and candidate.stem.lower() == path.stem.lower()
            and candidate.suffix.lower() in PAK_BUNDLE_EXTENSIONS
        ]
    except OSError:
        return [path]


def _sorted_unique(files: Iterable[Path]) -> list[Path]:
    by_key = {_normalized_file(file_path): file_path for file_path in files}
    return sorted(
        by_key.values(),
        key=lambda file_path: (_PAK_BUNDLE_ORDER.get(file_path.suffix.lower(), 99), file_path.name.lower()),
    )


def _write_bundle_zip(files: list[Path], archive_path: Path) -> None:
    ensure_dir(archive_path.parent)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for file_path in files:
            archive.write(file_path, arcname=file_path.name)


def _bundle_digest(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for file_path in files:
        digest.update(file_path.name.lower().encode("utf-8"))
        digest.update(b"\0")
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _normalized_file(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path.absolute()).lower()


def _normalized_parent(path: Path) -> str:
    try:
        return str(path.parent.resolve()).lower()
    except OSError:
        return str(path.parent.absolute()).lower()
