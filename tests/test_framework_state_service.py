from windrose_deployer.core.framework_state_service import FrameworkStateService
from windrose_deployer.models.remote_profile import RemoteProfile


class FakeProvider:
    def __init__(self, existing: set[str]):
        self.existing = existing
        self.closed = False

    def close(self):
        self.closed = True

    def path_exists(self, remote_path: str) -> bool:
        return remote_path in self.existing


def test_remote_framework_state_checks_ue4ss_rcon_and_windroseplus():
    profile = RemoteProfile(
        profile_id="p1",
        name="Hosted",
        remote_root_dir="/srv/windrose",
    )
    existing = {
        "/srv/windrose/R5/Binaries/Win64/dwmapi.dll",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/WindroseRCON",
        "/srv/windrose/R5/Binaries/Win64/ue4ss/Mods/WindrosePlus",
    }
    service = FrameworkStateService(provider_factory=lambda _profile: FakeProvider(existing))

    state = service.remote_state(profile)

    assert state.configured is True
    assert state.checked is True
    assert state.ue4ss_runtime is True
    assert state.rcon_mod is True
    assert state.windrose_plus is True
    assert state.windrose_plus_package is True
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
