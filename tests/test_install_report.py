from pathlib import Path
import zipfile

from windrose_deployer.core.archive_inspector import inspect_archive
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
    assert "2 config/support files" in text
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
    assert "Layout: Standard Pak Archive" in report
    assert "Destination hint: paks" in report
    assert "Selection:" in report
    assert "UE4SS: not required by detected layout" in report
    assert "BetterWind_P.pak" in report
    assert "Managed conflicts: none detected" in report
    assert "Backup:" in report


def test_local_install_report_includes_selected_entries_and_skipped_support_warning(tmp_path: Path):
    archive = tmp_path / "mixed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("BetterWind_P.pak", "pak")
        zf.writestr("Config/settings.ini", "value=true")
        zf.writestr("README.md", "readme")

    info = inspect_archive(archive)
    paths = AppPaths(client_root=tmp_path / "Windrose")
    plan = plan_deployment(
        info,
        paths,
        InstallTarget.CLIENT,
        mod_name="Better Wind",
        selected_entries={"BetterWind_P.pak"},
    )

    report = build_local_install_report(
        info=info,
        mod_name="Better Wind",
        preset_label="Client only",
        selected_variant=None,
        prepared_plans=[(InstallTarget.CLIENT, plan)],
        plan_warnings=plan.warnings,
        conflict_lines=[],
    )

    assert "Layout: Mixed Archive" in report
    assert "Selected entries/components: 1" in report
    assert "Planned archive entries: 1" in report
    assert "BetterWind_P.pak" in report
    assert "Support/metadata files were skipped" in report
    assert "Config files were found" in report


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
        layout_kind="ue4ss_mod_archive",
        target_root_hint=r"R5\Binaries\Win64\ue4ss\Mods",
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
    assert "Layout: UE4SS Mod Archive" in report
    assert r"Destination hint: R5\Binaries\Win64\ue4ss\Mods" in report
    assert "UE4SS: managed outside the app" in report
    assert "runtime will not be replaced" in report


def test_remote_install_report_includes_layout_and_selected_variant():
    pak_10 = ArchiveEntry(path="MoreStacks_x10_P.pak")
    pak_20 = ArchiveEntry(path="MoreStacks_x20_P.pak")
    info = ArchiveInfo(
        archive_path="MoreStacks.zip",
        archive_type=ArchiveType.MULTI_VARIANT_PAK,
        entries=[pak_10, pak_20],
        pak_entries=[pak_10, pak_20],
        variant_groups=[VariantGroup(base_name="MoreStacks_", variants=[pak_10, pak_20])],
        install_kind="standard_mod",
    )
    plan = RemoteDeploymentPlan(
        profile_id="hosted",
        mod_name="MoreStacks",
        archive_path="MoreStacks.zip",
        selected_variant="MoreStacks_x10_P.pak",
        layout_kind="multi_variant_pak_archive",
        target_root_hint="paks",
        files=[
            RemotePlannedFile(
                archive_entry_path="MoreStacks_x10_P.pak",
                remote_path="/srv/windrose/R5/Content/Paks/~mods/MoreStacks_x10_P.pak",
                is_pak=True,
            )
        ],
    )

    report = build_remote_install_report(
        info=info,
        profile_name="Hosted",
        selected_variant="MoreStacks_x10_P.pak",
        plan=plan,
    )

    assert "Layout: Multi Variant Pak" in report
    assert "Selected variant: MoreStacks_x10_P.pak" in report
    assert "Planned archive entries: 1" in report
