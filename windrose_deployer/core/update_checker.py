"""Check GitHub Releases for newer versions (non-blocking)."""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/Vercadi/windrose-mod-manager/releases/latest"


def check_for_update(
    current_version: str,
    callback: Callable[[str, str], None],
) -> None:
    """Check GitHub for a newer release in a background thread.

    If a newer version is found, *callback(new_version, download_url)* is
    called on the same thread.  The caller must schedule UI updates
    via ``after()`` if needed.
    """
    def _worker() -> None:
        try:
            import urllib.request
            import json

            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())

            tag = data.get("tag_name", "")
            remote_version = tag.lstrip("vV")
            html_url = data.get("html_url", "")

            if _is_newer(remote_version, current_version):
                log.info("Update available: %s (current: %s)", remote_version, current_version)
                callback(remote_version, html_url)
            else:
                log.debug("Up to date (remote=%s, local=%s)", remote_version, current_version)
        except Exception as exc:
            log.debug("Update check failed (non-critical): %s", exc)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _is_newer(remote: str, local: str) -> bool:
    """Simple semver comparison: '0.3.0' > '0.2.0'."""
    try:
        r_parts = [int(x) for x in remote.split(".")]
        l_parts = [int(x) for x in local.split(".")]
        return r_parts > l_parts
    except (ValueError, AttributeError):
        return False
