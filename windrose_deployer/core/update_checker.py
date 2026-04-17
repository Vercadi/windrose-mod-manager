"""Check GitHub Releases for newer versions and download release assets."""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/Vercadi/windrose-mod-manager/releases/latest"
USER_AGENT = "Windrose-Mod-Manager-Updater"
IGNORED_ASSET_SUFFIXES = (".sha256", ".sha1", ".txt", ".sig", ".asc", ".json")
PREFERRED_ASSET_SUFFIXES = (".zip", ".7z", ".msi", ".exe")


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int = 0


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    html_url: str
    assets: list[ReleaseAsset]

    @property
    def preferred_asset(self) -> ReleaseAsset | None:
        return _pick_preferred_asset(self.assets)


def check_for_update(
    current_version: str,
    callback: Callable[[ReleaseInfo], None],
    no_update_callback: Callable[[], None] | None = None,
    error_callback: Callable[[str], None] | None = None,
) -> None:
    """Check GitHub for a newer release in a background thread."""

    def _worker() -> None:
        try:
            release = _fetch_latest_release()
            if _is_newer(release.version, current_version):
                log.info("Update available: %s (current: %s)", release.version, current_version)
                callback(release)
            else:
                log.debug("Up to date (remote=%s, local=%s)", release.version, current_version)
                if no_update_callback:
                    no_update_callback()
        except Exception as exc:
            log.debug("Update check failed (non-critical): %s", exc)
            if error_callback:
                error_callback(str(exc))

    threading.Thread(target=_worker, daemon=True).start()


def download_release_asset(
    release: ReleaseInfo,
    *,
    dest_dir: Path | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    complete_callback: Callable[[Path | None, str | None], None] | None = None,
) -> None:
    """Download the preferred release asset in a background thread."""
    asset = release.preferred_asset
    if asset is None:
        if complete_callback:
            complete_callback(None, "No downloadable release asset was found.")
        return

    target_dir = dest_dir or _downloads_dir()

    def _worker() -> None:
        target_path = _dedupe_path(target_dir / asset.name)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            req = Request(
                asset.download_url,
                headers={"Accept": "application/octet-stream", "User-Agent": USER_AGENT},
            )
            with urlopen(req, timeout=20) as resp, target_path.open("wb") as handle:
                total = int(resp.headers.get("Content-Length") or asset.size or 0)
                downloaded = 0
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total, asset.name)

            log.info("Downloaded update %s to %s", release.version, target_path)
            if complete_callback:
                complete_callback(target_path, None)
        except Exception as exc:
            log.warning("Update download failed: %s", exc)
            try:
                if target_path.exists():
                    target_path.unlink()
            except OSError:
                pass
            if complete_callback:
                complete_callback(None, str(exc))

    threading.Thread(target=_worker, daemon=True).start()


def _fetch_latest_release() -> ReleaseInfo:
    req = Request(
        GITHUB_API_URL,
        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": USER_AGENT},
    )
    with urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode())
    return _release_info_from_api(data)


def _release_info_from_api(data: dict) -> ReleaseInfo:
    assets = [
        ReleaseAsset(
            name=asset.get("name", ""),
            download_url=asset.get("browser_download_url", ""),
            size=int(asset.get("size") or 0),
        )
        for asset in data.get("assets", [])
        if asset.get("name") and asset.get("browser_download_url")
    ]
    return ReleaseInfo(
        version=str(data.get("tag_name", "")).lstrip("vV"),
        html_url=str(data.get("html_url", "")),
        assets=assets,
    )


def _pick_preferred_asset(assets: list[ReleaseAsset]) -> ReleaseAsset | None:
    candidates = [
        asset for asset in assets
        if not asset.name.lower().endswith(IGNORED_ASSET_SUFFIXES)
    ]
    if not candidates:
        return None

    lower_names = {asset.name: asset.name.lower() for asset in candidates}
    for suffix in PREFERRED_ASSET_SUFFIXES:
        for asset in candidates:
            if lower_names[asset.name].endswith(suffix):
                return asset

    return candidates[0]


def _downloads_dir() -> Path:
    return Path.home() / "Downloads"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _is_newer(remote: str, local: str) -> bool:
    """Simple semver comparison: '0.3.1' > '0.3.0'."""
    try:
        r_parts = [int(x) for x in remote.split(".")]
        l_parts = [int(x) for x in local.split(".")]
        return r_parts > l_parts
    except (ValueError, AttributeError):
        return False
