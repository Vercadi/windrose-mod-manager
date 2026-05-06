from windrose_deployer.core.lazy_tabs import LazyTabController
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
