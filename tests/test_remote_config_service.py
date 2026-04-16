"""Tests for remote config load/save/restore flows."""
import json

from windrose_deployer.core.backup_manager import BackupManager
from windrose_deployer.core.remote_config_service import RemoteConfigService
from windrose_deployer.core.remote_profile_store import RemoteProfileStore
from windrose_deployer.models.remote_profile import RemoteProfile
from windrose_deployer.models.server_config import ServerConfig
from windrose_deployer.models.world_config import WorldConfig


class FakeRemoteProvider:
    def __init__(self, files: dict[str, bytes]):
        self.files = files

    def close(self) -> None:
        return None

    def path_exists(self, remote_path: str) -> bool:
        if remote_path in self.files:
            return True
        prefix = remote_path.rstrip("/") + "/"
        return any(path.startswith(prefix) for path in self.files)

    def list_files(self, remote_dir: str) -> list[str]:
        return sorted([path for path in self.files if path.startswith(remote_dir)])

    def list_entries(self, remote_dir: str):
        prefix = remote_dir.rstrip("/") + "/"
        children: dict[str, bool] = {}
        for path in self.files:
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix):]
            first = remainder.split("/", 1)[0]
            is_dir = "/" in remainder
            children[first] = children.get(first, False) or is_dir
        return [
            type("RemoteEntry", (), {
                "path": prefix.rstrip("/") + "/" + name,
                "name": name,
                "is_dir": is_dir,
            })()
            for name, is_dir in sorted(children.items())
        ]

    def ensure_dir(self, remote_dir: str) -> None:
        return None

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        self.files[remote_path] = data

    def read_bytes(self, remote_path: str) -> bytes:
        return self.files[remote_path]

    def execute(self, command: str) -> tuple[bool, str]:
        return True, command


def _make_service(tmp_path, files):
    backup = BackupManager(tmp_path / "backups")
    store = RemoteProfileStore(tmp_path / "data")
    profile = RemoteProfile.new("Remote")
    profile.host = "example.com"
    profile.username = "user"
    profile.remote_server_description_path = "/game/R5/ServerDescription.json"
    profile.remote_save_root = "/saves"
    store.upsert(profile)
    service = RemoteConfigService(
        backup,
        store,
        provider_factory=lambda _profile: FakeRemoteProvider(files),
    )
    return service, store, profile, backup


def test_remote_server_save_and_restore(tmp_path):
    server_payload = {
        "Version": 1,
        "DeploymentId": "dep",
        "ServerDescription_Persistent": {
            "PersistentServerId": "ps",
            "InviteCode": "ABCDEF",
            "IsPasswordProtected": False,
            "Password": "",
            "ServerName": "Initial",
            "WorldIslandId": "WORLD1",
            "MaxPlayerCount": 8,
            "P2pProxyAddress": "127.0.0.1",
        },
    }
    files = {
        "/game/R5/ServerDescription.json": json.dumps(server_payload).encode("utf-8"),
    }
    service, _store, profile, backup = _make_service(tmp_path, files)

    config = service.load_server(profile)
    assert config is not None
    config.server_name = "Updated"

    success, errors = service.save_server(profile, config)
    assert success
    assert errors == []
    assert len(backup.list_backups("remote_server_config")) == 1

    broken_payload = dict(server_payload)
    broken_persistent = dict(server_payload["ServerDescription_Persistent"])
    broken_persistent["ServerName"] = "Broken"
    broken_payload["ServerDescription_Persistent"] = broken_persistent
    files["/game/R5/ServerDescription.json"] = json.dumps(broken_payload).encode("utf-8")
    assert service.restore_latest_server(profile)
    restored = json.loads(files["/game/R5/ServerDescription.json"].decode("utf-8"))
    assert restored["ServerDescription_Persistent"]["ServerName"] == "Initial"


def test_remote_world_discovery_by_island_id(tmp_path):
    world_payload = WorldConfig(
        island_id="WORLD-123",
        world_name="Remote World",
        world_preset_type="Medium",
    ).to_json_dict()
    files = {
        "/saves/SaveProfiles/profileA/RocksDB/v1/Worlds/worldA/WorldDescription.json":
            json.dumps(world_payload).encode("utf-8"),
    }
    service, _store, profile, _backup = _make_service(tmp_path, files)

    config, remote_path = service.load_world_by_island_id(profile, "WORLD-123")

    assert config is not None
    assert config.world_name == "Remote World"
    assert remote_path.endswith("WorldDescription.json")


def test_remote_config_uses_root_defaults_when_overrides_blank(tmp_path):
    server_payload = {
        "Version": 1,
        "DeploymentId": "dep",
        "ServerDescription_Persistent": {
            "PersistentServerId": "ps",
            "InviteCode": "ABCDEF",
            "IsPasswordProtected": False,
            "Password": "",
            "ServerName": "Initial",
            "WorldIslandId": "WORLD1",
            "MaxPlayerCount": 8,
            "P2pProxyAddress": "127.0.0.1",
        },
    }
    world_payload = WorldConfig(
        island_id="WORLD-123",
        world_name="Remote World",
        world_preset_type="Medium",
    ).to_json_dict()
    files = {
        "/game-root/R5/ServerDescription.json": json.dumps(server_payload).encode("utf-8"),
        "/game-root/R5/Saved/SaveProfiles/profileA/RocksDB/v1/Worlds/worldA/WorldDescription.json":
            json.dumps(world_payload).encode("utf-8"),
    }
    service, _store, profile, _backup = _make_service(tmp_path, files)
    profile.remote_server_description_path = ""
    profile.remote_save_root = ""
    profile.remote_root_dir = "/game-root"

    config = service.load_server(profile)
    world_config, remote_path = service.load_world_by_island_id(profile, "WORLD-123")

    assert config is not None
    assert config.server_name == "Initial"
    assert world_config is not None
    assert remote_path == "/game-root/R5/Saved/SaveProfiles/profileA/RocksDB/v1/Worlds/worldA/WorldDescription.json"


def test_remote_load_server_returns_none_when_provider_creation_fails(tmp_path):
    backup = BackupManager(tmp_path / "backups")
    store = RemoteProfileStore(tmp_path / "data")
    profile = RemoteProfile.new("Remote")
    profile.host = "localhost"
    profile.username = "jonte"
    profile.remote_server_description_path = "/game/R5/ServerDescription.json"
    store.upsert(profile)

    service = RemoteConfigService(
        backup,
        store,
        provider_factory=lambda _profile: (_ for _ in ()).throw(ValueError("bad key path")),
    )

    assert service.load_server(profile) is None
