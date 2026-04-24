"""Read/write known Windrose RCON UE4SS config files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Optional

from ..models.remote_profile import RemoteProfile
from .backup_manager import BackupManager
from .remote_config_service import remote_source_uri
from .remote_provider import RemoteProvider
from .remote_provider_factory import create_remote_provider


@dataclass
class RconSettings:
    port: int = 27065
    password: str = ""
    enabled: bool = False
    source_path: str = ""

    def to_text(self) -> str:
        return (
            "# WindroseRCON Configuration\n"
            "# RCON server port\n"
            f"Port={self.port}\n\n"
            "# RCON password\n"
            f"Password={self.password}\n"
        )


def parse_rcon_settings(text: str, *, source_path: str = "") -> RconSettings:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip()
    port = 27065
    try:
        port = int(values.get("port", port))
    except ValueError:
        port = 27065
    return RconSettings(
        port=port,
        password=values.get("password", ""),
        enabled=True,
        source_path=source_path,
    )


class RconConfigService:
    def __init__(self, backup_manager: BackupManager, provider_factory=None):
        self.backup = backup_manager
        self.provider_factory = provider_factory or create_remote_provider

    @staticmethod
    def local_settings_path(root: Path | None) -> Optional[Path]:
        if root is None:
            return None
        return root / "R5" / "Binaries" / "Win64" / "ue4ss" / "Mods" / "WindroseRCON" / "settings.ini"

    @staticmethod
    def remote_settings_path(profile: RemoteProfile) -> str:
        root = profile.normalized_root_dir()
        if not root:
            return ""
        return str(PurePosixPath(root).joinpath("R5", "Binaries", "Win64", "ue4ss", "Mods", "WindroseRCON", "settings.ini"))

    def load_local(self, root: Path | None) -> Optional[RconSettings]:
        path = self.local_settings_path(root)
        if path is None or not path.is_file():
            return None
        return parse_rcon_settings(path.read_text(encoding="utf-8", errors="replace"), source_path=str(path))

    def save_local(self, root: Path | None, settings: RconSettings) -> bool:
        path = self.local_settings_path(root)
        if path is None:
            return False
        if path.exists():
            self.backup.backup_file(
                path,
                category="rcon_config",
                description="Pre-save backup of WindroseRCON settings.ini",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(settings.to_text(), encoding="utf-8")
        return True

    def load_remote(self, profile: RemoteProfile) -> Optional[RconSettings]:
        remote_path = self.remote_settings_path(profile)
        if not remote_path:
            return None
        provider: RemoteProvider | None = None
        try:
            provider = self.provider_factory(profile)
            data = provider.read_bytes(remote_path)
            return parse_rcon_settings(data.decode("utf-8", errors="replace"), source_path=remote_path)
        except Exception:
            return None
        finally:
            if provider is not None:
                provider.close()

    def save_remote(self, profile: RemoteProfile, settings: RconSettings) -> bool:
        remote_path = self.remote_settings_path(profile)
        if not remote_path:
            return False
        provider: RemoteProvider | None = None
        try:
            provider = self.provider_factory(profile)
            try:
                data = provider.read_bytes(remote_path)
                self.backup.backup_bytes(
                    source_path=remote_source_uri(profile.protocol, profile.profile_id, remote_path),
                    filename="settings.ini",
                    data=data,
                    category="remote_rcon_config",
                    description="Pre-save backup of hosted WindroseRCON settings.ini",
                )
            except Exception:
                pass
            provider.upload_bytes(settings.to_text().encode("utf-8"), remote_path)
            return True
        finally:
            if provider is not None:
                provider.close()
