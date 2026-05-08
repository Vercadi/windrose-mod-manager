"""Human-readable archive and install review text helpers."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

from ..models.archive_info import ArchiveInfo
from ..models.mod_install import target_value_label
from .deployment_planner import DeploymentPlan
from .remote_deployer import RemoteDeploymentPlan


_CONFIG_SUFFIXES = {".ini", ".json", ".cfg", ".conf", ".toml", ".yaml", ".yml"}
_METADATA_NAMES = {"manifest.json", "readme.md", "readme.txt", "changelog.md", "icon.png"}


def archive_summary_lines(info: ArchiveInfo) -> list[str]:
    """Return concise user-facing facts about an inspected archive."""
    config_entries = archive_config_entries(info)
    detected = ", ".join(
        part
        for part in [
            _count_label(len(info.pak_entries), "pak file"),
            _count_label(len(info.companion_entries), "companion file"),
            _count_label(len(info.loose_entries), "loose file"),
            _count_label(len(config_entries), "config/metadata file"),
        ]
        if part
    ) or "none"
    summary = [
        f"Type: {info.archive_type.value.replace('_', ' ').title()}",
        f"Install kind: {info.install_kind.replace('_', ' ').title()}",
        f"Files detected: {detected}",
    ]
    if info.variant_groups:
        summary.append(
            "Variants: "
            + ", ".join(
                f"{group.base_name or 'group'} ({len(group.variants)})"
                for group in info.variant_groups
            )
        )
    if info.framework_name:
        summary.append(f"Framework: {info.framework_name}")
    if info.root_prefix:
        summary.append(f"Wrapper folder: {info.root_prefix}")
    if info.likely_destinations:
        summary.append("Destination hint: " + ", ".join(info.likely_destinations))
    elif info.suggested_target:
        summary.append(f"Destination hint: {info.suggested_target}")
    if config_entries:
        summary.append(
            "Config/metadata: "
            + ", ".join(_short_entry_name(entry.path) for entry in config_entries[:8])
            + (" ..." if len(config_entries) > 8 else "")
        )
    warnings = list(info.warnings) + list(info.dependency_warnings)
    if warnings:
        summary.append(f"Review notes: {len(warnings)}")
    return summary


def archive_config_entries(info: ArchiveInfo):
    return [
        entry
        for entry in info.entries
        if not entry.is_dir and _is_config_or_metadata_path(entry.path)
    ]


def build_local_install_report(
    *,
    info: ArchiveInfo,
    mod_name: str,
    preset_label: str,
    selected_variant: str | None,
    prepared_plans: Sequence[tuple[object, DeploymentPlan]],
    plan_warnings: Iterable[str] = (),
    conflict_lines: Iterable[str] = (),
) -> str:
    """Build the local install review shown before writing files."""
    warnings = _dedupe_lines(plan_warnings)
    conflicts = _dedupe_lines(conflict_lines)
    lines = [
        "Install review",
        f"Mod: {mod_name}",
        f"Source: {Path(info.archive_path).name}",
        f"Target: {preset_label}",
        f"Selected variant: {selected_variant or 'none'}",
        f"UE4SS: {_ue4ss_status(info, warnings)}",
        "",
        "Archive:",
        *_prefix_lines(archive_summary_lines(info)),
        "",
        "Files to install:",
    ]
    for target, plan in prepared_plans:
        target_label = _target_label(target)
        lines.append(f"- {target_label}: {plan.file_count} file(s)")
        lines.extend(_preview_plan_files(plan.files))

    lines.append("")
    lines.append("Risk:")
    if conflicts:
        lines.append(f"- Managed conflicts: {len(conflicts)}")
        lines.extend(f"  {line}" for line in conflicts[:8])
    else:
        lines.append("- Managed conflicts: none detected")
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")
        lines.extend(f"  {line}" for line in warnings[:8])
    else:
        lines.append("- Warnings: none")
    lines.append("- Backup: existing managed files are backed up before overwrite")
    return "\n".join(lines)


def build_remote_install_report(
    *,
    info: ArchiveInfo,
    profile_name: str,
    selected_variant: str | None,
    plan: RemoteDeploymentPlan,
    ue4ss_external: bool = False,
) -> str:
    """Build the hosted upload review text."""
    lines = [
        "Hosted upload review",
        f"Profile: {profile_name}",
        f"Source: {Path(info.archive_path).name}",
        f"Selected variant: {selected_variant or 'none'}",
        f"UE4SS: {_ue4ss_status(info, plan.warnings, ue4ss_external=ue4ss_external)}",
        "",
        "Archive:",
        *_prefix_lines(archive_summary_lines(info)),
        "",
        f"Files to upload: {plan.file_count}",
    ]
    for item in plan.files[:12]:
        lines.append(f"- {_short_entry_name(item.archive_entry_path)} -> {item.remote_path}")
    if len(plan.files) > 12:
        lines.append(f"- ... {len(plan.files) - 12} more")

    lines.append("")
    lines.append("Risk:")
    if plan.warnings:
        lines.extend(f"- {warning}" for warning in _dedupe_lines(plan.warnings)[:8])
    else:
        lines.append("- Warnings: none")
    if ue4ss_external and not any("host/provider" in warning or "managed" in warning for warning in plan.warnings):
        lines.append("- UE4SS: managed by host/provider; runtime will not be replaced")
    lines.append("- Backup: hosted uploads do not create remote backups automatically")
    return "\n".join(lines)


def _is_config_or_metadata_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    return pure.suffix.lower() in _CONFIG_SUFFIXES or name in _METADATA_NAMES


def _short_entry_name(path: str) -> str:
    return PurePosixPath(path).name or str(path)


def _target_label(target: object) -> str:
    if hasattr(target, "value"):
        return target_value_label(str(getattr(target, "value")))
    return target_value_label(str(target))


def _ue4ss_status(
    info: ArchiveInfo,
    warnings: Iterable[str],
    *,
    ue4ss_external: bool = False,
) -> str:
    if info.install_kind == "ue4ss_runtime":
        return "runtime package selected"
    if info.install_kind not in {"ue4ss_mod", "windrose_plus"}:
        return "not required by detected layout"
    if ue4ss_external:
        return "managed outside the app"
    warning_text = " ".join(str(warning).lower() for warning in warnings)
    if "marked external" in warning_text or "managed by host/provider" in warning_text:
        return "managed outside the app"
    if "not detected" in warning_text or "missing" in warning_text:
        return "missing or not detected"
    return "detected for selected target"


def _count_label(count: int, label: str) -> str:
    if count <= 0:
        return ""
    suffix = "" if count == 1 else "s"
    return f"{count} {label}{suffix}"


def _prefix_lines(lines: Iterable[str]) -> list[str]:
    return [f"- {line}" for line in lines]


def _preview_plan_files(files) -> list[str]:
    lines: list[str] = []
    for item in list(files)[:8]:
        lines.append(f"  {_short_entry_name(item.archive_entry_path)} -> {item.dest_path}")
    count = len(files)
    if count > 8:
        lines.append(f"  ... {count - 8} more")
    return lines


def _dedupe_lines(lines: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in lines:
        line = str(raw).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result
