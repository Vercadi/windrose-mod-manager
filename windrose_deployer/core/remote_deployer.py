"""Plan and execute remote deployments against rented servers."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from ..models.archive_info import ArchiveEntry, ArchiveInfo
from ..models.remote_profile import RemoteProfile, normalize_remote_protocol
from .archive_handler import open_archive
from .framework_deployment_planner import (
    framework_entry_relative_path,
    is_framework_install_kind,
    remote_framework_install_root,
)
from .installer import _is_safe_relative_path
from .remote_provider import RemoteProvider
from .remote_provider_factory import create_remote_provider
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
    install_kind: str = "standard_mod"
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
        install_kind=info.install_kind,
    )

    remote_mods_dir = profile.resolved_mods_dir()
    remote_root_dir = profile.normalized_root_dir()

    if is_framework_install_kind(info.install_kind):
        if not remote_root_dir:
            plan.valid = False
            plan.warnings.append(
                "Hosted framework installs require Server Folder so the app can target R5/Binaries/Win64."
            )
            return plan
        framework_root = remote_framework_install_root(remote_root_dir, info.install_kind)
        for entry in [entry for entry in info.entries if not entry.is_dir]:
            rel = framework_entry_relative_path(info, entry)
            if rel is None:
                continue
            plan.files.append(
                RemotePlannedFile(
                    archive_entry_path=entry.path,
                    remote_path=_join_remote(framework_root, rel),
                    is_pak=entry.is_unreal_asset,
                )
            )
        if info.install_kind == "ue4ss_runtime":
            plan.warnings.append("Hosted UE4SS runtime files will be uploaded under R5/Binaries/Win64.")
        elif info.install_kind == "windrose_plus":
            plan.warnings.append(
                "WindrosePlus hosted upload is file deployment only. Dashboard/rebuild/restart behavior depends on your host."
            )
        if not plan.files:
            plan.valid = False
            plan.warnings.append("No framework files could be mapped for hosted deployment.")
        return plan

    if not remote_mods_dir:
        plan.valid = False
        plan.warnings.append(
            "Hosted mods directory is required. Set Server Folder, use '.', or fill the Mods Folder Override."
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
                "This archive contains loose files. Configure Server Folder first, or use explicit hosted path overrides."
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
        self.provider_factory = provider_factory or create_remote_provider

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
                    return False, self._missing_remote_path_message(profile, "remote root", root_dir)
                notes.append(f"root OK: {root_dir}")

            if mods_dir:
                if not provider.path_exists(mods_dir):
                    if profile.has_explicit_mods_dir():
                        return False, self._missing_remote_path_message(profile, "mods folder", mods_dir)
                    notes.append(f"mods dir missing (will be created on first install): {mods_dir}")
                else:
                    notes.append(f"mods dir OK: {mods_dir}")

            if server_desc:
                if not provider.path_exists(server_desc):
                    return False, (
                        "Connected, but ServerDescription.json was not found at "
                        f"{server_desc}. Check Server Folder, or paste the exact file path into "
                        "Server Settings File Override."
                        + self._remote_path_hint(profile)
                    )
                notes.append(f"server config OK: {server_desc}")

            if save_root:
                if not provider.path_exists(save_root):
                    return False, self._missing_remote_path_message(profile, "save root", save_root)
                notes.append(f"save root OK: {save_root}")

            if notes:
                return True, "Connection successful. " + " | ".join(notes)
            return True, (
                "Connection successful. Set Server Folder to derive Windrose paths, "
                "enter '.' if the login already opens in the server root, "
                "or leave it blank and fill the overrides manually."
            )
        except Exception as exc:
            message = self._friendly_connection_error(profile, exc)
            if "paramiko is required" in message.lower():
                message += " Run 'python -m pip install -r requirements.txt' when testing from source."
            return False, message
        finally:
            if provider is not None:
                provider.close()

    def list_remote_files(self, profile: RemoteProfile, remote_dir: str | None = None) -> list[str]:
        target_dir = remote_dir or profile.resolved_mods_dir()
        if not target_dir:
            raise ValueError("Set Server Folder, enter '.', or fill the Mods Folder Override first.")
        provider = self.provider_factory(profile)
        try:
            if not provider.path_exists(target_dir):
                if remote_dir is not None or profile.has_explicit_mods_dir():
                    raise FileNotFoundError(self._missing_remote_path_message(profile, "mods folder", target_dir))
                return []
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

    def delete_remote_files(self, profile: RemoteProfile, remote_paths: list[str]) -> tuple[list[str], list[str]]:
        deleted: list[str] = []
        failed: list[str] = []
        provider = self.provider_factory(profile)
        try:
            for remote_path in remote_paths:
                try:
                    provider.delete_file(remote_path)
                    deleted.append(remote_path)
                    log.info("Deleted remote file: %s", remote_path)
                except Exception as exc:
                    log.error("Failed remote delete %s: %s", remote_path, exc)
                    failed.append(f"{PurePosixPath(remote_path).name}: {exc}")
        finally:
            provider.close()
        return deleted, failed

    def restart_remote(self, profile: RemoteProfile) -> tuple[bool, str]:
        if not profile.supports_remote_execute():
            return False, "Restart commands are only available for SFTP/SSH profiles. FTP supports file access only."
        if not profile.restart_command.strip():
            return False, "No restart command is configured for this profile."

        provider = self.provider_factory(profile)
        try:
            return provider.execute(profile.restart_command.strip())
        finally:
            provider.close()

    @staticmethod
    def _friendly_connection_error(profile: RemoteProfile, exc: Exception) -> str:
        protocol = normalize_remote_protocol(profile.protocol)
        message = str(exc).strip() or exc.__class__.__name__
        lowered = message.lower()

        if protocol == "sftp":
            if "error reading ssh protocol banner" in lowered or "banner timeout" in lowered:
                return (
                    "Connection failed. The selected protocol is SFTP, but the host did not respond like an SFTP/SSH service. "
                    "The selected protocol likely does not match the host. Use the provider's FTP Info or SFTP Info exactly as shown."
                )
            if "authentication failed" in lowered:
                return "Connection failed. The SFTP username, password, or private key was rejected."
            return message

        if protocol == "ftp":
            if "timed out" in lowered or "connection reset" in lowered or "connection refused" in lowered:
                return (
                    "Connection failed. The selected protocol is FTP, but the host did not respond like an FTP service. "
                    "Check that the provider really gave FTP credentials, the port is correct, and the selected protocol matches the host."
                )
            if "530" in lowered or "login incorrect" in lowered or "not logged in" in lowered:
                return "Connection failed. The FTP username or password was rejected."
            if "502" in lowered or "500" in lowered or "unknown command" in lowered:
                return (
                    "Connection failed. The selected protocol is FTP, but the host response suggests the protocol may not match. "
                    "If the provider offers SFTP Info instead, switch the profile to SFTP."
                )
            return message

        return message

    @staticmethod
    def _missing_remote_path_message(profile: RemoteProfile, label: str, remote_path: str) -> str:
        return f"Connected, but {label} was not found: {remote_path}.{RemoteDeploymentService._remote_path_hint(profile)}"

    @staticmethod
    def _remote_path_hint(profile: RemoteProfile) -> str:
        if normalize_remote_protocol(profile.protocol) == "ftp":
            return (
                " For FTP hosts such as Nitrado, paths are relative to the FTP login root, not the web-panel "
                "or operating-system path. Use the path exactly as it appears in an FTP client. If FTP opens "
                "inside the Windrose server folder, set Server Folder to '.' and leave Mods Folder Override "
                "blank, or set Mods Folder Override to R5/Content/Paks/~mods."
            )
        return (
            " If your login opens directly inside the Windrose server folder, set Server Folder to '.' and "
            "leave Mods Folder Override blank, or set Mods Folder Override to R5/Content/Paks/~mods."
        )
