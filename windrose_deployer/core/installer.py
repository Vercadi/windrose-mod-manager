"""Execute mod install / uninstall / disable / enable operations."""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Optional

from ..models.deployment_record import DeployedFile, DeploymentRecord
from ..models.mod_install import InstallTarget, ModInstall
from ..utils.filesystem import ensure_dir, safe_delete
from ..utils.hashing import hash_file
from ..utils.naming import sanitize_mod_id, timestamp_slug
from .backup_manager import BackupManager
from .deployment_planner import DeploymentPlan

log = logging.getLogger(__name__)

DISABLED_SUFFIX = ".disabled"


class Installer:
    """Executes planned deployments and tracks results."""

    def __init__(self, backup_manager: BackupManager):
        self.backup = backup_manager

    def install(self, plan: DeploymentPlan) -> tuple[ModInstall, DeploymentRecord]:
        """Execute a deployment plan and return the install record + deployment record."""
        if not plan.valid:
            raise ValueError(f"Cannot execute invalid plan: {plan.warnings}")

        mod_id = sanitize_mod_id(plan.mod_name)
        archive_path = Path(plan.archive_path)
        archive_hash: Optional[str] = None
        try:
            archive_hash = hash_file(archive_path)
        except Exception as exc:
            log.warning("Could not hash archive: %s", exc)

        deployed_files: list[DeployedFile] = []
        installed_paths: list[str] = []
        backed_up_paths: list[str] = []

        with zipfile.ZipFile(archive_path, "r") as zf:
            for pf in plan.files:
                dest = pf.dest_path
                ensure_dir(dest.parent)

                backup_record = None
                was_overwrite = False
                if dest.exists():
                    was_overwrite = True
                    backup_record = self.backup.backup_file(
                        dest,
                        category="installs",
                        description=f"Overwritten by {plan.mod_name}",
                    )

                try:
                    data = zf.read(pf.archive_entry_path)
                    dest.write_bytes(data)
                    log.info("Installed: %s", dest)
                except Exception as exc:
                    log.error("Failed to extract %s -> %s: %s", pf.archive_entry_path, dest, exc)
                    continue

                installed_paths.append(str(dest))
                df = DeployedFile(
                    source_archive_path=pf.archive_entry_path,
                    dest_path=str(dest),
                    backup_path=backup_record.backup_path if backup_record else None,
                    was_overwrite=was_overwrite,
                )
                deployed_files.append(df)
                if backup_record:
                    backed_up_paths.append(backup_record.backup_path)

        mod = ModInstall(
            mod_id=mod_id,
            display_name=plan.mod_name,
            source_archive=str(archive_path),
            archive_hash=archive_hash,
            install_type=plan.install_type,
            selected_variant=plan.selected_variant,
            targets=[plan.target.value],
            installed_files=installed_paths,
            backed_up_files=backed_up_paths,
            enabled=True,
        )

        record = DeploymentRecord(
            mod_id=mod_id,
            target=plan.target.value,
            action="install",
            files=deployed_files,
            notes=f"Installed {len(deployed_files)} files",
        )

        log.info("Install complete: %s — %d files deployed", mod_id, len(deployed_files))
        return mod, record

    def uninstall(self, mod: ModInstall) -> DeploymentRecord:
        """Remove all files tracked by the mod install."""
        removed: list[DeployedFile] = []
        for fp in mod.installed_files:
            p = Path(fp)
            if p.exists():
                safe_delete(p)
                removed.append(DeployedFile(source_archive_path="", dest_path=fp))
            disabled = p.with_suffix(p.suffix + DISABLED_SUFFIX)
            if disabled.exists():
                safe_delete(disabled)

        record = DeploymentRecord(
            mod_id=mod.mod_id,
            target=",".join(mod.targets),
            action="uninstall",
            files=removed,
            notes=f"Removed {len(removed)} files",
        )
        log.info("Uninstall complete: %s — %d files removed", mod.mod_id, len(removed))
        return record

    def disable(self, mod: ModInstall) -> bool:
        """Disable a mod by renaming its files with a .disabled suffix."""
        count = 0
        new_paths: list[str] = []
        for fp in mod.installed_files:
            p = Path(fp)
            if p.exists():
                disabled = p.with_suffix(p.suffix + DISABLED_SUFFIX)
                p.rename(disabled)
                new_paths.append(str(disabled))
                count += 1
                log.info("Disabled: %s -> %s", p.name, disabled.name)
            else:
                new_paths.append(fp)

        mod.installed_files = [
            (f if not Path(f).exists() else f)
            for f in mod.installed_files
        ]
        mod.enabled = False
        log.info("Disabled mod %s — %d files renamed", mod.mod_id, count)
        return count > 0

    def enable(self, mod: ModInstall) -> bool:
        """Re-enable a disabled mod by removing the .disabled suffix."""
        count = 0
        restored: list[str] = []
        for fp in mod.installed_files:
            p = Path(fp)
            disabled = p.with_suffix(p.suffix + DISABLED_SUFFIX)
            if disabled.exists():
                original = Path(fp)
                disabled.rename(original)
                restored.append(str(original))
                count += 1
                log.info("Enabled: %s -> %s", disabled.name, original.name)
            else:
                restored.append(fp)

        mod.installed_files = restored
        mod.enabled = True
        log.info("Enabled mod %s — %d files restored", mod.mod_id, count)
        return count > 0
