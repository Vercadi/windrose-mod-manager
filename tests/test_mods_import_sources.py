import zipfile

from windrose_deployer.ui.tabs.mods_tab import ModsTab


def test_mods_tab_import_source_paths_copies_archives_and_bundles_loose_paks(tmp_path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    archive = downloads / "BetterShip.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("BetterShip_P.pak", b"pak")
    loose_dir = tmp_path / "loose"
    loose_dir.mkdir()
    for suffix in (".pak", ".ucas", ".utoc"):
        (loose_dir / f"Ship_P{suffix}").write_bytes(suffix.encode("ascii"))

    tab = object.__new__(ModsTab)
    tab._library = []
    tab._archive_info_cache = {}
    tab._save_library = lambda: None
    tab._archive_import_dir = lambda: tmp_path / "app_data" / "archives"
    tab._loose_import_dir = lambda: tmp_path / "app_data" / "imports"

    imported, warnings = ModsTab._import_source_paths(tab, [archive, loose_dir])

    assert warnings == []
    assert len(imported) == 2
    assert any(path.parent == tmp_path / "app_data" / "archives" for path in imported)
    assert any(path.parent == tmp_path / "app_data" / "imports" for path in imported)
    assert len(tab._library) == 2
    archive_entry = next(entry for entry in tab._library if entry["source_kind"] == "archive")
    assert archive_entry["manager_owned"] is True
    assert archive_entry["original_path"] == str(archive)
    bundle_entry = next(entry for entry in tab._library if entry["source_kind"] == "pak_bundle")
    assert {path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for path in bundle_entry["original_files"]} == {
        "Ship_P.pak",
        "Ship_P.ucas",
        "Ship_P.utoc",
    }
