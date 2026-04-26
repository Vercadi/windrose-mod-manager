"""Helpers for manager-owned archive library files."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..utils.filesystem import ensure_dir
from ..utils.hashing import hash_file
from ..utils.naming import sanitize_mod_id


def should_copy_archive_to_library(*, content_category: str = "standard_mod", install_kind: str = "standard_mod") -> bool:
    """Only manager-copy normal mod archives, not external tool/framework bundles."""
    if (install_kind or "standard_mod") != "standard_mod":
        return False
    return (content_category or "standard_mod") not in {"framework_runtime", "framework_mod"}


def manager_owned_archive_path(
    source: Path,
    archive_dir: Path,
    existing_entries: list[dict],
) -> tuple[Path, str, bool]:
    """Copy an imported archive into *archive_dir* and reuse existing copies by hash."""
    digest = hash_file(source)
    for entry in existing_entries:
        if entry.get("source_kind", "archive") != "archive":
            continue
        if entry.get("archive_hash") != digest:
            continue
        candidate = Path(str(entry.get("path", "")))
        if candidate.is_file():
            return candidate, digest, True

    ensure_dir(archive_dir)
    suffix = source.suffix.lower()
    stem = sanitize_mod_id(source.stem) or "archive"
    target = archive_dir / f"{stem}-{digest[:12]}{suffix}"
    if not target.is_file():
        shutil.copy2(source, target)
    return target, digest, False
