import time
from types import SimpleNamespace

from windrose_deployer.core.lazy_tabs import LazyTabController
from windrose_deployer.ui.app_window import AppWindow
from windrose_deployer.ui.ui_state import banner


def test_lazy_tab_controller_constructs_once():
    calls: list[str] = []
    controller = LazyTabController({"Mods": lambda: calls.append("Mods") or object()})

    first = controller.ensure("Mods")
    second = controller.ensure("Mods")

    assert first is second
    assert calls == ["Mods"]
    assert controller.is_constructed("Mods") is True


def test_banner_state_normalizes_unknown_kind():
    state = banner("unknown", "  Ready  ")

    assert state.kind == "info"
    assert state.message == "Ready"
    assert state.background


def test_app_window_refresh_tab_constructs_selected_lazy_tab():
    app = object.__new__(AppWindow)
    calls: list[str] = []

    class FakeTab:
        def refresh_view(self):
            calls.append("refresh mods")

    def make_mods():
        calls.append("construct mods")
        app._mods_tab = FakeTab()
        return app._mods_tab

    app._lazy_tabs = LazyTabController({"Mods": make_mods})

    AppWindow._refresh_tab(app, "Mods")

    assert calls == ["construct mods", "refresh mods"]
    assert app._lazy_tabs.is_constructed("Mods") is True


def test_app_window_ensure_tab_shows_and_clears_loading_placeholder():
    app = object.__new__(AppWindow)
    calls: list[str] = []
    app._lazy_tabs = LazyTabController({"Mods": lambda: calls.append("construct mods") or object()})
    app._show_tab_loading_placeholder = lambda name: calls.append(f"show {name}")
    app.update_idletasks = lambda: calls.append("flush")
    app._clear_tab_loading_placeholder = lambda name: calls.append(f"clear {name}")
    app.tk = object()

    AppWindow._ensure_tab(app, "Mods")

    assert calls == ["show Mods", "flush", "construct mods", "clear Mods"]


def test_app_window_tab_changed_reads_current_tab_when_no_argument():
    app = object.__new__(AppWindow)
    calls: list[str] = []
    app._loaded_tabs = set()
    app._tabview = SimpleNamespace(get=lambda: "Settings")
    app._lazy_tabs = LazyTabController({"Settings": lambda: calls.append("construct settings")})
    app._settings_tab = SimpleNamespace(refresh_view=lambda: calls.append("refresh settings"))

    AppWindow._on_tab_changed(app)

    assert calls == ["construct settings", "refresh settings"]
    assert "Settings" in app._loaded_tabs


def test_app_window_refresh_mods_tab_does_not_force_unopened_tabs():
    app = object.__new__(AppWindow)
    calls: list[str] = []
    app._lazy_tabs = LazyTabController(
        {
            "Mods": lambda: calls.append("construct mods"),
            "Server": lambda: calls.append("construct server"),
        }
    )
    app._dashboard_tab = SimpleNamespace(refresh_view=lambda: calls.append("refresh dashboard"))
    app._tabview = SimpleNamespace(get=lambda: "Dashboard")
    app._update_mod_badge = lambda: calls.append("badge")

    AppWindow.refresh_mods_tab(app)

    assert calls == ["refresh dashboard", "badge"]
    assert app._lazy_tabs.is_constructed("Mods") is False
    assert app._lazy_tabs.is_constructed("Server") is False


def test_cached_process_status_uses_existing_cache_without_sync_query():
    app = object.__new__(AppWindow)
    app._process_names_cache = {"windrose.exe"}
    app._process_names_cache_at = time.monotonic()
    app._process_names_cache_ready = True
    app._request_process_names_refresh = lambda: (_ for _ in ()).throw(AssertionError("refresh requested"))

    assert AppWindow.cached_is_game_running(app) is True
    assert AppWindow.cached_is_server_process_running(app) is False


def test_app_window_refresh_mods_tab_constructs_active_server_tab():
    app = object.__new__(AppWindow)
    calls: list[str] = []

    class FakeServerTab:
        def refresh_view(self):
            calls.append("refresh server")

    def make_server():
        calls.append("construct server")
        app._server_tab = FakeServerTab()
        return app._server_tab

    app._lazy_tabs = LazyTabController({"Server": make_server})
    app._dashboard_tab = SimpleNamespace(refresh_view=lambda: calls.append("refresh dashboard"))
    app._tabview = SimpleNamespace(get=lambda: "Server")
    app._update_mod_badge = lambda: calls.append("badge")

    AppWindow.refresh_mods_tab(app)

    assert calls == ["refresh dashboard", "construct server", "refresh server", "badge"]


def test_dashboard_overview_uses_lightweight_state_before_server_tab_exists():
    app = object.__new__(AppWindow)
    app._lazy_tabs = LazyTabController({"Server": lambda: (_ for _ in ()).throw(AssertionError("server constructed"))})
    app.manifest = SimpleNamespace(
        list_mods=lambda: [
            SimpleNamespace(targets=["client", "dedicated_server"]),
            SimpleNamespace(targets=["hosted"]),
        ],
        list_history=lambda: [],
    )
    app.remote_profiles = SimpleNamespace(list_profiles=lambda: [SimpleNamespace(name="Hosted")])
    app.backup = SimpleNamespace(list_backups=lambda: [])

    overview = AppWindow.dashboard_overview(app)

    assert overview["counts"] == {"client": 1, "server": 0, "dedicated_server": 1, "hosted": 1}
    assert overview["source_key"] == "dedicated_server"
    assert overview["hosted_state"] == "Configured"
    assert app._lazy_tabs.is_constructed("Server") is False
