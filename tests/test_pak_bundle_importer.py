from __future__ import annotations

import zipfile

from windrose_deployer.core.archive_inspector import inspect_archive
from windrose_deployer.core.pak_bundle_importer import import_pak_bundles, is_pak_bundle_file


def test_loose_pak_import_groups_companions_into_one_archive(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    pak = source_dir / "Example_Mod_P.pak"
    utoc = source_dir / "Example_Mod_P.utoc"
    ucas = source_dir / "Example_Mod_P.ucas"
    pak.write_bytes(b"pak-data")
    utoc.write_bytes(b"utoc-data")
    ucas.write_bytes(b"ucas-data")

    result = import_pak_bundles([pak], tmp_path / "imports")

    assert result.warnings == []
    assert len(result.created_archives) == 1
    bundle = result.created_archives[0]
    assert bundle.display_name == "Example_Mod_P"
    assert {path.name for path in bundle.source_files} == {
        "Example_Mod_P.pak",
        "Example_Mod_P.utoc",
        "Example_Mod_P.ucas",
    }

    with zipfile.ZipFile(bundle.archive_path) as archive:
        assert set(archive.namelist()) == {
            "Example_Mod_P.pak",
            "Example_Mod_P.utoc",
            "Example_Mod_P.ucas",
        }

    info = inspect_archive(bundle.archive_path)
    assert len(info.pak_entries) == 1
    assert len(info.companion_entries) == 2


def test_loose_pak_import_deduplicates_selected_companions(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    pak = source_dir / "Stack_Mod_P.pak"
    utoc = source_dir / "Stack_Mod_P.utoc"
    pak.write_bytes(b"pak")
    utoc.write_bytes(b"utoc")

    result = import_pak_bundles([pak, utoc], tmp_path / "imports")

    assert result.warnings == []
    assert len(result.created_archives) == 1
    with zipfile.ZipFile(result.created_archives[0].archive_path) as archive:
        assert archive.namelist() == ["Stack_Mod_P.pak", "Stack_Mod_P.utoc"]


def test_loose_pak_import_skips_companions_without_matching_pak(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    utoc = source_dir / "Broken_Mod_P.utoc"
    ucas = source_dir / "Broken_Mod_P.ucas"
    utoc.write_bytes(b"utoc")
    ucas.write_bytes(b"ucas")

    result = import_pak_bundles([utoc], tmp_path / "imports")

    assert result.created_archives == []
    assert result.warnings
    assert "matching .pak" in result.warnings[0]


def test_is_pak_bundle_file_only_matches_pak_companion_extensions(tmp_path):
    assert is_pak_bundle_file(tmp_path / "a.pak")
    assert is_pak_bundle_file(tmp_path / "a.utoc")
    assert is_pak_bundle_file(tmp_path / "a.ucas")
    assert not is_pak_bundle_file(tmp_path / "a.zip")
