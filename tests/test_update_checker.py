"""Tests for GitHub release parsing and asset selection."""
from pathlib import Path

from windrose_deployer.core.update_checker import (
    ReleaseAsset,
    _dedupe_path,
    _pick_preferred_asset,
    _release_info_from_api,
)


def test_release_info_prefers_zip_asset() -> None:
    release = _release_info_from_api({
        "tag_name": "v0.2.1",
        "html_url": "https://github.com/example/release",
        "assets": [
            {
                "name": "windrose-mod-manager-0.2.1.sha256",
                "browser_download_url": "https://example.com/checksum",
                "size": 64,
            },
            {
                "name": "windrose-mod-manager-0.2.1.exe",
                "browser_download_url": "https://example.com/app.exe",
                "size": 123,
            },
            {
                "name": "windrose-mod-manager-0.2.1.zip",
                "browser_download_url": "https://example.com/app.zip",
                "size": 456,
            },
        ],
    })

    assert release.version == "0.2.1"
    assert release.preferred_asset is not None
    assert release.preferred_asset.name.endswith(".zip")


def test_pick_preferred_asset_falls_back_to_first_real_asset() -> None:
    asset = _pick_preferred_asset([
        ReleaseAsset("windrose-mod-manager-0.2.1.bin", "https://example.com/app.bin"),
        ReleaseAsset("windrose-mod-manager-0.2.1.txt", "https://example.com/notes.txt"),
    ])

    assert asset is not None
    assert asset.name.endswith(".bin")


def test_dedupe_path_adds_numeric_suffix(tmp_path: Path) -> None:
    original = tmp_path / "Windrose Mod Manager.zip"
    original.write_text("existing", encoding="utf-8")

    second = _dedupe_path(original)
    second.write_text("existing", encoding="utf-8")

    third = _dedupe_path(original)

    assert second.name == "Windrose Mod Manager (1).zip"
    assert third.name == "Windrose Mod Manager (2).zip"
