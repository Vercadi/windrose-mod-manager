"""Remote ServerDescription.json and WorldDescription.json support over hosted transports."""
from __future__ import annotations

import json
import logging
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import urlsplit

from ..models.remote_profile import RemoteProfile, normalize_remote_protocol
from ..models.server_config import ServerConfig
from ..models.world_config import WorldConfig
from .backup_manager import BackupManager, BackupRecord
from .remote_provider_factory import create_remote_provider
from .remote_profile_store import RemoteProfileStore
from .remote_provider import RemoteProvider

log = logging.getLogger(__name__)


def remote_source_uri(protocol: str, profile_id: str, remote_path: str) -> str:
    scheme = normalize_remote_protocol(protocol)
    normalized = remote_path if remote_path.startswith("/") else f"/{remote_path}"
    return f"{scheme}://{profile_id}{normalized}"


def parse_remote_source_uri(source_uri: str) -> tuple[str, str, str]:
    parsed = urlsplit(source_uri)
    scheme = normalize_remote_protocol(parsed.scheme)
    if scheme not in {"sftp", "ftp"}:
        raise ValueError(f"Unsupported remote source uri: {source_uri}")
    profile_id = parsed.netloc
    remote_path = parsed.path or "/"
    return scheme, profile_id, remote_path


class RemoteConfigService:
    def __init__(
        self,
        backup_manager: BackupManager,
        profile_store: RemoteProfileStore,
        provider_factory=None,
    ):
        self.backup = backup_manager
        self.profile_store = profile_store
        self.provider_factory = provider_factory or create_remote_provider

    def load_server(self, profile: RemoteProfile) -> Optional[ServerConfig]:
        remote_path = profile.resolved_server_description_path()
        if not remote_path:
            log.warning("Remote server description path is not configured for %s", profile.name)
            return None

        provider = None
        try:
            provider = self.provider_factory(profile)
            data = json.loads(provider.read_bytes(remote_path).decode("utf-8"))
            config = ServerConfig.from_json_dict(data)
            log.info("Loaded remote server config from %s", remote_path)
            return config
        except Exception as exc:
            log.error("Failed to load remote server config %s: %s", remote_path, exc)
            return None
        finally:
            if provider is not None:
                provider.close()

    def save_server(self, profile: RemoteProfile, config: ServerConfig) -> tuple[bool, list[str]]:
        remote_path = profile.resolved_server_description_path()
        if not remote_path:
            return False, ["Remote ServerDescription.json path is not configured."]

        errors = config.validate()
        if errors:
            return False, errors

        provider = None
        try:
            provider = self.provider_factory(profile)
            self._backup_remote_file(
                provider,
                profile,
                remote_path,
                category="remote_server_config",
                description="Pre-save backup of remote ServerDescription.json",
            )
            payload = json.dumps(config.to_json_dict(), indent=2, ensure_ascii=False).encode("utf-8")
            provider.upload_bytes(payload, remote_path)
            log.info("Saved remote server config to %s", remote_path)
            return True, []
        except Exception as exc:
            log.error("Failed to save remote server config: %s", exc)
            return False, [str(exc)]
        finally:
            if provider is not None:
                provider.close()

    def restore_latest_server(self, profile: RemoteProfile) -> bool:
        remote_path = profile.resolved_server_description_path()
        if not remote_path:
            return False

        source_uri = remote_source_uri(profile.protocol, profile.profile_id, remote_path)
        latest = self.backup.latest_backup(category="remote_server_config", source_path=source_uri)
        if not latest:
            log.warning("No remote server config backups available for %s", source_uri)
            return False
        return self.restore_backup_record(latest)

    def load_world_by_island_id(
        self,
        profile: RemoteProfile,
        island_id: str,
    ) -> tuple[Optional[WorldConfig], Optional[str]]:
        if not island_id:
            return None, None

        provider = None
        try:
            provider = self.provider_factory(profile)
            world_paths = self._discover_worlds(provider, profile)
            for remote_path in world_paths:
                try:
                    data = json.loads(provider.read_bytes(remote_path).decode("utf-8"))
                except Exception:
                    continue
                config = WorldConfig.from_json_dict(data, file_path=remote_path)
                if config.island_id.upper() == island_id.upper():
                    log.info("Loaded remote world config %s for island %s", remote_path, island_id)
                    return config, remote_path
            return None, None
        except Exception as exc:
            log.error("Failed to discover remote worlds for %s: %s", profile.name, exc)
            return None, None
        finally:
            if provider is not None:
                provider.close()

    def save_world(
        self,
        profile: RemoteProfile,
        remote_path: str,
        config: WorldConfig,
    ) -> tuple[bool, list[str]]:
        if not remote_path:
            return False, ["Remote WorldDescription.json path is not set."]

        errors = config.validate()
        if errors:
            return False, errors

        provider = None
        try:
            provider = self.provider_factory(profile)
            self._backup_remote_file(
                provider,
                profile,
                remote_path,
                category="remote_world_config",
                description=f"Pre-save backup of remote WorldDescription.json ({config.world_name})",
            )
            payload = json.dumps(config.to_json_dict(), indent=2, ensure_ascii=False).encode("utf-8")
            provider.upload_bytes(payload, remote_path)
            log.info("Saved remote world config to %s", remote_path)
            return True, []
        except Exception as exc:
            log.error("Failed to save remote world config: %s", exc)
            return False, [str(exc)]
        finally:
            if provider is not None:
                provider.close()

    def restore_latest_world(self, profile: RemoteProfile, remote_path: str) -> bool:
        if not remote_path:
            return False

        source_uri = remote_source_uri(profile.protocol, profile.profile_id, remote_path)
        latest = self.backup.latest_backup(category="remote_world_config", source_path=source_uri)
        if not latest:
            log.warning("No remote world config backups available for %s", source_uri)
            return False
        return self.restore_backup_record(latest)

    def restore_backup_record(self, record: BackupRecord) -> bool:
        try:
            _protocol, profile_id, remote_path = parse_remote_source_uri(record.source_path)
        except ValueError:
            return False

        profile = self.profile_store.get_profile(profile_id)
        if profile is None:
            log.warning("Remote profile %s no longer exists for restore", profile_id)
            return False

        provider = None
        try:
            provider = self.provider_factory(profile)
            backup_bytes = Path(record.backup_path).read_bytes()
            provider.upload_bytes(backup_bytes, remote_path)
            log.info("Restored remote backup %s -> %s", record.backup_path, remote_path)
            return True
        except Exception as exc:
            log.error("Failed to restore remote backup %s: %s", record.backup_path, exc)
            return False
        finally:
            if provider is not None:
                provider.close()

    def _backup_remote_file(
        self,
        provider: RemoteProvider,
        profile: RemoteProfile,
        remote_path: str,
        *,
        category: str,
        description: str,
    ) -> None:
        try:
            data = provider.read_bytes(remote_path)
        except Exception as exc:
            log.warning("Could not back up remote file %s before save: %s", remote_path, exc)
            return

        source_uri = remote_source_uri(profile.protocol, profile.profile_id, remote_path)
        self.backup.backup_bytes(
            source_path=source_uri,
            filename=PurePosixPath(remote_path).name or "remote_config.json",
            data=data,
            category=category,
            description=description,
        )

    def _discover_worlds(self, provider: RemoteProvider, profile: RemoteProfile) -> list[str]:
        save_root = profile.resolved_save_root()
        if not save_root:
            return []

        worlds: list[str] = []
        root_path = PurePosixPath(save_root)
        if root_path.name.lower() == "saveprofiles":
            profiles_dir = str(root_path)
        else:
            profiles_dir = self._join_remote(save_root, "SaveProfiles")
        for profile_entry in self._safe_list_dirs(provider, profiles_dir):
            rocksdb_dir = self._join_remote(profile_entry.path, "RocksDB")
            for version_dir in self._safe_list_dirs(provider, rocksdb_dir):
                worlds_dir = self._join_remote(version_dir.path, "Worlds")
                for world_dir in self._safe_list_dirs(provider, worlds_dir):
                    world_desc = self._join_remote(world_dir.path, "WorldDescription.json")
                    try:
                        provider.read_bytes(world_desc)
                        worlds.append(world_desc)
                    except Exception:
                        continue
        return worlds

    @staticmethod
    def _safe_list_dirs(provider: RemoteProvider, remote_dir: str):
        try:
            return [entry for entry in provider.list_entries(remote_dir) if entry.is_dir]
        except Exception:
            return []

    @staticmethod
    def _join_remote(root: str, child: str) -> str:
        return str(PurePosixPath(root).joinpath(child))
