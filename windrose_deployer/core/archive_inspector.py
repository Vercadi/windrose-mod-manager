"""Analyze mod archive contents and classify the archive type."""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Optional

from ..models.archive_info import ArchiveEntry, ArchiveInfo, ArchiveType, VariantGroup
from .archive_handler import ArchiveReader, open_archive, is_supported_archive
from .framework_detector import analyze_archive_framework

log = logging.getLogger(__name__)

PAK_EXTENSIONS = {".pak", ".utoc", ".ucas"}
KNOWN_ROOT_DIRS = {"R5", "Engine"}
_VARIANT_NUMBER_RE = re.compile(
    r"""
    (?:[-_ ]?)                       # optional separator
    (?:x|v|var|variant|option)?      # optional label
    (\d{2,})                         # 2+ digit number (the variant id)
    (?:[-_ ]\w+)?                    # optional trailing suffix like _P
    $                                # end of stem
    """,
    re.IGNORECASE | re.VERBOSE,
)


def inspect_archive(archive_path: Path) -> ArchiveInfo:
    """Open an archive, enumerate entries, classify, and return analysis."""
    info = ArchiveInfo(archive_path=str(archive_path))

    if not archive_path.is_file():
        info.warnings.append(f"Archive not found: {archive_path}")
        return info

    if not is_supported_archive(archive_path):
        info.warnings.append(
            f"Unsupported archive format: {archive_path.suffix}\n"
            "Supported formats: .zip, .7z, .rar"
        )
        return info

    try:
        reader = open_archive(archive_path)
    except Exception as exc:
        info.warnings.append(f"Failed to open archive: {exc}")
        return info

    try:
        _enumerate(reader, info)
    except Exception as exc:
        info.warnings.append(f"Error reading archive: {exc}")
        return info
    finally:
        reader.close()

    _detect_root_prefix(info)
    _classify(info)
    _detect_variants(info)
    _suggest_target(info)
    _detect_frameworks(info)

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


def _enumerate(reader: ArchiveReader, info: ArchiveInfo) -> None:
    for ei in reader.list_entries():
        entry = ArchiveEntry(
            path=ei.filename,
            is_dir=ei.is_dir,
            size=ei.file_size,
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
        # Only treat as a wrapper folder if at least one entry has deeper parts
        # (i.e. it's actually a directory, not a bare filename at the root)
        has_children = any(len(PurePosixPath(e.path).parts) > 1 for e in info.entries)
        if has_children and single not in KNOWN_ROOT_DIRS:
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
    """Group pak files that look like numbered alternatives.

    Strategy: strip .pak, look for a numeric segment near the end of the stem,
    and group files that share the same prefix before that segment.  Handles
    real-world patterns like ``Stack_Size_Changes_x10_P.pak``.

    Only uses the regex-based grouping to avoid false positives on additive
    multi-pak mods (e.g. ShipOverhaul_Base.pak + ShipOverhaul_Compatibility.pak).
    """
    if len(info.pak_entries) < 2:
        return

    groups: dict[str, list[ArchiveEntry]] = defaultdict(list)

    for entry in info.pak_entries:
        stem = PurePosixPath(entry.path).stem
        m = _VARIANT_NUMBER_RE.search(stem)
        if m:
            base = stem[: m.start()]
            groups[base].append(entry)

    for base, members in groups.items():
        if len(members) >= 2:
            info.variant_groups.append(VariantGroup(base_name=base, variants=members))
            info.warnings.append(
                f"Detected {len(members)} variants for '{base}' — user should choose one."
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


def _detect_frameworks(info: ArchiveInfo) -> None:
    analysis = analyze_archive_framework(info.entries, archive_path=info.archive_path)
    info.content_category = analysis.category
    info.install_kind = analysis.install_kind
    info.framework_name = analysis.framework_name
    info.likely_destinations = list(analysis.likely_destinations)
    info.dependency_warnings.extend(analysis.dependency_warnings)
    if analysis.install_kind == "ue4ss_runtime":
        info.warnings.append("Likely UE4SS runtime package. Install it to R5\\Binaries\\Win64 for the chosen target.")
    elif analysis.install_kind == "windrose_plus":
        info.warnings.append("WindrosePlus package detected. Local Windows dedicated-server workflows are the safest first target.")
    elif analysis.install_kind == "ue4ss_mod" and analysis.framework_name:
        info.dependency_warnings.append(
            f"Review recommended: this archive may depend on {analysis.framework_name}."
        )
