"""Tests for bundled-server and dedicated-server discovery."""
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


def test_discover_bundled_server_root_uses_windowsserver_under_client(tmp_path):
    client_root = _make_client_root(tmp_path / "Windrose")
    bundled = _make_server_root(client_root / "R5" / "Builds" / "WindowsServer")

    discovered = discovery.discover_bundled_server_root(client_root)

    assert discovered == bundled


def test_discover_dedicated_server_root_finds_standalone_install(monkeypatch, tmp_path):
    common_dir = tmp_path / "steamapps" / "common"
    standalone = _make_server_root(common_dir / "Windrose Dedicated Server")

    monkeypatch.setattr(discovery, "STEAM_COMMON_DIRS", [str(common_dir)])

    discovered = discovery.discover_dedicated_server_root()

    assert discovered == standalone


def test_discover_all_returns_both_local_server_targets(monkeypatch, tmp_path):
    common_dir = tmp_path / "steamapps" / "common"
    standalone = _make_server_root(common_dir / "Windrose Dedicated Server")
    (standalone / "R5" / "Saved").mkdir(parents=True)
    client_root = _make_client_root(common_dir / "Windrose")
    bundled = _make_server_root(client_root / "R5" / "Builds" / "WindowsServer")

    monkeypatch.setattr(discovery, "STEAM_COMMON_DIRS", [str(common_dir)])

    detected = discovery.discover_all()

    assert detected.client_root == client_root
    assert detected.server_root == bundled
    assert detected.dedicated_server_root == standalone
    assert detected.local_save_root == standalone / "R5" / "Saved"


def test_reconcile_paths_splits_old_collapsed_server_setting(monkeypatch, tmp_path):
    common_dir = tmp_path / "steamapps" / "common"
    standalone = _make_server_root(common_dir / "Windrose Dedicated Server")
    (standalone / "R5" / "Saved").mkdir(parents=True)

    client_root = _make_client_root(common_dir / "Windrose")
    bundled = _make_server_root(client_root / "R5" / "Builds" / "WindowsServer")
    (bundled / "R5" / "Saved").mkdir(parents=True)

    appdata = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(appdata))
    monkeypatch.setattr(discovery, "STEAM_COMMON_DIRS", [str(common_dir)])

    paths = AppPaths(
        client_root=client_root,
        server_root=standalone,
        local_save_root=standalone / "R5" / "Saved",
    )

    reconciled, changed = discovery.reconcile_paths(paths)

    assert changed
    assert reconciled.server_root == bundled
    assert reconciled.dedicated_server_root == standalone
    assert reconciled.local_save_root == standalone / "R5" / "Saved"


def test_server_description_property_uses_dedicated_server_root(tmp_path):
    dedicated_root = _make_server_root(tmp_path / "Windrose Dedicated Server")
    paths = AppPaths(dedicated_server_root=dedicated_root)

    assert paths.server_description_json == dedicated_root / "R5" / "ServerDescription.json"


def test_reconcile_paths_skips_broad_discovery_when_saved_paths_are_valid(monkeypatch, tmp_path):
    client_root = _make_client_root(tmp_path / "Windrose")
    bundled = _make_server_root(client_root / "R5" / "Builds" / "WindowsServer")
    standalone = _make_server_root(tmp_path / "Windrose Dedicated Server")
    local_config = tmp_path / "Config" / "Windows"
    local_config.mkdir(parents=True)
    local_save_root = standalone / "R5" / "Saved"
    local_save_root.mkdir(parents=True)

    called = {"discover": False}

    def _unexpected_discover_all(*args, **kwargs):
        called["discover"] = True
        raise AssertionError("discover_all should not run when saved paths are already valid")

    monkeypatch.setattr(discovery, "discover_all", _unexpected_discover_all)

    reconciled, changed = discovery.reconcile_paths(
        AppPaths(
            client_root=client_root,
            server_root=bundled,
            dedicated_server_root=standalone,
            local_config=local_config,
            local_save_root=local_save_root,
        )
    )

    assert not called["discover"]
    assert not changed
    assert reconciled.client_root == client_root
