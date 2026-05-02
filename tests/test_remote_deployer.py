"""Tests for remote planning and deployment flows."""
from pathlib import Path
import zipfile

from windrose_deployer.core.archive_inspector import inspect_archive
from windrose_deployer.core.remote_deployer import (
    RemoteDeploymentService,
    plan_remote_deployment,
    remote_connection_diagnostics,
)
from windrose_deployer.models.remote_profile import RemoteProfile


class FakeRemoteProvider:
    def __init__(self, uploads: list[str], existing_paths: set[str] | None = None):
        self.uploads = uploads
        self.closed = False
        self.existing_paths = existing_paths or set(uploads)

    def close(self) -> None:
        self.closed = True

    def path_exists(self, remote_path: str) -> bool:
        return remote_path in self.existing_paths

    def list_files(self, remote_dir: str) -> list[str]:
        if remote_dir not in self.existing_paths:
            raise FileNotFoundError(remote_dir)
        return sorted([path for path in self.uploads if path.startswith(remote_dir)])

    def list_entries(self, remote_dir: str):
        return []

    def ensure_dir(self, remote_dir: str) -> None:
        return None

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        self.uploads.append(remote_path)
        self.existing_paths.add(remote_path)

    def read_bytes(self, remote_path: str) -> bytes:
        return b""

    def execute(self, command: str) -> tuple[bool, str]:
        return True, f"ran {command}"


def _make_profile() -> RemoteProfile:
    return RemoteProfile(
        profile_id="remote1",
        name="Remote",
        host="example.com",
        username="user",
        remote_root_dir="/srv/windrose",
        remote_mods_dir="/srv/windrose/R5/Content/Paks/~mods",
    )


def test_remote_plan_requires_root_for_loose_files(tmp_path: Path) -> None:
    archive = tmp_path / "mixed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("R5/Content/Paks/~mods/test.pak", "pak")
        zf.writestr("Config/extra.ini", "value=1")

    info = inspect_archive(archive)
    profile = _make_profile()
    profile.remote_root_dir = ""

    plan = plan_remote_deployment(info, profile, mod_name="MixedMod")

    assert not plan.valid
    assert any("configure server folder" in warning.lower() for warning in plan.warnings)


def test_remote_plan_uses_root_defaults_when_overrides_blank(tmp_path: Path) -> None:
    archive = tmp_path / "pak.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("SomeMod.pak", "pak")

    info = inspect_archive(archive)
    profile = _make_profile()
    profile.remote_mods_dir = ""

    plan = plan_remote_deployment(info, profile, mod_name="PakOnly")

    assert plan.valid
    assert plan.files[0].remote_path == "/srv/windrose/R5/Content/Paks/~mods/SomeMod.pak"


def test_remote_plan_routes_ue4ss_mod_to_remote_mods_tree(tmp_path: Path) -> None:
    archive = tmp_path / "toggle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ToggleSprint/enabled.txt", "1")
        zf.writestr("ToggleSprint/Scripts/main.lua", "print('x')")

    info = inspect_archive(archive)
    profile = _make_profile()
    plan = plan_remote_deployment(info, profile, mod_name="ToggleSprint")

    assert plan.valid
    assert plan.install_kind == "ue4ss_mod"
    assert sorted(item.remote_path for item in plan.files) == [
        "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/ToggleSprint/Scripts/main.lua",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/ToggleSprint/enabled.txt",
    ]


def test_remote_plan_routes_ue4ss_runtime_to_remote_win64(tmp_path: Path) -> None:
    archive = tmp_path / "ue4ss.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("UE4SS/dwmapi.dll", "dll")
        zf.writestr("UE4SS/ue4ss/UE4SS.dll", "dll")
        zf.writestr("UE4SS/readme.txt", "skip")

    info = inspect_archive(archive)
    profile = _make_profile()
    plan = plan_remote_deployment(info, profile, mod_name="UE4SS")

    assert plan.valid
    assert sorted(item.remote_path for item in plan.files) == [
        "/srv/windrose/R5/Binaries/Win64/dwmapi.dll",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/UE4SS.dll",
    ]


