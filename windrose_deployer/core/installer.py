"""Execute mod install / uninstall / disable / enable operations."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..models.deployment_record import DeployedFile, DeploymentRecord
from ..models.mod_install import InstallTarget, ModInstall
from ..utils.filesystem import ensure_dir, safe_delete
from ..utils.hashing import hash_file
from ..utils.naming import generate_mod_id, timestamp_slug
from .archive_handler import open_archive
from .backup_manager import BackupManager
from .deployment_planner import DeploymentPlan

log = logging.getLogger(__name__)

DISABLED_SUFFIX = ".disabled"


def _is_safe_relative_path(entry_path: str) -> bool:
    """Reject archive entry paths that attempt directory traversal or are absolute."""
    from pathlib import PurePosixPath, PureWindowsPath
    for cls in (PurePosixPath, PureWindowsPath):
        p = cls(entry_path)
        if p.is_absolute():
            return False
        if ".." in p.parts:
            return False
    return True


def _canonical_installed_path(path_str: str) -> str:
    """Return the original managed path even if the file is currently disabled."""
    if path_str.endswith(DISABLED_SUFFIX):
        return path_str[: -len(DISABLED_SUFFIX)]
    return path_str


class Installer:
    """Executes planned deployments and tracks results."""

    def __init__(self, backup_manager: BackupManager):
        self.backup = backup_manager

    def install(self, plan: DeploymentPlan) -> tuple[ModInstall, DeploymentRecord]:
        """Execute a deployment plan and return the install record + deployment record.

        On partial failure, successfully deployed files are still tracked so they
        can be cleanly uninstalled.  The caller is warned via the record notes.
        """
        if not plan.valid:
            raise ValueError(f"Cannot execute invalid plan: {plan.warnings}")

        mod_id = generate_mod_id()
        archive_path = Path(plan.archive_path)
        archive_hash: Optional[str] = None
        try:
            archive_hash = hash_file(archive_path)
        except Exception as exc:
            log.warning("Could not hash archive: %s", exc)

        deployed_files: list[DeployedFile] = []
        installed_paths: list[str] = []
        backed_up_paths: list[str] = []
        backup_map: dict[str, str] = {}
        failed_count = 0

        reader = open_archive(archive_path)
        try:
            for pf in plan.files:
                if not _is_safe_relative_path(pf.archive_entry_path):
                    log.warning("Skipping unsafe archive path: %s", pf.archive_entry_path)
                    failed_count += 1
                    continue

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
                    data = reader.read_file(pf.archive_entry_path)
                    dest.write_bytes(data)
                    log.info("Installed: %s", dest)
                except Exception as exc:
                    log.error("Failed to extract %s -> %s: %s", pf.archive_entry_path, dest, exc)
                    failed_count += 1
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
                    backup_map[str(dest)] = backup_record.backup_path
        finally:
            reader.close()

        if failed_count and not deployed_files:
            raise RuntimeError(
                f"Install failed completely — {failed_count} file(s) could not be extracted."
            )

        notes = f"Installed {len(deployed_files)} files"
        if failed_count:
            notes += f" ({failed_count} failed)"
            log.warning("Partial install: %d succeeded, %d failed", len(deployed_files), failed_count)

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
            backup_map=backup_map,
            enabled=True,
        )

        record = DeploymentRecord(
            mod_id=mod_id,
            target=plan.target.value,
            action="install",
            display_name=plan.mod_name,
            source_archive=str(archive_path),
            files=deployed_files,
            notes=notes,
        )

        log.info("Install complete: %s — %s", mod_id, notes)
        return mod, record

    def uninstall(self, mod: ModInstall) -> DeploymentRecord:
        """Remove all files tracked by the mod install and restore any backed-up originals."""
        removed: list[DeployedFile] = []
        restored_count = 0
        for fp in mod.installed_files:
            p = Path(fp)
            canonical_path = Path(_canonical_installed_path(fp))
            deleted = False
            if p.exists():
                safe_delete(p)
                deleted = True
            disabled = Path(fp + DISABLED_SUFFIX) if not fp.endswith(DISABLED_SUFFIX) else None
            if disabled and disabled.exists():
                safe_delete(disabled)
                deleted = True

            # Restore the original file from backup if one was saved
            backup_path = mod.backup_map.get(str(canonical_path)) or mod.backup_map.get(fp)
            if backup_path:
                bp = Path(backup_path)
                if bp.is_file():
                    ensure_dir(canonical_path.parent)
                    import shutil
                    shutil.copy2(str(bp), str(canonical_path))
                    restored_count += 1
                    log.info("Restored original: %s from %s", canonical_path, bp)

            if deleted:
                removed.append(DeployedFile(source_archive_path="", dest_path=fp,
                                            backup_path=backup_path))

        notes = f"Removed {len(removed)} files"
        if restored_count:
            notes += f", restored {restored_count} originals"

        record = DeploymentRecord(
            mod_id=mod.mod_id,
            target=",".join(mod.targets),
            action="uninstall",
            display_name=mod.display_name,
            source_archive=mod.source_archive,
            files=removed,
            notes=notes,
        )
        log.info("Uninstall complete: %s — %d files removed, %d restored",
                 mod.mod_id, len(removed), restored_count)
        return record

    def disable(self, mod: ModInstall) -> bool:
        """Disable a mod by renaming its files with a .disabled suffix.

        The manifest's installed_files is updated to the .disabled paths so
        that uninstall/enable stay consistent.
        """
        count = 0
        updated_paths: list[str] = []
        for fp in mod.installed_files:
            p = Path(fp)
            if p.exists() and not fp.endswith(DISABLED_SUFFIX):
                disabled = p.with_name(p.name + DISABLED_SUFFIX)
                p.rename(disabled)
                updated_paths.append(str(disabled))
                count += 1
                log.info("Disabled: %s -> %s", p.name, disabled.name)
            else:
                updated_paths.append(fp)

        mod.installed_files = updated_paths
        mod.enabled = False
        log.info("Disabled mod %s — %d files renamed", mod.mod_id, count)
        return count > 0

    def enable(self, mod: ModInstall) -> bool:
        """Re-enable a disabled mod by removing the .disabled suffix."""
        count = 0
        restored_paths: list[str] = []
        for fp in mod.installed_files:
            p = Path(fp)
            if p.exists() and fp.endswith(DISABLED_SUFFIX):
                original = Path(fp[: -len(DISABLED_SUFFIX)])
                p.rename(original)
                restored_paths.append(str(original))
                count += 1
                log.info("Enabled: %s -> %s", p.name, original.name)
            elif not p.exists():
                # Try to find the disabled version even if manifest has original path
                disabled = Path(fp + DISABLED_SUFFIX)
                if disabled.exists():
                    disabled.rename(p)
                    restored_paths.append(fp)
                    count += 1
                    log.info("Enabled: %s -> %s", disabled.name, p.name)
                else:
                    restored_paths.append(fp)
            else:
                restored_paths.append(fp)

        mod.installed_files = restored_paths
        mod.enabled = True
        log.info("Enabled mod %s — %d files restored", mod.mod_id, count)
        return count > 0
