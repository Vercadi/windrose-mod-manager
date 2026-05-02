from pathlib import Path

from windrose_deployer.core.remote_profile_store import RemoteProfileStore
from windrose_deployer.core import remote_provider_factory
from windrose_deployer.models.remote_profile import (
    RemoteProfile,
    default_port_for_protocol,
    normalize_remote_endpoint,
)


def test_remote_profile_store_loads_legacy_profiles_as_sftp(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "compat" / "remote_profiles.current.sftp.json"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "remote_profiles.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    store = RemoteProfileStore(data_dir)
    profiles = store.list_profiles()

    assert len(profiles) == 2
    assert all(profile.protocol == "sftp" for profile in profiles)
    assert profiles[0].port == 22


def test_remote_profile_store_loads_current_ftp_profiles(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "compat" / "remote_profiles.current.ftp.json"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "remote_profiles.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    store = RemoteProfileStore(data_dir)
    profiles = store.list_profiles()

    assert len(profiles) == 1
    assert profiles[0].protocol == "ftp"
    assert profiles[0].port == 21
    assert profiles[0].auth_mode == "password"
    assert profiles[0].restart_command == ""


def test_normalize_remote_endpoint_preserves_explicit_ports_and_supports_host_forms():
    assert normalize_remote_endpoint("example.com", "", protocol="ftp") == ("example.com", 21, "ftp")
    assert normalize_remote_endpoint("example.com:2121", "", protocol="ftp") == ("example.com", 2121, "ftp")
    assert normalize_remote_endpoint("sftp://panel.host:8022", "", protocol="ftp") == ("panel.host", 8022, "sftp")
    assert default_port_for_protocol("sftp") == 22
    assert default_port_for_protocol("ftp") == 21


def test_remote_profile_normalized_for_connection_trims_fields_and_keeps_explicit_port():
    profile = RemoteProfile(
        profile_id="p1",
        name="  Nitrado  ",
        protocol="ftp",
        host="  ms2084.gamedata.io:2121  ",
        port="21",
        username="  user123  ",
        auth_mode="key",
        private_key_path=" C:/Users/test/.ssh/id_rsa ",
        remote_root_dir=" . ",
        remote_mods_dir=" R5\\Content\\Paks\\~mods ",
        remote_server_description_path=" R5\\ServerDescription.json ",
        remote_save_root=" R5\\Saved ",
        restart_command=" restart ",
    )

    normalized = profile.normalized_for_connection()

    assert normalized.name == "Nitrado"
    assert normalized.protocol == "ftp"
    assert normalized.host == "ms2084.gamedata.io"
    assert normalized.port == 2121
    assert normalized.username == "user123"
    assert normalized.auth_mode == "password"
    assert normalized.private_key_path == ""
    assert normalized.remote_root_dir == "."
    assert normalized.remote_mods_dir == "R5/Content/Paks/~mods"
    assert normalized.restart_command == ""


def test_remote_provider_factory_routes_by_protocol(monkeypatch):
    calls: list[str] = []

    class FakeFtpProvider:
        def __init__(self, _profile):
            calls.append("ftp")

    class FakeSftpProvider:
        def __init__(self, _profile):
            calls.append("sftp")

    monkeypatch.setattr(remote_provider_factory, "FtpProvider", FakeFtpProvider)
    monkeypatch.setattr(remote_provider_factory, "SftpProvider", FakeSftpProvider)

    ftp_profile = RemoteProfile.new("FTP")
    ftp_profile.protocol = "ftp"
    sftp_profile = RemoteProfile.new("SFTP")
    sftp_profile.protocol = "sftp"

    remote_provider_factory.create_remote_provider(ftp_profile)
    remote_provider_factory.create_remote_provider(sftp_profile)

    assert calls == ["ftp", "sftp"]
