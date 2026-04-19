"""Factory helpers for hosted remote providers."""
from __future__ import annotations

from ..models.remote_profile import RemoteProfile, normalize_remote_protocol
from .ftp_provider import FtpProvider
from .remote_provider import RemoteProvider
from .sftp_provider import SftpProvider


def create_remote_provider(profile: RemoteProfile) -> RemoteProvider:
    protocol = normalize_remote_protocol(profile.protocol)
    if protocol == "ftp":
        return FtpProvider(profile)
    return SftpProvider(profile)