def test_remote_deploy_uploads_only_selected_variant(tmp_path: Path) -> None:
    archive = tmp_path / "variants.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Stack_Size_Changes_x10_P.pak", "ten")
        zf.writestr("Stack_Size_Changes_x20_P.pak", "twenty")
        zf.writestr("SharedSupport.utoc", "support")

    info = inspect_archive(archive)
    profile = _make_profile()
    plan = plan_remote_deployment(
        info,
        profile,
        selected_variant="Stack_Size_Changes_x10_P.pak",
        mod_name="VariantMod",
    )

    uploads: list[str] = []
    service = RemoteDeploymentService(provider_factory=lambda _profile: FakeRemoteProvider(uploads))
    result = service.deploy(plan, profile)

    assert result.failed == []
    assert "/srv/windrose/R5/Content/Paks/~mods/Stack_Size_Changes_x10_P.pak" in uploads
    assert "/srv/windrose/R5/Content/Paks/~mods/Stack_Size_Changes_x20_P.pak" not in uploads


def test_remote_deploy_skips_unsafe_archive_paths(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("good_mod.pak", "safe")
        zf.writestr("../escaped.pak", "unsafe")

    info = inspect_archive(archive)
    profile = _make_profile()
    plan = plan_remote_deployment(info, profile, mod_name="UnsafeMod")

    uploads: list[str] = []
    service = RemoteDeploymentService(provider_factory=lambda _profile: FakeRemoteProvider(uploads))
    result = service.deploy(plan, profile)

    assert any("unsafe path" in entry for entry in result.skipped)
    assert uploads == ["/srv/windrose/R5/Content/Paks/~mods/good_mod.pak"]
    assert "1 uploaded" in result.summary
    assert "1 skipped" in result.summary


def test_test_connection_validates_resolved_paths_from_root() -> None:
    uploads: list[str] = []
    existing_paths = {
        "/srv/windrose",
        "/srv/windrose/R5/Content/Paks/~mods",
        "/srv/windrose/R5/ServerDescription.json",
        "/srv/windrose/R5/Saved",
    }
    profile = _make_profile()
    profile.remote_mods_dir = ""
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: FakeRemoteProvider(uploads, existing_paths)
    )

    ok, message = service.test_connection(profile)

    assert ok
    assert "root OK" in message
    assert "mods dir OK" in message
    assert "server config OK" in message
    assert "save root OK" in message


def test_test_connection_allows_missing_mods_dir_until_first_upload() -> None:
    uploads: list[str] = []
    existing_paths = {
        "/srv/windrose",
        "/srv/windrose/R5/ServerDescription.json",
        "/srv/windrose/R5/Saved",
    }
    profile = _make_profile()
    profile.remote_mods_dir = ""
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: FakeRemoteProvider(uploads, existing_paths)
    )

    ok, message = service.test_connection(profile)

    assert ok
    assert "mods dir missing" in message
    assert "will be created on first install" in message


def test_test_connection_rejects_missing_explicit_mods_override() -> None:
    uploads: list[str] = []
    existing_paths = {
        "/srv/windrose",
        "/srv/windrose/R5/ServerDescription.json",
        "/srv/windrose/R5/Saved",
    }
    profile = _make_profile()
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: FakeRemoteProvider(uploads, existing_paths)
    )

    ok, message = service.test_connection(profile)

    assert not ok
    assert "mods folder was not found" in message
    assert "/srv/windrose/R5/Content/Paks/~mods" in message
    assert "Server Folder to '.'" in message


def test_list_remote_files_returns_empty_when_mods_dir_is_missing() -> None:
    uploads: list[str] = []
    existing_paths = {
        "/srv/windrose",
        "/srv/windrose/R5/ServerDescription.json",
        "/srv/windrose/R5/Saved",
    }
    profile = _make_profile()
    profile.remote_mods_dir = ""
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: FakeRemoteProvider(uploads, existing_paths)
    )

    files = service.list_remote_files(profile)

    assert files == []


def test_list_remote_files_raises_when_explicit_mods_override_is_missing() -> None:
    uploads: list[str] = []
    existing_paths = {
        "/srv/windrose",
        "/srv/windrose/R5/ServerDescription.json",
        "/srv/windrose/R5/Saved",
    }
    profile = _make_profile()
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: FakeRemoteProvider(uploads, existing_paths)
    )

    try:
        service.list_remote_files(profile)
    except FileNotFoundError as exc:
        assert "/srv/windrose/R5/Content/Paks/~mods" in str(exc)
        assert "Server Folder to '.'" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing explicit mods dir override")


