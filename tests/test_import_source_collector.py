from pathlib import Path

from windrose_deployer.core.import_source_collector import collect_importable_sources


def test_collect_direct_archive_and_pak_sources(tmp_path: Path) -> None:
    archive = tmp_path / "BetterWind.zip"
    pak = tmp_path / "BetterWind_P.pak"
    unsupported = tmp_path / "notes.txt"
    archive.write_bytes(b"zip")
    pak.write_bytes(b"pak")
    unsupported.write_text("notes", encoding="utf-8")

    result = collect_importable_sources([archive, pak, unsupported])

    assert result.archive_files == [archive]
    assert result.pak_files == [pak]
    assert "Skipped unsupported file: notes.txt" in result.warnings


def test_collect_folder_scans_supported_files_one_level_deep(tmp_path: Path) -> None:
    folder = tmp_path / "Downloads"
    nested = folder / "Extracted"
    deep = nested / "TooDeep"
    deep.mkdir(parents=True)
    direct_archive = folder / "One.zip"
    nested_archive = nested / "Two.7z"
    deep_archive = deep / "Three.zip"
    direct_archive.write_bytes(b"one")
    nested_archive.write_bytes(b"two")
    deep_archive.write_bytes(b"three")
    (folder / "readme.md").write_text("readme", encoding="utf-8")

    result = collect_importable_sources([folder])

    assert result.archive_files == [direct_archive, nested_archive]
    assert deep_archive not in result.archive_files
    assert result.scanned_folders == [folder]
    assert any("unsupported file" in warning for warning in result.warnings)


def test_collect_folder_with_loose_pak_companions(tmp_path: Path) -> None:
    folder = tmp_path / "LoosePak"
    folder.mkdir()
    pak = folder / "Example_P.pak"
    utoc = folder / "Example_P.utoc"
    ucas = folder / "Example_P.ucas"
    pak.write_bytes(b"pak")
    utoc.write_bytes(b"utoc")
    ucas.write_bytes(b"ucas")

    result = collect_importable_sources([folder])

    assert result.archive_files == []
    assert result.pak_files == [pak, ucas, utoc]
    assert result.warnings == []


def test_collect_unsupported_folder_contents_are_concise(tmp_path: Path) -> None:
    folder = tmp_path / "BadFolder"
    folder.mkdir()
    for index in range(5):
        (folder / f"file{index}.txt").write_text("bad", encoding="utf-8")

    result = collect_importable_sources([folder])

    assert result.supported_files == []
    assert result.warnings == [
        "No supported mod files found in folder: BadFolder",
        "Skipped 5 unsupported file(s) while scanning BadFolder.",
    ]
