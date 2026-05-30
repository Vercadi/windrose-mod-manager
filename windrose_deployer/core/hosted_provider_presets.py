"""Hosted provider preset helpers."""
from __future__ import annotations

from dataclasses import dataclass

from ..models.remote_profile import RemoteProfile, normalize_remote_protocol


@dataclass(frozen=True)
class HostedProviderPreset:
    label: str
    protocol: str
    port: int
    remote_root_dir: str = ""
    remote_mods_dir: str = ""
    status: str = ""


NITRADO_FTP_PRESET = HostedProviderPreset(
    label="Nitrado FTP",
    protocol="ftp",
    port=21,
    remote_root_dir="windrose",
    remote_mods_dir="windrose/Mods",
    status=(
        "Nitrado FTP preset applied. Use FTP Credentials from the Nitrado panel. "
        "This uses Server Folder = windrose and uploads pak mods to windrose/Mods. "
        "If your FTP browser does not show windrose/Mods, clear Mods Folder Override "
        "to use the normal derived R5/Content/Paks/~mods path."
    ),
)


def apply_hosted_provider_preset(
    profile: RemoteProfile,
    preset: HostedProviderPreset,
    *,
    fill_paths: bool = True,
) -> RemoteProfile:
    """Return a profile copy with provider preset connection/path values applied."""
    updated = RemoteProfile(
        profile_id=profile.profile_id,
        name=profile.name,
        protocol=normalize_remote_protocol(preset.protocol),
        host=profile.host,
        port=preset.port,
        username=profile.username,
        auth_mode="password" if normalize_remote_protocol(preset.protocol) == "ftp" else profile.auth_mode,
        password=profile.password,
        private_key_path="" if normalize_remote_protocol(preset.protocol) == "ftp" else profile.private_key_path,
        remote_root_dir=profile.remote_root_dir,
        remote_mods_dir=profile.remote_mods_dir,
        remote_server_description_path=profile.remote_server_description_path,
        remote_save_root=profile.remote_save_root,
        restart_command="" if normalize_remote_protocol(preset.protocol) == "ftp" else profile.restart_command,
        ue4ss_managed_externally=profile.ue4ss_managed_externally,
    )
    if fill_paths:
        updated.remote_root_dir = preset.remote_root_dir or updated.remote_root_dir
        updated.remote_mods_dir = preset.remote_mods_dir or updated.remote_mods_dir
    return updated
