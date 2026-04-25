from windrose_deployer.core.rcon_config_service import RconConfigService, RconSettings, parse_rcon_settings
from windrose_deployer.models.remote_profile import RemoteProfile


class FakeProvider:
    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.closed = False
        self.uploads: dict[str, bytes] = {}

    def close(self):
        self.closed = True

    def path_exists(self, remote_path: str) -> bool:
        return remote_path in self.files

    def read_bytes(self, remote_path: str) -> bytes:
        if remote_path not in self.files:
            raise FileNotFoundError(remote_path)
        return self.files[remote_path]

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        self.uploads[remote_path] = data
        self.files[remote_path] = data


def test_parse_rcon_settings_reads_simple_key_value_file():
    settings = parse_rcon_settings(
        "# WindroseRCON Configuration\n"
        "Enabled=false\n"
        "Port=27065\n"
        "\n"
        "Password=secret\n",
        source_path="settings.ini",
    )

    assert settings.enabled is False
    assert settings.port == 27065
    assert settings.password == "secret"
    assert settings.source_path == "settings.ini"


def test_rcon_settings_serializes_simple_key_value_file():
    text = RconSettings(port=1234, password="pw").to_text()

    assert "Enabled=true" in text
    assert "Port=1234" in text
    assert "Password=pw" in text


def test_local_settings_path_uses_generated_rcon_location(tmp_path):
    path = RconConfigService.local_settings_path(tmp_path)

    assert path is not None
    assert path.relative_to(tmp_path).as_posix() == "R5/Binaries/Win64/windrosercon/settings.ini"


def test_local_settings_path_uses_legacy_location_when_only_legacy_exists(tmp_path):
    legacy = tmp_path / "R5" / "Binaries" / "Win64" / "ue4ss" / "Mods" / "WindroseRCON" / "settings.ini"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("Port=27065\nPassword=legacy\n", encoding="utf-8")

    path = RconConfigService.local_settings_path(tmp_path)

    assert path == legacy


def test_remote_load_uses_generated_rcon_settings_first():
    profile = RemoteProfile(profile_id="p1", name="Hosted", remote_root_dir="/srv/windrose")
    provider = FakeProvider({
        "/srv/windrose/R5/Binaries/Win64/windrosercon/settings.ini": b"Port=27065\nPassword=primary\n",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/WindroseRCON/settings.ini": b"Port=27065\nPassword=legacy\n",
    })
    service = RconConfigService(backup_manager=None, provider_factory=lambda _profile: provider)

    settings = service.load_remote(profile)

    assert settings is not None
    assert settings.password == "primary"
    assert settings.source_path == "/srv/windrose/R5/Binaries/Win64/windrosercon/settings.ini"
    assert provider.closed is True


def test_remote_save_preserves_legacy_path_when_only_legacy_exists(tmp_path):
    profile = RemoteProfile(profile_id="p1", name="Hosted", remote_root_dir="/srv/windrose")
    legacy = "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/WindroseRCON/settings.ini"
    provider = FakeProvider({legacy: b"Port=27065\nPassword=old\n"})
    service = RconConfigService(backup_manager=_NoopBackup(), provider_factory=lambda _profile: provider)

    assert service.save_remote(profile, RconSettings(port=1234, password="new")) is True

    assert legacy in provider.uploads
    assert b"Password=new" in provider.uploads[legacy]


class _NoopBackup:
    def backup_bytes(self, **_kwargs):
        return None
