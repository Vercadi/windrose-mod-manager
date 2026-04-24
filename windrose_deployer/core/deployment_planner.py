"""Plan deployment operations before executing them."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional

from ..models.app_paths import AppPaths
from ..models.archive_info import ArchiveEntry, ArchiveInfo, ArchiveType
from ..models.mod_install import InstallTarget
from .framework_deployment_planner import (
    framework_entry_relative_path,
    framework_install_root,
    is_framework_install_kind,
)
from .target_resolver import resolve_pak_target, resolve_loose_target, strip_archive_prefix

log = logging.getLogger(__name__)


@dataclass
class PlannedFile:
    """A single file planned for deployment."""
    archive_entry_path: str
    dest_path: Path
    is_pak: bool = False


@dataclass
class DeploymentPlan:
    """Full plan describing what the installer should do."""
    mod_name: str
    archive_path: str
    target: InstallTarget
    install_type: str
    install_kind: str = "standard_mod"
    selected_variant: Optional[str] = None
    files: list[PlannedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    valid: bool = True

    @property
    def file_count(self) -> int:
        return len(self.files)


def plan_deployment(
    info: ArchiveInfo,
    paths: AppPaths,
    target: InstallTarget,
    selected_variant: Optional[str] = None,
    mod_name: Optional[str] = None,
    selected_entries: Optional[set[str]] = None,
) -> DeploymentPlan:
    """Build a deployment plan from archive analysis and target selection."""
    name = mod_name or PurePosixPath(info.archive_path).stem
    plan = DeploymentPlan(
        mod_name=name,
        archive_path=info.archive_path,
        target=target,
        install_type=info.archive_type.value,
        install_kind=info.install_kind,
        selected_variant=selected_variant,
    )

    if info.archive_type == ArchiveType.UNKNOWN:
        plan.valid = False
        plan.warnings.append("Cannot plan deployment for unknown archive type.")
        return plan

    if is_framework_install_kind(info.install_kind):
        _plan_framework_files(info, plan, paths, target, selected_entries)
        if plan.file_count == 0:
            plan.valid = False
            if not plan.warnings:
                plan.warnings.append("No framework files could be mapped to this target.")
        return plan

    pak_targets = resolve_pak_target(paths, target)
    loose_targets = resolve_loose_target(paths, target, info)

    if not pak_targets and not loose_targets:
        plan.valid = False
        plan.warnings.append("No valid target directories found.")
        return plan

    _plan_paks(info, plan, pak_targets, selected_variant, selected_entries)
    _plan_companions(info, plan, pak_targets, selected_entries)
    _plan_loose(info, plan, loose_targets, selected_entries)

    if plan.file_count == 0:
        plan.valid = False
        plan.warnings.append("No files to deploy after planning.")

    return plan


def _plan_paks(
    info: ArchiveInfo,
    plan: DeploymentPlan,
    pak_targets: list[Path],
    selected_variant: Optional[str],
    selected_entries: Optional[set[str]],
) -> None:
    entries_to_deploy: list[ArchiveEntry] = []

    if info.has_variants and selected_variant:
        for group in info.variant_groups:
            for v in group.variants:
                if PurePosixPath(v.path).name == selected_variant:
                    entries_to_deploy.append(v)
                    break
        non_variant_paks = [
            e for e in info.pak_entries
            if not any(e in g.variants for g in info.variant_groups)
        ]
        entries_to_deploy.extend(non_variant_paks)
    elif info.has_variants and not selected_variant:
        plan.warnings.append("Multi-variant archive but no variant selected — skipping all variant paks.")
        entries_to_deploy = [
            e for e in info.pak_entries
            if not any(e in g.variants for g in info.variant_groups)
        ]
    else:
        entries_to_deploy = list(info.pak_entries)

    if selected_entries:
        entries_to_deploy = [entry for entry in entries_to_deploy if entry.path in selected_entries]

    for entry in entries_to_deploy:
        filename = PurePosixPath(entry.path).name
        for tgt in pak_targets:
            plan.files.append(PlannedFile(
                archive_entry_path=entry.path,
                dest_path=tgt / filename,
                is_pak=True,
            ))


def _plan_framework_files(
    info: ArchiveInfo,
    plan: DeploymentPlan,
    paths: AppPaths,
    target: InstallTarget,
    selected_entries: Optional[set[str]],
) -> None:
    root = framework_install_root(paths, target, info.install_kind)
    if root is None:
        plan.valid = False
        plan.warnings.append("No valid framework target directory found.")
        return

    for entry in [entry for entry in info.entries if not entry.is_dir]:
        if selected_entries and entry.path not in selected_entries:
            continue
        rel = framework_entry_relative_path(info, entry)
        if rel is None:
            continue
        plan.files.append(
            PlannedFile(
                archive_entry_path=entry.path,
                dest_path=root / Path(rel),
                is_pak=entry.is_unreal_asset,
            )
        )

    if info.install_kind == "ue4ss_runtime":
        plan.warnings.append("UE4SS runtime files will be installed under R5\\Binaries\\Win64.")
    elif info.install_kind == "windrose_plus":
        plan.warnings.append(
            "WindrosePlus package files will be installed to the server root. Run its documented installer/rebuild steps where required."
        )


def _plan_companions(
    info: ArchiveInfo,
    plan: DeploymentPlan,
    pak_targets: list[Path],
    selected_entries: Optional[set[str]],
) -> None:
    selected_stems: set[str] = set()
    if selected_entries:
        selected_stems = {
            PurePosixPath(path).stem
            for path in selected_entries
        }
    for entry in info.companion_entries:
        if selected_entries and entry.path not in selected_entries and PurePosixPath(entry.path).stem not in selected_stems:
            continue
        filename = PurePosixPath(entry.path).name
        for tgt in pak_targets:
            plan.files.append(PlannedFile(
                archive_entry_path=entry.path,
                dest_path=tgt / filename,
                is_pak=True,
            ))


def _plan_loose(
    info: ArchiveInfo,
    plan: DeploymentPlan,
    loose_targets: list[Path],
    selected_entries: Optional[set[str]],
) -> None:
    for entry in info.loose_entries:
        if selected_entries and entry.path not in selected_entries:
            continue
        rel = strip_archive_prefix(entry.path, info.root_prefix)
        for tgt in loose_targets:
            plan.files.append(PlannedFile(
                archive_entry_path=entry.path,
                dest_path=tgt / Path(rel),
                is_pak=False,
            ))
