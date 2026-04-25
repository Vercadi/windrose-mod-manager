from pathlib import Path
from types import SimpleNamespace

import pytest

from windrose_deployer.core.live_mod_inventory import bundle_live_file_names, snapshot_live_mods_folder
from windrose_deployer.core.manifest_store import ManifestStore
from windrose_deployer.models.mod_install import ModInstall
from windrose_deployer.ui.tabs.mods_tab import ModsTab
from windrose_deployer.utils.naming import generate_mod_id


def test_snapshot_live_mods_folder_reports_unmanaged_and_managed_files(tmp_path):
    mods_dir = tmp_path / "R5" / "Content" / "Paks" / "~mods"
    mods_dir.mkdir(parents=True)
    (mods_dir / "Managed_P.pak").write_text("managed", encoding="utf-8")
    (mods_dir / "Manual_P.pak").write_text("manual", encoding="utf-8")

    mods = [
        ModInstall(
            mod_id=generate_mod_id(),
            display_name="Managed",
            source_archive="Managed.zip",
            targets=["client"],
            installed_files=[str(mods_dir / "Managed_P.pak")],
        )
    ]

    snapshot = snapshot_live_mods_folder(mods_dir, mods, target="client")

    assert snapshot.warning is None
    assert snapshot.managed_present_files == ["Managed_P.pak"]
    assert snapshot.unmanaged_files == ["Manual_P.pak"]
    assert snapshot.missing_managed_files == []


def test_snapshot_live_mods_folder_reports_missing_expected_files(tmp_path):
    mods_dir = tmp_path / "R5" / "Content" / "Paks" / "~mods"
    expected = mods_dir / "Missing_P.pak"
    mods = [
        ModInstall(
            mod_id=generate_mod_id(),
            display_name="Managed",
            source_archive="Managed.zip",
            targets=["server"],
            installed_files=[str(expected)],
        )
    ]

    snapshot = snapshot_live_mods_folder(mods_dir, mods, target="server")

    assert snapshot.warning is not None
    assert snapshot.missing_managed_files == ["Missing_P.pak"]


def test_bundle_live_file_names_groups_ue5_companion_files():
    bundles = bundle_live_file_names(
        [
            "Example_P.pak",
            "Example_P.utoc",
            "Example_P.ucas",
            "Solo_P.pak",
        ]
    )

    assert [(bundle.display_name, list(bundle.file_names)) for bundle in bundles] == [
        ("Example_P", ["Example_P.pak", "Example_P.utoc", "Example_P.ucas"]),
        ("Solo_P", ["Solo_P.pak"]),
    ]


def test_available_archives_filter_hides_applied_sources(tmp_path):
    manifest = ManifestStore(tmp_path / "data")
    manifest.add_mod(
        ModInstall(
            mod_id=generate_mod_id(),
            display_name="Installed",
            source_archive="installed.zip",
            targets=["client"],
            installed_files=["C:/game/mod.pak"],
        )
    )

    tab = object.__new__(ModsTab)
    tab.app = SimpleNamespace(manifest=manifest)
    tab._library = [
        {"path": "installed.zip", "name": "installed", "ext": ".zip"},
        {"path": "available.zip", "name": "available", "ext": ".zip"},
    ]
    tab._search_var = SimpleNamespace(get=lambda: "")
    tab._filter_var = SimpleNamespace(get=lambda: "Available Archives")
    tab._scope_var = SimpleNamespace(get=lambda: "all")

    entries = ModsTab._filtered_entries(tab)

    assert [entry["path"] for entry in entries] == ["available.zip"]


@pytest.mark.parametrize("install_kind", ["ue4ss_runtime", "ue4ss_mod"])
def test_framework_source_archive_returns_to_inactive_after_last_uninstall(tmp_path, install_kind):
    manifest = ManifestStore(tmp_path / "data")
    archive_path = str(tmp_path / "data" / "archives" / f"{install_kind}.zip")

    tab = object.__new__(ModsTab)
    tab.app = SimpleNamespace(manifest=manifest)
    tab._library = [{"path": archive_path, "name": install_kind, "ext": ".zip", "install_kind": install_kind}]
    tab._search_var = SimpleNamespace(get=lambda: "")
    tab._filter_var = SimpleNamespace(get=lambda: "Available Archives")
    tab._scope_var = SimpleNamespace(get=lambda: "all")

    mod_id = generate_mod_id()
    manifest.add_mod(
        ModInstall(
            mod_id=mod_id,
            display_name=install_kind,
            source_archive=archive_path,
            install_kind=install_kind,
            targets=["dedicated_server"],
            installed_files=["D:/server/R5/Binaries/Win64/ue4ss/file.txt"],
        )
    )
    assert ModsTab._filtered_entries(tab) == []

    manifest.remove_mod(mod_id)
    entries = ModsTab._filtered_entries(tab)

    assert [entry["path"] for entry in entries] == [archive_path]
