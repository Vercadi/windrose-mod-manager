from pathlib import Path

from windrose_deployer.core.deployment_planner import plan_deployment
from windrose_deployer.core.install_report import (
    archive_summary_lines,
    build_local_install_report,
    build_remote_install_report,
)
from windrose_deployer.core.remote_deployer import RemoteDeploymentPlan, RemotePlannedFile
from windrose_deployer.models.app_paths import AppPaths
from windrose_deployer.models.archive_info import ArchiveEntry, ArchiveInfo, ArchiveType, VariantGroup
from windrose_deployer.models.mod_install import InstallTarget


def test_archive_summary_calls_out_counts_variants_and_config_files():
    pak_10 = ArchiveEntry(path="pak/Stacks_x10_P.pak")
    pak_20 = ArchiveEntry(path="pak/Stacks_x20_P.pak")
    info = ArchiveInfo(
        archive_path="Stacks.zip",
        archive_type=ArchiveType.MULTI_VARIANT_PAK,
        entries=[
            pak_10,
            pak_20,
            ArchiveEntry(path="manifest.json"),
            ArchiveEntry(path="README.md"),
        ],
        pak_entries=[pak_10, pak_20],
        loose_entries=[
            ArchiveEntry(path="manifest.json"),
            ArchiveEntry(path="README.md"),
        ],
        variant_groups=[VariantGroup(base_name="Stacks_", variants=[pak_10, pak_20])],
        install_kind="standard_mod",
    )

    text = "\n".join(archive_summary_lines(info))

    assert "2 pak files" in text
    assert "2 config/metadata files" in text
    assert "Variants:" in text
    assert "manifest.json" in text


def test_local_install_report_includes_destination_preview_and_risk(tmp_path: Path):
    pak = ArchiveEntry(path="BetterWind_P.pak")
    info = ArchiveInfo(
        archive_path="BetterWind.zip",
        archive_type=ArchiveType.PAK_ONLY,
        entries=[pak],
        pak_entries=[pak],
        install_kind="standard_mod",
    )
    paths = AppPaths(client_root=tmp_path / "Windrose")
    plan = plan_deployment(info, paths, InstallTarget.CLIENT, mod_name="Better Wind")

    report = build_local_install_report(
        info=info,
        mod_name="Better Wind",
        preset_label="Client only",
        selected_variant=None,
        prepared_plans=[(InstallTarget.CLIENT, plan)],
        plan_warnings=[],
        conflict_lines=[],
    )

    assert "Install review" in report
    assert "Better Wind" in report
    assert "UE4SS: not required by detected layout" in report
    assert "BetterWind_P.pak" in report
    assert "Managed conflicts: none detected" in report
    assert "Backup:" in report


def test_remote_install_report_calls_out_external_ue4ss():
    lua = ArchiveEntry(path="scripts/main.lua")
    info = ArchiveInfo(
        archive_path="BetterWindUE4SS.zip",
        archive_type=ArchiveType.LOOSE_FILES,
        entries=[lua],
        loose_entries=[lua],
        install_kind="ue4ss_mod",
        framework_name="UE4SS",
    )
    plan = RemoteDeploymentPlan(
        profile_id="hosted",
        mod_name="BetterWindUE4SS",
        archive_path="BetterWindUE4SS.zip",
        files=[
            RemotePlannedFile(
                archive_entry_path="scripts/main.lua",
                remote_path="/R5/Binaries/Win64/ue4ss/Mods/BetterWindUE4SS/scripts/main.lua",
            )
        ],
    )

    report = build_remote_install_report(
        info=info,
        profile_name="Bisect",
        selected_variant=None,
        plan=plan,
        ue4ss_external=True,
    )

    assert "Hosted upload review" in report
    assert "UE4SS: managed outside the app" in report
    assert "runtime will not be replaced" in report
