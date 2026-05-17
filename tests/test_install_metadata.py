from pathlib import Path
import zipfile

from windrose_deployer.core.archive_inspector import inspect_archive
from windrose_deployer.core.backup_manager import BackupManager
from windrose_deployer.core.deployment_planner import ALL_VARIANTS, plan_deployment
from windrose_deployer.core.installer import Installer
from windrose_deployer.core.manifest_store import ManifestStore
from windrose_deployer.models.app_paths import AppPaths
from windrose_deployer.models.mod_install import InstallTarget


def test_installer_persists_layout_metadata_for_selected_component_install(tmp_path: Path):
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("BetterWind_P.pak", "pak")
        zf.writestr("BetterWind_P.utoc", "utoc")
        zf.writestr("README.md", "readme")

    root = tmp_path / "Windrose"
    paths = AppPaths(client_root=root)
    info = inspect_archive(archive)
    plan = plan_deployment(
        info,
        paths,
        InstallTarget.CLIENT,
        mod_name="Better Wind",
        selected_entries={"BetterWind_P.pak"},
    )

    mod, record = Installer(BackupManager(tmp_path / "backups")).install(plan)

    assert mod.archive_hash
    assert mod.layout_kind == "standard_pak_archive"
    assert mod.target_root_hint == "paks"
    assert mod.selected_entries == ["BetterWind_P.pak"]
    assert sorted(mod.installed_archive_entries) == ["BetterWind_P.pak", "BetterWind_P.utoc"]
    assert record.archive_hash == mod.archive_hash
    assert record.layout_kind == mod.layout_kind
    assert record.selected_entries == ["BetterWind_P.pak"]
    assert sorted(record.installed_archive_entries) == ["BetterWind_P.pak", "BetterWind_P.utoc"]


def test_manifest_round_trip_preserves_variant_and_layout_metadata(tmp_path: Path):
    archive = tmp_path / "variants.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("MoreStacks_x10_P.pak", "ten")
        zf.writestr("MoreStacks_x20_P.pak", "twenty")

    root = tmp_path / "Windrose"
    info = inspect_archive(archive)
    plan = plan_deployment(
        info,
        AppPaths(client_root=root),
        InstallTarget.CLIENT,
        selected_variant=ALL_VARIANTS,
        mod_name="More Stacks",
    )
    mod, record = Installer(BackupManager(tmp_path / "backups")).install(plan)

    store = ManifestStore(tmp_path / "data")
    store.add_mod(mod)
    store.add_record(record)
    loaded = ManifestStore(tmp_path / "data")
    loaded_mod = loaded.get_mod(mod.mod_id)
    loaded_record = loaded.list_history()[0]

    assert loaded_mod is not None
    assert loaded_mod.selected_variant == ALL_VARIANTS
    assert loaded_mod.layout_kind == "multi_variant_pak_archive"
    assert sorted(loaded_mod.installed_archive_entries) == ["MoreStacks_x10_P.pak", "MoreStacks_x20_P.pak"]
    assert loaded_record.selected_variant == ALL_VARIANTS
    assert loaded_record.layout_kind == "multi_variant_pak_archive"
    assert sorted(loaded_record.installed_archive_entries) == ["MoreStacks_x10_P.pak", "MoreStacks_x20_P.pak"]
