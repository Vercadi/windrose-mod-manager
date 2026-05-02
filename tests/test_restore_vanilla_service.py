from pathlib import Path

import pytest

from windrose_deployer.core.backup_manager import BackupManager
from windrose_deployer.core.installer import Installer
from windrose_deployer.core.manifest_store import ManifestStore
from windrose_deployer.core.restore_vanilla_service import RestoreVanillaService
from windrose_deployer.models.app_paths import AppPaths
from windrose_deployer.models.mod_install import ModInstall
from windrose_deployer.utils.naming import generate_mod_id


def _root(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    (root / "R5" / "Content" / "Paks" / "~mods").mkdir(parents=True)
    return root


def _service(tmp_path: Path, paths: AppPaths) -> tuple[RestoreVanillaService, ManifestStore, BackupManager]:
    manifest = ManifestStore(tmp_path / "data")
    backup = BackupManager(tmp_path / "backups")
    return RestoreVanillaService(paths, manifest, Installer(backup), backup), manifest, backup


def test_restore_vanilla_rejects_hosted_target(tmp_path):
    service, _manifest, _backup = _service(tmp_path, AppPaths())

    with pytest.raises(ValueError, match="Hosted"):
        service.build_plan("hosted")


def test_restore_vanilla_plan_includes_only_selected_single_target_managed_mods(tmp_path):
    client_root = _root(tmp_path, "Client")
    server_root = _root(tmp_path, "Server")
    service, manifest, _backup = _service(
        tmp_path,
        AppPaths(client_root=client_root, server_root=server_root),
    )
    client_mod_path = client_root / "R5" / "Content" / "Paks" / "~mods" / "Client_P.pak"
    server_mod_path = server_root / "R5" / "Content" / "Paks" / "~mods" / "Server_P.pak"
    manifest.add_mod(
        ModInstall(
            mod_id=generate_mod_id(),
            display_name="Client Only",
            source_archive="client.zip",
            targets=["client"],
            installed_files=[str(client_mod_path)],
        )
    )
    manifest.add_mod(
        ModInstall(
            mod_id=generate_mod_id(),
            display_name="Server Only",
            source_archive="server.zip",
            targets=["server"],
            installed_files=[str(server_mod_path)],
        )
    )

    plan = service.build_plan("client")

    assert [item.label for item in plan.managed_mods] == ["Client Only"]
    assert [item.label for item in plan.managed_review] == []


def test_restore_vanilla_plan_leaves_multi_target_managed_mods_for_review(tmp_path):
    client_root = _root(tmp_path, "Client")
    server_root = _root(tmp_path, "Server")
    service, manifest, _backup = _service(
        tmp_path,
        AppPaths(client_root=client_root, server_root=server_root),
    )
    manifest.add_mod(
        ModInstall(
            mod_id=generate_mod_id(),
            display_name="Old Combined",
            source_archive="combined.zip",
            targets=["both"],
            installed_files=[
                str(client_root / "R5" / "Content" / "Paks" / "~mods" / "Combined_P.pak"),
                str(server_root / "R5" / "Content" / "Paks" / "~mods" / "Combined_P.pak"),
            ],
        )
    )

    plan = service.build_plan("client")

    assert plan.managed_mods == ()
    assert [item.label for item in plan.managed_review] == ["Old Combined"]


def test_restore_vanilla_groups_unmanaged_ue_companion_files(tmp_path):
    client_root = _root(tmp_path, "Client")
    mods_dir = client_root / "R5" / "Content" / "Paks" / "~mods"
    for name in ("Manual_P.pak", "Manual_P.utoc", "Manual_P.ucas", "Solo_P.pak"):
        (mods_dir / name).write_bytes(b"x")
    service, _manifest, _backup = _service(tmp_path, AppPaths(client_root=client_root))

    plan = service.build_plan("client")

    assert [(item.label, len(item.paths)) for item in plan.unmanaged_files] == [
        ("Manual_P", 3),
        ("Solo_P", 1),
    ]


def test_restore_vanilla_detects_known_framework_files(tmp_path):
    server_root = _root(tmp_path, "Dedicated")
    win64 = server_root / "R5" / "Binaries" / "Win64"
    (win64 / "ue4ss" / "Mods" / "WindroseRCON").mkdir(parents=True)
    (win64 / "dwmapi.dll").write_bytes(b"dll")
    (win64 / "version.dll").write_bytes(b"dll")
    (server_root / "windrose_plus").mkdir()
    (server_root / "StartWindrosePlusServer.bat").write_text("@echo off\n", encoding="utf-8")
    service, _manifest, _backup = _service(tmp_path, AppPaths(dedicated_server_root=server_root))

    plan = service.build_plan("dedicated_server")

    assert [item.label for item in plan.framework_files] == [
        "UE4SS runtime/files",
        "WindroseRCON files",
        "WindrosePlus files",
    ]


def test_restore_vanilla_backs_up_unmanaged_files_before_deletion(tmp_path):
    client_root = _root(tmp_path, "Client")
    mods_dir = client_root / "R5" / "Content" / "Paks" / "~mods"
    target_file = mods_dir / "Manual_P.pak"
    target_file.write_bytes(b"manual")
    service, _manifest, backup = _service(tmp_path, AppPaths(client_root=client_root))
    plan = service.build_plan("client")

    result = service.execute_plan(
        plan,
        include_managed=False,
        include_unmanaged=True,
        include_frameworks=False,
    )

    assert result.errors == ()
    assert result.removed_unmanaged == 1
    assert not target_file.exists()
    records = backup.list_backups(category="restore_vanilla")
    assert len(records) == 1
    assert Path(records[0].backup_path).parent.name == "restore_vanilla"
    assert Path(records[0].backup_path).read_bytes() == b"manual"


def test_restore_vanilla_executes_single_target_managed_uninstall_through_manifest(tmp_path):
    client_root = _root(tmp_path, "Client")
    mods_dir = client_root / "R5" / "Content" / "Paks" / "~mods"
    target_file = mods_dir / "Managed_P.pak"
    target_file.write_bytes(b"managed")
    service, manifest, _backup = _service(tmp_path, AppPaths(client_root=client_root))
    mod_id = generate_mod_id()
    manifest.add_mod(
        ModInstall(
            mod_id=mod_id,
            display_name="Managed",
            source_archive="managed.zip",
            targets=["client"],
            installed_files=[str(target_file)],
        )
    )
    plan = service.build_plan("client")

    result = service.execute_plan(
        plan,
        include_managed=True,
        include_unmanaged=False,
        include_frameworks=False,
    )

    assert result.errors == ()
    assert result.removed_managed == 1
    assert not target_file.exists()
    assert manifest.get_mod(mod_id) is None
    assert manifest.list_history()[-1].action == "uninstall"


def test_restore_vanilla_backs_up_framework_directories_before_deletion(tmp_path):
    server_root = _root(tmp_path, "Dedicated")
    ue4ss_dir = server_root / "R5" / "Binaries" / "Win64" / "ue4ss"
    ue4ss_dir.mkdir(parents=True)
    (ue4ss_dir / "UE4SS.dll").write_bytes(b"runtime")
    service, _manifest, backup = _service(tmp_path, AppPaths(dedicated_server_root=server_root))
    plan = service.build_plan("dedicated_server")

    result = service.execute_plan(
        plan,
        include_managed=False,
        include_unmanaged=False,
        include_frameworks=True,
    )

    assert result.errors == ()
    assert result.removed_frameworks == 1
    assert not ue4ss_dir.exists()
    records = backup.list_backups(category="restore_vanilla")
    assert len(records) == 1
    assert (Path(records[0].backup_path) / "UE4SS.dll").read_bytes() == b"runtime"
