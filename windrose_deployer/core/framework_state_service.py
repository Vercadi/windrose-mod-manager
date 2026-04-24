"""Detect installed UE4SS/framework state on local and hosted targets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.app_paths import AppPaths
from ..models.remote_profile import RemoteProfile
from .framework_detector import detect_framework_state, remote_framework_paths
from .remote_provider import RemoteProvider
from .remote_provider_factory import create_remote_provider


@dataclass(frozen=True)
class FrameworkTargetState:
    configured: bool = False
    ue4ss_runtime: bool = False
    rcon_mod: bool = False
    windrose_plus: bool = False
    windrose_plus_package: bool = False
    checked: bool = True
    warning: str = ""

    @property
    def summary(self) -> str:
        if not self.configured:
            return "Not configured"
        if not self.checked:
            return "Unknown"
        bits = []
        if self.ue4ss_runtime:
            bits.append("UE4SS")
        if self.rcon_mod:
            bits.append("RCON")
        if self.windrose_plus:
            bits.append("WindrosePlus")
        elif self.windrose_plus_package:
            bits.append("WindrosePlus files")
        return " + ".join(bits) if bits else "Missing"


class FrameworkStateService:
    def __init__(self, provider_factory=None):
        self.provider_factory = provider_factory or create_remote_provider

    def local_state(self, root: Path | None) -> FrameworkTargetState:
        raw = detect_framework_state(root)
        return FrameworkTargetState(
            configured=bool(raw.get("configured")),
            ue4ss_runtime=bool(raw.get("ue4ss_runtime")),
            rcon_mod=bool(raw.get("rcon_mod")),
            windrose_plus=bool(raw.get("windrose_plus")),
            windrose_plus_package=bool(raw.get("windrose_plus_package")),
        )

    def all_local_states(self, paths: AppPaths) -> dict[str, FrameworkTargetState]:
        return {
            "client": self.local_state(paths.client_root),
            "server": self.local_state(paths.server_root),
            "dedicated_server": self.local_state(paths.dedicated_server_root),
        }

    def remote_state(self, profile: RemoteProfile) -> FrameworkTargetState:
        root = profile.normalized_root_dir()
        if not root:
            return FrameworkTargetState(configured=False, checked=False, warning="Server Folder is not configured.")

        provider: RemoteProvider | None = None
        try:
            provider = self.provider_factory(profile)
            paths = remote_framework_paths(root)
            runtime = provider.path_exists(paths["ue4ss_runtime_marker"]) or provider.path_exists(paths["ue4ss_runtime_folder"])
            windrose_plus = provider.path_exists(paths["windrose_plus"])
            windrose_plus_package = windrose_plus or provider.path_exists(paths["windrose_plus_package"])
            return FrameworkTargetState(
                configured=True,
                ue4ss_runtime=runtime,
                rcon_mod=provider.path_exists(paths["rcon_mod"]),
                windrose_plus=windrose_plus,
                windrose_plus_package=windrose_plus_package,
            )
        except Exception as exc:
            return FrameworkTargetState(
                configured=True,
                checked=False,
                warning=str(exc) or exc.__class__.__name__,
            )
        finally:
            if provider is not None:
                provider.close()
