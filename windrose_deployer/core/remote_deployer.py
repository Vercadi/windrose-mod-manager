"""Plan and execute remote deployments against rented servers."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from ..models.archive_info import ArchiveEntry, ArchiveInfo
from ..models.remote_profile import RemoteProfile
from .archive_handler import open_archive
from .installer import _is_safe_relative_path
from .remote_provider import RemoteProvider
from .sftp_provider import SftpProvider
from .target_resolver import strip_archive_prefix

log = logging.getLogger(__name__)


@dataclass
class RemotePlannedFile:
    archive_entry_path: str
    remote_path: str
    is_pak: bool = False


@dataclass
class RemoteDeploymentPlan:
    profile_id: str
    mod_name: str
    archive_path: str
    selected_variant: Optional[str] = None
    files: list[RemotePlannedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    valid: bool = True

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass
class RemoteDeploymentResult:
    uploaded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts = [f"{len(self.uploaded)} uploaded"]
        if self.failed:
            parts.append(f"{len(self.failed)} failed")
        if self.skipped:
            parts.append(f"{len(self.skipped)} skipped")
        return ", ".join(parts)


def plan_remote_deployment(
    info: ArchiveInfo,
    profile: RemoteProfile,
    *,
    selected_variant: Optional[str] = None,
    mod_name: Optional[str] = None,
) -> RemoteDeploymentPlan:
    plan = RemoteDeploymentPlan(
        profile_id=profile.profile_id,
        mod_name=mod_name or Path(info.archive_path).stem,
        archive_path=info.archive_path,
        selected_variant=selected_variant,
    )

    remote_mods_dir = profile.resolved_mods_dir()
    remote_root_dir = profile.normalized_root_dir()
    if not remote_mods_dir:
        plan.valid = False
        plan.warnings.append(
            "Remote mods directory is required. Set Remote Game/Server Root or Remote Mods Dir."
        )
        return plan

    pak_entries = _select_pak_entries(info, selected_variant, plan)
    for entry in pak_entries:
        plan.files.append(RemotePlannedFile(
            archive_entry_path=entry.path,
            remote_path=_join_remote(remote_mods_dir, PurePosixPath(entry.path).name),
            is_pak=True,
        ))

    for entry in info.companion_entries:
        plan.files.append(RemotePlannedFile(
            archive_entry_path=entry.path,
            remote_path=_join_remote(remote_mods_dir, PurePosixPath(entry.path).name),
            is_pak=True,
        ))

    if info.loose_entries:
        if not remote_root_dir:
            plan.valid = False
            plan.warnings.append(
                "This archive contains loose files. Configure Remote Game/Server Root first."
            )
        else:
            for entry in info.loose_entries:
                rel = strip_archive_prefix(entry.path, info.root_prefix)
                plan.files.append(RemotePlannedFile(
                    archive_entry_path=entry.path,
                    remote_path=_join_remote(remote_root_dir, rel),
                    is_pak=False,
                ))

    if not plan.files:
        plan.valid = False
        if not plan.warnings:
            plan.warnings.append("No files were selected for remote deployment.")

    return plan


def _select_pak_entries(
    info: ArchiveInfo,
    selected_variant: Optional[str],
    plan: RemoteDeploymentPlan,
) -> list[ArchiveEntry]:
    if not info.has_variants:
        return list(info.pak_entries)

    if not selected_variant:
        plan.valid = False
        plan.warnings.append("Select a variant before deploying this archive remotely.")
        return [
            entry for entry in info.pak_entries
            if not any(entry in group.variants for group in info.variant_groups)
        ]

    selected: list[ArchiveEntry] = []
    for group in info.variant_groups:
        for entry in group.variants:
            if PurePosixPath(entry.path).name == selected_variant:
                selected.append(entry)
                break
    selected.extend(
        entry for entry in info.pak_entries
        if not any(entry in group.variants for group in info.variant_groups)
    )
    return selected


def _join_remote(root: str, rel: str) -> str:
    root_path = PurePosixPath(root)
    rel_path = PurePosixPath(str(rel).replace("\\", "/"))
    return str(root_path.joinpath(rel_path))


class RemoteDeploymentService:
    def __init__(self, provider_factory: Callable[[RemoteProfile], RemoteProvider] | None = None):
        self.provider_factory = provider_factory or (lambda profile: SftpProvider(profile))

    def test_connection(self, profile: RemoteProfile) -> tuple[bool, str]:
        provider: RemoteProvider | None = None
        try:
            provider = self.provider_factory(profile)
            notes: list[str] = []
            root_dir = profile.normalized_root_dir()
            mods_dir = profile.resolved_mods_dir()
            server_desc = profile.resolved_server_description_path()
            save_root = profile.resolved_save_root()

            if root_dir:
                if not provider.path_exists(root_dir):
                    return False, f"Connected, but remote root was not found: {root_dir}"
                notes.append(f"root OK: {root_dir}")

            if mods_dir:
                if not provider.path_exists(mods_dir):
                    return False, f"Connected, but mods dir was not found: {mods_dir}"
                notes.append(f"mods dir OK: {mods_dir}")

            if server_desc:
                if not provider.path_exists(server_desc):
                    return False, f"Connected, but ServerDescription.json was not found: {server_desc}"
                notes.append(f"server config OK: {server_desc}")

            if save_root:
                if not provider.path_exists(save_root):
                    return False, f"Connected, but save root was not found: {save_root}"
                notes.append(f"save root OK: {save_root}")

            if notes:
                return True, "Connection successful. " + " | ".join(notes)
            return True, "Connection successful. Set Remote Game/Server Root next to derive paths."
        except Exception as exc:
            message = str(exc)
            if "paramiko is required" in message.lower():
                message += " Run 'python -m pip install -r requirements.txt' when testing from source."
            return False, message
        finally:
            if provider is not None:
                provider.close()

    def list_remote_files(self, profile: RemoteProfile, remote_dir: str | None = None) -> list[str]:
        target_dir = remote_dir or profile.resolved_mods_dir()
        if not target_dir:
            raise ValueError("Set Remote Game/Server Root or Remote Mods Dir first.")
        provider = self.provider_factory(profile)
        try:
            return provider.list_files(target_dir)
        finally:
            provider.close()

    def deploy(self, plan: RemoteDeploymentPlan, profile: RemoteProfile) -> RemoteDeploymentResult:
        result = RemoteDeploymentResult(warnings=list(plan.warnings))
        if not plan.valid:
            result.failed.extend(plan.warnings or ["Remote deployment plan is invalid."])
            return result

        provider = self.provider_factory(profile)
        reader = open_archive(Path(plan.archive_path))
        try:
            for item in plan.files:
                if not _is_safe_relative_path(item.archive_entry_path):
                    result.skipped.append(f"{item.archive_entry_path} (unsafe path)")
                    continue

                try:
                    data = reader.read_file(item.archive_entry_path)
                    provider.upload_bytes(data, item.remote_path)
                    result.uploaded.append(item.remote_path)
                    log.info("Uploaded remote file: %s", item.remote_path)
                except Exception as exc:
                    log.error("Failed remote upload %s -> %s: %s",
                              item.archive_entry_path, item.remote_path, exc)
                    result.failed.append(f"{item.archive_entry_path}: {exc}")
        finally:
            reader.close()
            provider.close()

        return result

    def restart_remote(self, profile: RemoteProfile) -> tuple[bool, str]:
        if not profile.restart_command.strip():
            return False, "No restart command is configured for this profile."

        provider = self.provider_factory(profile)
        try:
            return provider.execute(profile.restart_command.strip())
        finally:
            provider.close()
