from windrose_deployer.core.framework_state_service import FrameworkStateService, FrameworkTargetState
from windrose_deployer.core.remote_provider import RemoteEntry
from windrose_deployer.models.remote_profile import RemoteProfile
from windrose_deployer.ui.tabs.dashboard_tab import DashboardTab


class FakeProvider:
    def __init__(self, existing: set[str]):
        self.existing = existing
        self.closed = False

    def close(self):
        self.closed = True

    def path_exists(self, remote_path: str) -> bool:
        return remote_path in self.existing

    def list_entries(self, remote_dir: str) -> list[RemoteEntry]:
        prefix = remote_dir.rstrip("/") + "/"
        entries: list[RemoteEntry] = []
        seen: set[str] = set()
        for path in self.existing:
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix):]
            if not rest:
                continue
            name = rest.split("/", 1)[0]
            if name in seen:
                continue
            seen.add(name)
            full_path = prefix + name
            entries.append(RemoteEntry(path=full_path, name=name, is_dir="/" in rest))
        return entries


def test_remote_framework_state_checks_ue4ss_rcon_and_windroseplus():
    profile = RemoteProfile(
        profile_id="p1",
        name="Hosted",
        remote_root_dir="/srv/windrose",
    )
    existing = {
        "/srv/windrose/R5/Binaries/Win64/dwmapi.dll",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/UE4SS.dll",
        "/srv/windrose/R5/Binaries/Win64/version.dll",
        "/srv/windrose/R5/Binaries/Win64/windrosercon/settings.ini",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/WindrosePlus",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/WindrosePlus/Scripts/main.lua",
        "/srv/windrose/StartWindrosePlusServer.bat",
    }
    service = FrameworkStateService(provider_factory=lambda _profile: FakeProvider(existing))

    state = service.remote_state(profile)

    assert state.configured is True
    assert state.checked is True
    assert state.ue4ss_runtime is True
    assert state.rcon_mod is True
    assert state.windrose_plus is True
    assert state.windrose_plus_package is True
    assert state.windrose_plus_launch_wrapper is True
    assert state.summary == "UE4SS + RCON + WindrosePlus"


def test_remote_framework_state_checks_windroseplus_package_files():
    profile = RemoteProfile(
        profile_id="p1",
        name="Hosted",
        remote_root_dir="/srv/windrose",
    )
    service = FrameworkStateService(
        provider_factory=lambda _profile: FakeProvider({"/srv/windrose/WindrosePlus"})
    )

    state = service.remote_state(profile)

    assert state.windrose_plus is False
    assert state.windrose_plus_package is True
    assert state.summary == "WindrosePlus files"


def test_remote_framework_state_detects_generated_windroseplus_paks():
    profile = RemoteProfile(
        profile_id="p1",
        name="Hosted",
        remote_root_dir="/srv/windrose",
    )
    service = FrameworkStateService(
        provider_factory=lambda _profile: FakeProvider({
            "/srv/windrose/R5/Content/Paks/WindrosePlus_Multipliers_P.pak",
        })
    )

    state = service.remote_state(profile)

    assert state.windrose_plus_generated_paks is True
    assert state.windrose_plus_partial is True


def test_remote_framework_state_ignores_empty_rcon_folder():
    profile = RemoteProfile(
        profile_id="p1",
        name="Hosted",
        remote_root_dir="/srv/windrose",
    )
    service = FrameworkStateService(
        provider_factory=lambda _profile: FakeProvider({
            "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/WindroseRCON",
        })
    )

    state = service.remote_state(profile)

    assert state.rcon_mod is False


def test_dashboard_rcon_text_marks_client_install_as_wrong_target():
    states = {
        "client": FrameworkTargetState(configured=True, rcon_mod=True),
        "server": FrameworkTargetState(configured=True, rcon_mod=True, rcon_configured=True),
        "dedicated_server": FrameworkTargetState(configured=True, rcon_mod=False),
    }

    assert DashboardTab._rcon_text(states) == "Local | Wrong target: Client"


def test_dashboard_rcon_text_marks_settings_pending():
    states = {
        "client": FrameworkTargetState(configured=True),
        "server": FrameworkTargetState(configured=True, rcon_mod=True, rcon_configured=False),
        "dedicated_server": FrameworkTargetState(configured=True),
    }

    assert DashboardTab._rcon_text(states) == "Local | Settings pending: Local"
