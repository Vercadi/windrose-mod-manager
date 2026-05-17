from types import SimpleNamespace

from windrose_deployer.ui.tabs.dashboard_tab import DashboardTab


def test_sync_action_detail_includes_variant_component_and_layout_metadata():
    mod = SimpleNamespace(
        source_archive="MoreStacks.zip",
        layout_kind="multi_variant_pak_archive",
        target_root_hint="paks",
        selected_variant="MoreStacks_x10_P.pak",
        selected_entries=["MoreStacks_x10_P.pak"],
        installed_archive_entries=["MoreStacks_x10_P.pak", "MoreStacks_x10_P.utoc"],
        layout_warnings=["Support/metadata files were skipped during deployment planning."],
        component_map={"MoreStacks_x10_P.pak": ["C:/mods/MoreStacks_x10_P.pak"]},
    )

    detail = DashboardTab._sync_metadata_detail(
        mod,
        target_label="Local Server",
        archive_name="MoreStacks.zip",
        action="Install",
        file_count=2,
        target_hint="paks",
        layout_kind="multi_variant_pak_archive",
    )

    assert "Install 2 file(s) to Local Server" in detail
    assert "Layout: Multi Variant Pak" in detail
    assert "Variant: MoreStacks_x10_P.pak" in detail
    assert "Selected entries: 1" in detail
    assert "Installed archive entries: 2" in detail
    assert "Support/config skipped or requires review" in detail


def test_sync_action_detail_for_old_install_without_layout_metadata_is_sane():
    mod = SimpleNamespace(
        selected_variant=None,
        component_map={},
        selected_entries=[],
        installed_archive_entries=[],
        layout_warnings=[],
        layout_kind="",
        target_root_hint="",
    )

    detail = DashboardTab._sync_metadata_detail(
        mod,
        target_label="Dedicated Server",
        archive_name="old.zip",
    )

    assert detail == "Source archive: old.zip"
