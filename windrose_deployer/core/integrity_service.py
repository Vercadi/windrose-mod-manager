"""Verify and repair managed installs against their source archives."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..models.app_paths import AppPaths
from ..models.mod_install import InstallTarget, ModInstall
from ..utils.filesystem import ensure_dir
from .archive_handler import open_archive
from .archive_inspector import inspect_archive
from .backup_manager import BackupManager
from .deployment_planner import plan_deployment
from .installer import _canonical_installed_path

log = logging.getLogger(__name__)


@dataclass
class VerificationIssue:
    file_path: str
    reason: str


@dataclass
class VerificationResult:
    verified_files: int = 0
    issues: list[VerificationIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def summary(self) -> str:
        parts = [f"{self.verified_files} verified"]
        if self.issues:
            parts.append(f"{len(self.issues)} issue(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return ", ".join(parts)


@dataclass
class RepairResult:
    repaired: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts = [f"{len(self.repaired)} repaired"]
        if self.failed:
            parts.append(f"{len(self.failed)} failed")
        if self.skipped:
            parts.append(f"{len(self.skipped)} skipped")
        return ", ".join(parts)


class IntegrityService:
    def __init__(self, paths: AppPaths, backup_manager: BackupManager | None = None):
        self.paths = paths
        self.backup = backup_manager

    def verify_mod(self, mod: ModInstall) -> VerificationResult:
        result = VerificationResult()
        archive_path = Path(mod.source_archive) if mod.source_archive else None
        if not archive_path or not archive_path.is_file():
            result.warnings.append("Original archive is unavailable; only existence checks were performed.")
            for fp in mod.installed_files:
                if Path(fp).exists():
                    result.verified_files += 1
                else:
                    result.issues.append(VerificationIssue(fp, "missing"))
            return result

        plan = self._plan_for_mod(mod, result.warnings)
        if not plan or not plan.valid:
            for fp in mod.installed_files:
                if Path(fp).exists():
                    result.verified_files += 1
                else:
                    result.issues.append(VerificationIssue(fp, "missing"))
            return result

        actual_map = {
            _canonical_installed_path(fp): Path(fp)
            for fp in mod.installed_files
        }
        reader = open_archive(archive_path)
        try:
            for planned in plan.files:
                actual_path = actual_map.get(str(planned.dest_path), planned.dest_path)
                if not actual_path.exists():
                    result.issues.append(VerificationIssue(str(actual_path), "missing"))
                    continue

                expected = reader.read_file(planned.archive_entry_path)
                current = actual_path.read_bytes()
                if current != expected:
                    result.issues.append(VerificationIssue(str(actual_path), "modified"))
                    continue
                result.verified_files += 1
        finally:
            reader.close()

        return result

    def repair_mod(self, mod: ModInstall) -> RepairResult:
        result = RepairResult()
        if not mod.enabled:
            result.skipped.append("Repair skipped for disabled mod; enable it first.")
            return result

        archive_path = Path(mod.source_archive) if mod.source_archive else None
        if not archive_path or not archive_path.is_file():
            result.failed.append("Original archive is unavailable.")
            return result

        plan = self._plan_for_mod(mod, result.warnings)
        if not plan or not plan.valid:
            result.failed.extend(plan.warnings if plan else ["Repair plan is invalid."])
            return result

        reader = open_archive(archive_path)
        try:
            for planned in plan.files:
                dest = planned.dest_path
                expected = reader.read_file(planned.archive_entry_path)
                current = dest.read_bytes() if dest.exists() else None
                if current == expected:
                    result.skipped.append(str(dest))
                    continue

                try:
                    if dest.exists() and self.backup is not None:
                        self.backup.backup_file(
                            dest,
                            category="installs",
                            description=f"Pre-repair backup of {mod.display_name}",
                        )
                    ensure_dir(dest.parent)
                    dest.write_bytes(expected)
                    result.repaired.append(str(dest))
                    log.info("Repaired managed file: %s", dest)
                except Exception as exc:
                    result.failed.append(f"{dest}: {exc}")
        finally:
            reader.close()

        return result

    def scan_manifest_drift(self, mods: list[ModInstall]) -> list[str]:
        warnings: list[str] = []
        for mod in mods:
            verification = self.verify_mod(mod)
            for issue in verification.issues:
                warnings.append(f"{mod.display_name}: {issue.file_path} ({issue.reason})")
        return warnings

    def _plan_for_mod(self, mod: ModInstall, warnings: list[str]):
        try:
            info = inspect_archive(Path(mod.source_archive))
            target = self._target_for_mod(mod)
            selected_entries = set(mod.component_map.keys()) if mod.component_map else None
            plan = plan_deployment(
                info,
                self.paths,
                target,
                mod.selected_variant,
                mod.display_name,
                selected_entries=selected_entries,
            )
            if not plan.valid:
                warnings.extend(plan.warnings)
            return plan
        except Exception as exc:
            warnings.append(str(exc))
            return None

    @staticmethod
    def _target_for_mod(mod: ModInstall) -> InstallTarget:
        target_values = set(mod.targets)
        if "both" in target_values or {"client", "server"}.issubset(target_values):
            return InstallTarget.BOTH
        if "dedicated_server" in target_values:
            return InstallTarget.DEDICATED_SERVER
        if "server" in target_values:
            return InstallTarget.SERVER
        return InstallTarget.CLIENT
