"""Analyze mod archive contents and classify the archive type."""
from __future__ import annotations

import logging
import re
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Optional

from ..models.archive_info import ArchiveEntry, ArchiveInfo, ArchiveType, VariantGroup

log = logging.getLogger(__name__)

PAK_EXTENSIONS = {".pak", ".utoc", ".ucas"}
KNOWN_ROOT_DIRS = {"R5", "Engine"}
VARIANT_PATTERN = re.compile(
    r"^(?P<base>.+?)(?:[-_ ]?(?:x|v|var|variant|option)?)(?P<num>\d{2,})\.pak$",
    re.IGNORECASE,
)


def inspect_archive(archive_path: Path) -> ArchiveInfo:
    """Open a zip archive, enumerate entries, classify, and return analysis."""
    info = ArchiveInfo(archive_path=str(archive_path))

    if not archive_path.is_file():
        info.warnings.append(f"Archive not found: {archive_path}")
        return info

    if not zipfile.is_zipfile(archive_path):
        info.warnings.append("File is not a valid zip archive.")
        return info

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            _enumerate(zf, info)
    except zipfile.BadZipFile as exc:
        info.warnings.append(f"Corrupt zip archive: {exc}")
        return info

    _detect_root_prefix(info)
    _classify(info)
    _detect_variants(info)
    _suggest_target(info)

    if info.has_variants:
        info.archive_type = ArchiveType.MULTI_VARIANT_PAK

    log.info(
        "Archive %s: type=%s, paks=%d, loose=%d, variants=%d",
        archive_path.name,
        info.archive_type.value,
        len(info.pak_entries),
        len(info.loose_entries),
        len(info.variant_groups),
    )
    return info


# ------------------------------------------------------------------ internals


def _enumerate(zf: zipfile.ZipFile, info: ArchiveInfo) -> None:
    for zi in zf.infolist():
        entry = ArchiveEntry(
            path=zi.filename,
            is_dir=zi.is_dir(),
            size=zi.file_size,
        )
        info.entries.append(entry)

        if entry.is_dir:
            continue

        if entry.is_pak:
            info.pak_entries.append(entry)
        elif entry.is_utoc or entry.is_ucas:
            info.companion_entries.append(entry)
        else:
            info.loose_entries.append(entry)


def _detect_root_prefix(info: ArchiveInfo) -> None:
    """If all entries share a common top-level folder that matches a known game
    dir (R5, Engine) or is a single wrapper folder, strip it."""
    top_parts: set[str] = set()
    for e in info.entries:
        parts = PurePosixPath(e.path).parts
        if parts:
            top_parts.add(parts[0])

    if len(top_parts) == 1:
        single = next(iter(top_parts))
        if single not in KNOWN_ROOT_DIRS:
            info.root_prefix = single + "/"
    elif top_parts & KNOWN_ROOT_DIRS:
        info.root_prefix = ""


def _classify(info: ArchiveInfo) -> None:
    has_paks = len(info.pak_entries) > 0
    has_loose = len(info.loose_entries) > 0

    if has_paks and has_loose:
        info.archive_type = ArchiveType.MIXED
    elif has_paks:
        info.archive_type = ArchiveType.PAK_ONLY
    elif has_loose:
        info.archive_type = ArchiveType.LOOSE_FILES
    else:
        info.archive_type = ArchiveType.UNKNOWN
        info.warnings.append("Archive contains no recognisable mod files.")


def _detect_variants(info: ArchiveInfo) -> None:
    """Group pak files that look like numbered alternatives."""
    if len(info.pak_entries) < 2:
        return

    groups: dict[str, list[ArchiveEntry]] = defaultdict(list)
    for entry in info.pak_entries:
        name = PurePosixPath(entry.path).name
        m = VARIANT_PATTERN.match(name)
        if m:
            groups[m.group("base")].append(entry)

    for base, members in groups.items():
        if len(members) >= 2:
            info.variant_groups.append(VariantGroup(base_name=base, variants=members))
            info.warnings.append(
                f"Detected {len(members)} variants for '{base}' — user should choose."
            )


def _suggest_target(info: ArchiveInfo) -> None:
    """Heuristic: if all files land under Paks, suggest pak target; otherwise root."""
    paks_pattern = re.compile(r"(?:^|/)Content/Paks/", re.IGNORECASE)
    all_in_paks = all(
        paks_pattern.search(e.path)
        for e in info.entries
        if not e.is_dir
    )
    if all_in_paks:
        info.suggested_target = "paks"
    elif info.archive_type == ArchiveType.PAK_ONLY:
        info.suggested_target = "paks"
    else:
        info.suggested_target = "root"
