from pathlib import Path

from windrose_deployer.core.deployment_planner import plan_deployment
from windrose_deployer.models.app_paths import AppPaths
from windrose_deployer.models.archive_info import ArchiveEntry, ArchiveInfo, ArchiveType
from windrose_deployer.models.mod_install import InstallTarget


def test_plan_deployment_can_limit_to_selected_bundle_entries(tmp_path):
    client_root = tmp_path / "Windrose"
    paths = AppPaths(client_root=client_root)
    info = ArchiveInfo(
        archive_path="bundle.zip",
        archive_type=ArchiveType.PAK_ONLY,
        entries=[
            ArchiveEntry(path="MoreStacks_10x_P.pak"),
            ArchiveEntry(path="MoreStacks_10x_P.utoc"),
            ArchiveEntry(path="MoreStacks_100x_P.pak"),
        ],
        pak_entries=[
            ArchiveEntry(path="MoreStacks_10x_P.pak"),
            ArchiveEntry(path="MoreStacks_100x_P.pak"),
        ],
        companion_entries=[ArchiveEntry(path="MoreStacks_10x_P.utoc")],
        suggested_target="paks",
    )

    plan = plan_deployment(
        info,
        paths,
        InstallTarget.CLIENT,
        selected_entries={"MoreStacks_10x_P.pak"},
    )

    names = sorted(Path(file.dest_path).name for file in plan.files)
    assert names == ["MoreStacks_10x_P.pak", "MoreStacks_10x_P.utoc"]


def test_plan_deployment_routes_ue4ss_runtime_to_win64(tmp_path):
    root = tmp_path / "Windrose"
    paths = AppPaths(client_root=root)
    info = ArchiveInfo(
        archive_path="ue4ss.zip",
        archive_type=ArchiveType.LOOSE_FILES,
        entries=[
            ArchiveEntry(path="UE4SS/dwmapi.dll"),
            ArchiveEntry(path="UE4SS/ue4ss/UE4SS.dll"),
            ArchiveEntry(path="UE4SS/readme.txt"),
        ],
        loose_entries=[
            ArchiveEntry(path="UE4SS/dwmapi.dll"),
            ArchiveEntry(path="UE4SS/ue4ss/UE4SS.dll"),
            ArchiveEntry(path="UE4SS/readme.txt"),
        ],
        root_prefix="UE4SS/",
        install_kind="ue4ss_runtime",
    )

    plan = plan_deployment(info, paths, InstallTarget.CLIENT)

    assert plan.valid
    destinations = sorted(str(file.dest_path.relative_to(root)) for file in plan.files)
    assert destinations == [
        "R5\\Binaries\\Win64\\dwmapi.dll",
        "R5\\Binaries\\Win64\\ue4ss\\UE4SS.dll",
    ]


def test_plan_deployment_routes_root_ue4ss_mod_to_mods_folder(tmp_path):
    root = tmp_path / "Windrose"
    paths = AppPaths(dedicated_server_root=root)
    info = ArchiveInfo(
        archive_path="ToggleSprint.zip",
        archive_type=ArchiveType.LOOSE_FILES,
        entries=[
            ArchiveEntry(path="ToggleSprint/enabled.txt"),
            ArchiveEntry(path="ToggleSprint/Scripts/main.lua"),
        ],
        loose_entries=[
            ArchiveEntry(path="ToggleSprint/enabled.txt"),
            ArchiveEntry(path="ToggleSprint/Scripts/main.lua"),
        ],
        root_prefix="ToggleSprint/",
        install_kind="ue4ss_mod",
    )

    plan = plan_deployment(info, paths, InstallTarget.DEDICATED_SERVER)

    assert plan.valid
    destinations = sorted(str(file.dest_path.relative_to(root)) for file in plan.files)
    assert destinations == [
        "R5\\Binaries\\Win64\\ue4ss\\Mods\\ToggleSprint\\Scripts\\main.lua",
        "R5\\Binaries\\Win64\\ue4ss\\Mods\\ToggleSprint\\enabled.txt",
    ]


def test_plan_deployment_rejects_windrose_plus_client_target(tmp_path):
    paths = AppPaths(client_root=tmp_path / "Windrose")
    info = ArchiveInfo(
        archive_path="windroseplus.zip",
        archive_type=ArchiveType.LOOSE_FILES,
        entries=[ArchiveEntry(path="WindrosePlus/Scripts/main.lua")],
        loose_entries=[ArchiveEntry(path="WindrosePlus/Scripts/main.lua")],
        install_kind="windrose_plus",
    )

    plan = plan_deployment(info, paths, InstallTarget.CLIENT)

    assert not plan.valid
    assert plan.file_count == 0


def test_plan_deployment_routes_windrose_plus_package_to_server_root(tmp_path):
    root = tmp_path / "Windrose Dedicated Server"
    paths = AppPaths(dedicated_server_root=root)
    info = ArchiveInfo(
        archive_path="windrose-plus.zip",
        archive_type=ArchiveType.LOOSE_FILES,
        entries=[
            ArchiveEntry(path="windrose+/install.ps1"),
            ArchiveEntry(path="windrose+/UE4SS-settings.ini"),
            ArchiveEntry(path="windrose+/WindrosePlus/enabled.txt"),
            ArchiveEntry(path="windrose+/WindrosePlus/Scripts/main.lua"),
        ],
        loose_entries=[
            ArchiveEntry(path="windrose+/install.ps1"),
            ArchiveEntry(path="windrose+/UE4SS-settings.ini"),
            ArchiveEntry(path="windrose+/WindrosePlus/enabled.txt"),
            ArchiveEntry(path="windrose+/WindrosePlus/Scripts/main.lua"),
        ],
        root_prefix="windrose+/",
        install_kind="windrose_plus",
    )

    plan = plan_deployment(info, paths, InstallTarget.DEDICATED_SERVER)

    assert plan.valid
    destinations = sorted(str(file.dest_path.relative_to(root)) for file in plan.files)
    assert destinations == [
        "UE4SS-settings.ini",
        "WindrosePlus\\Scripts\\main.lua",
        "WindrosePlus\\enabled.txt",
        "install.ps1",
    ]