def test_test_connection_ftp_missing_mods_override_explains_ftp_root_paths() -> None:
    uploads: list[str] = []
    existing_paths = {
        "/srv/windrose",
        "/srv/windrose/R5/ServerDescription.json",
        "/srv/windrose/R5/Saved",
    }
    profile = _make_profile()
    profile.protocol = "ftp"
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: FakeRemoteProvider(uploads, existing_paths)
    )

    ok, message = service.test_connection(profile)

    assert not ok
    assert "FTP hosts such as Nitrado" in message
    assert "relative to the FTP login root" in message
    assert "R5/Content/Paks/~mods" in message


def test_test_connection_guides_blank_root_and_manual_overrides() -> None:
    uploads: list[str] = []
    profile = _make_profile()
    profile.remote_root_dir = ""
    profile.remote_mods_dir = ""
    profile.remote_server_description_path = ""
    profile.remote_save_root = ""
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: FakeRemoteProvider(uploads, set())
    )

    ok, message = service.test_connection(profile)

    assert ok
    assert "server folder" in message.lower()
    assert "overrides manually" in message.lower()


def test_restart_remote_is_honest_for_ftp_profiles() -> None:
    profile = _make_profile()
    profile.protocol = "ftp"
    profile.restart_command = "restart-now"
    service = RemoteDeploymentService(provider_factory=lambda _profile: FakeRemoteProvider([]))

    ok, message = service.restart_remote(profile)

    assert not ok
    assert "ftp supports file access only" in message.lower()


def test_test_connection_reports_protocol_mismatch_for_sftp_banner_errors() -> None:
    profile = _make_profile()
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: (_ for _ in ()).throw(RuntimeError("Error reading SSH protocol banner")),
    )

    ok, message = service.test_connection(profile)

    assert not ok
    assert "selected protocol is sftp" in message.lower()
    assert "likely does not match the host" in message.lower()


def test_test_connection_reports_network_reachability_for_ftp_timeouts() -> None:
    profile = _make_profile()
    profile.protocol = "ftp"
    profile.port = 21
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: (_ for _ in ()).throw(TimeoutError("timed out while waiting for welcome banner")),
    )

    ok, message = service.test_connection(profile)

    assert not ok
    assert "ftp service could not be reached from this pc" in message.lower()
    assert "winscp/filezilla" in message.lower()
    assert "Tried FTP example.com:21 as user." in message


def test_test_connection_reports_hostname_resolution_failures() -> None:
    profile = _make_profile()
    profile.protocol = "ftp"
    profile.host = "ms2048.gamedata.io"
    profile.port = 21
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: (_ for _ in ()).throw(OSError("[Errno 11001] getaddrinfo failed")),
    )

    ok, message = service.test_connection(profile)

    assert not ok
    assert "hostname could not be resolved" in message.lower()
    assert "typos" in message.lower()
    assert "Tried FTP ms2048.gamedata.io:21 as user." in message


def test_test_connection_reports_ftp_login_rejected() -> None:
    profile = _make_profile()
    profile.protocol = "ftp"
    profile.port = 21
    service = RemoteDeploymentService(
        provider_factory=lambda _profile: (_ for _ in ()).throw(RuntimeError("530 Login incorrect.")),
    )

    ok, message = service.test_connection(profile)

    assert not ok
    assert "ftp username or password was rejected" in message.lower()
    assert "Tried FTP example.com:21 as user." in message


def test_remote_connection_diagnostics_redacts_secrets() -> None:
    profile = _make_profile()
    profile.protocol = "ftp"
    profile.port = 21
    profile.password = "super-secret"
    profile.private_key_path = "C:/Users/me/.ssh/id_rsa"
    profile.remote_mods_dir = "R5/Content/Paks/~mods"
    profile.remote_server_description_path = "R5/ServerDescription.json"
    profile.remote_save_root = "R5/Saved"

    diagnostics = remote_connection_diagnostics(profile)

    assert "Tried FTP example.com:21 as user." in diagnostics
    assert "super-secret" not in diagnostics
    assert "id_rsa" not in diagnostics
    assert "R5/Content/Paks/~mods" in diagnostics


def test_test_connection_uses_trimmed_profile_fields() -> None:
    seen = {}

    def _factory(profile):
        seen["profile"] = profile
        return FakeRemoteProvider([], set())

    profile = _make_profile()
    profile.protocol = "ftp"
    profile.host = "  example.com  "
    profile.port = "21"
    profile.username = "  user  "
    profile.remote_root_dir = " . "
    service = RemoteDeploymentService(provider_factory=_factory)

    service.test_connection(profile)

    normalized = seen["profile"]
    assert normalized.host == "example.com"
    assert normalized.port == 21
    assert normalized.username == "user"
    assert normalized.remote_root_dir == "."
