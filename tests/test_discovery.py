"""Tests for dedicated-server discovery and path reconciliation."""
from pathlib import Path

from windrose_deployer.core import discovery
from windrose_deployer.models.app_paths import AppPaths


def _make_client_root(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "Windrose.exe").touch()
    (path / "R5").mkdir(exist_ok=True)
    return path


def _make_server_root(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "WindroseServer.exe").touch()
    (path / "StartServerForeground.bat").touch()
    (path / "R5").mkdir(exist_ok=True)
    return path


def test_discover_server_root_prefers_standalone_dedicated_install(monkeypatch, tmp_path):
    common_dir = tmp_path / "steamapps" / "common"
    standalone = _make_server_root(common_dir / "Windrose Dedicated Server")
    client_root = _make_client_root(tmp_path / "Windrose")
    _make_server_root(client_root / "R5" / "Builds" / "WindowsServer")

    monkeypatch.setattr(discovery, "STEAM_COMMON_DIRS", [str(common_dir)])

    discovered = discovery.discover_server_root(client_root)

    assert discovered == standalone


def test_discover_local_save_root_prefers_server_install(monkeypatch, tmp_path):
    server_root = _make_server_root(tmp_path / "Windrose Dedicated Server")
    save_root = server_root / "R5" / "Saved"
    save_root.mkdir(parents=True)
    appdata = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(appdata))
    (appdata / "R5" / "Saved").mkdir(parents=True)

    discovered = discovery.discover_local_save_root(server_root)

    assert discovered == save_root


def test_reconcile_paths_upgrades_legacy_server_root_and_appdata_save_root(monkeypatch, tmp_path):
    common_dir = tmp_path / "steamapps" / "common"
    standalone = _make_server_root(common_dir / "Windrose Dedicated Server")
    (standalone / "R5" / "Saved").mkdir(parents=True)

    client_root = _make_client_root(tmp_path / "Windrose")
    legacy = _make_server_root(client_root / "R5" / "Builds" / "WindowsServer")
    (legacy / "R5" / "Saved").mkdir(parents=True)

    appdata = tmp_path / "AppData" / "Local"
    stale_save_root = appdata / "R5" / "Saved"
    stale_save_root.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(appdata))
    monkeypatch.setattr(discovery, "STEAM_COMMON_DIRS", [str(common_dir)])

    paths = AppPaths(
        client_root=client_root,
        server_root=legacy,
        local_save_root=stale_save_root,
    )

    reconciled, changed = discovery.reconcile_paths(paths)

    assert changed
    assert reconciled.server_root == standalone
    assert reconciled.local_save_root == standalone / "R5" / "Saved"


def test_server_description_property_uses_server_root(tmp_path):
    server_root = _make_server_root(tmp_path / "Windrose Dedicated Server")
    paths = AppPaths(server_root=server_root)

    assert paths.server_description_json == server_root / "R5" / "ServerDescription.json"
