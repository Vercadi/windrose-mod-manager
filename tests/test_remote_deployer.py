"""Tests for remote planning and deployment flows."""
from pathlib import Path
import zipfile

from windrose_deployer.core.archive_inspector import inspect_archive
from windrose_deployer.core.remote_deployer import (
    RemoteDeploymentService,
    plan_remote_deployment,
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
