from windrose_deployer.core.archive_library_service import manager_owned_archive_path


def test_manager_owned_archive_path_copies_imported_archive(tmp_path):
    source = tmp_path / "Downloads" / "My Mod.zip"
    source.parent.mkdir()
    source.write_bytes(b"archive-data")
    library_dir = tmp_path / "data" / "archives"

    copied, digest, reused = manager_owned_archive_path(source, library_dir, [])

    assert copied.parent == library_dir
    assert copied.is_file()
    assert copied.read_bytes() == b"archive-data"
    assert digest
    assert reused is False


def test_manager_owned_archive_path_reuses_existing_hash_copy(tmp_path):
    source = tmp_path / "Downloads" / "My Mod.zip"
    source.parent.mkdir()
    source.write_bytes(b"archive-data")
    library_dir = tmp_path / "data" / "archives"
    copied, digest, _reused = manager_owned_archive_path(source, library_dir, [])

    other = tmp_path / "Downloads" / "Copy.zip"
    other.write_bytes(b"archive-data")
    reused_path, reused_digest, reused = manager_owned_archive_path(
        other,
        library_dir,
        [{"path": str(copied), "archive_hash": digest, "source_kind": "archive"}],
    )

    assert reused_path == copied
    assert reused_digest == digest
    assert reused is True
    assert len(list(library_dir.iterdir())) == 1
