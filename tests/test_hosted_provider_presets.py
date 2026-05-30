from pathlib import Path
import zipfile

from windrose_deployer.core.archive_inspector import inspect_archive
from windrose_deployer.core.hosted_provider_presets import (
    NITRADO_FTP_PRESET,
    apply_hosted_provider_preset,
)
from windrose_deployer.core.remote_deployer import plan_remote_deployment
from windrose_deployer.models.remote_profile import RemoteProfile


def test_nitrado_preset_applies_conservative_ftp_paths() -> None:
    profile = RemoteProfile(
        profile_id="n1",
        name="Nitrado",
        protocol="sftp",
        port=22,
        remote_root_dir="",
        remote_mods_dir="",
        restart_command="restart",
    )

    updated = apply_hosted_provider_preset(profile, NITRADO_FTP_PRESET)

    assert updated.protocol == "ftp"
    assert updated.port == 21
    assert updated.remote_root_dir == "windrose"
    assert updated.remote_mods_dir == "windrose/Mods"
    assert updated.resolved_server_description_path() == "windrose/R5/ServerDescription.json"
    assert updated.resolved_save_root() == "windrose/R5/Saved"
    assert updated.restart_command == ""


def test_generic_remote_profile_derived_mods_path_is_unchanged() -> None:
    profile = RemoteProfile(profile_id="g1", name="Generic", remote_root_dir="windrose")

    assert profile.resolved_mods_dir() == "windrose/R5/Content/Paks/~mods"


def test_remote_plan_uses_nitrado_mods_override(tmp_path: Path) -> None:
    archive = tmp_path / "mod.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("TestMod_P.pak", "pak")
        zf.writestr("TestMod_P.ucas", "ucas")
        zf.writestr("TestMod_P.utoc", "utoc")

    info = inspect_archive(archive)
    profile = apply_hosted_provider_preset(
        RemoteProfile(profile_id="n1", name="Nitrado"),
        NITRADO_FTP_PRESET,
    )

    plan = plan_remote_deployment(info, profile, mod_name="TestMod")

    assert plan.valid
    assert sorted(item.remote_path for item in plan.files) == [
        "windrose/Mods/TestMod_P.pak",
        "windrose/Mods/TestMod_P.ucas",
        "windrose/Mods/TestMod_P.utoc",
    ]


def test_nitrado_preset_status_keeps_override_editable_guidance() -> None:
    assert "clear Mods Folder Override" in NITRADO_FTP_PRESET.status
    assert "R5/Content/Paks/~mods" in NITRADO_FTP_PRESET.status
