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
