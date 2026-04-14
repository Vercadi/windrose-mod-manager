"""Detect file conflicts between installed mods and planned deployments."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.mod_install import ModInstall
from .deployment_planner import DeploymentPlan
from .manifest_store import ManifestStore

log = logging.getLogger(__name__)


@dataclass
class Conflict:
    file_path: str
    existing_mod_id: str
    incoming_mod_name: str
    description: str


@dataclass
class ConflictReport:
    conflicts: list[Conflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def summary(self) -> str:
        parts: list[str] = []
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} file conflict(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return ", ".join(parts) if parts else "No conflicts"


def check_plan_conflicts(plan: DeploymentPlan, manifest: ManifestStore) -> ConflictReport:
    """Check a deployment plan against existing installs for conflicts."""
    report = ConflictReport()
    files_map = manifest.get_files_map()

    for pf in plan.files:
        dest = str(pf.dest_path)
        if dest in files_map:
            for existing_mod_id in files_map[dest]:
                report.conflicts.append(Conflict(
                    file_path=dest,
                    existing_mod_id=existing_mod_id,
                    incoming_mod_name=plan.mod_name,
                    description=f"'{plan.mod_name}' will overwrite a file from '{existing_mod_id}'",
                ))

    if plan.target.value == "client":
        _check_sync_warning(plan, manifest, report)

    report.warnings.extend(plan.warnings)

    if report.has_conflicts:
        log.warning("Conflict report: %s", report.summary)

    return report


def check_existing_conflicts(manifest: ManifestStore) -> ConflictReport:
    """Scan all installed mods for file overlaps."""
    report = ConflictReport()
    files_map = manifest.get_files_map()

    for fp, mod_ids in files_map.items():
        if len(mod_ids) > 1:
            report.conflicts.append(Conflict(
                file_path=fp,
                existing_mod_id=mod_ids[0],
                incoming_mod_name=mod_ids[1],
                description=f"File shared by: {', '.join(mod_ids)}",
            ))

    return report


def _check_sync_warning(plan: DeploymentPlan, manifest: ManifestStore, report: ConflictReport) -> None:
    """Warn if a mod is only being deployed to client but a server install exists."""
    for mod in manifest.list_mods():
        if mod.display_name == plan.mod_name and "server" in mod.targets and "client" not in mod.targets:
            report.warnings.append(
                f"'{plan.mod_name}' is already installed on server but not client — consider syncing."
            )
