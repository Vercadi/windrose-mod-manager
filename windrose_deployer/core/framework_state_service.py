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
    ue4ss_partial: bool = False
    rcon_mod: bool = False
    rcon_configured: bool = False
    rcon_missing_password: bool = False
    windrose_plus: bool = False
    windrose_plus_package: bool = False
    windrose_plus_generated_paks: bool = False
    windrose_plus_install_script: bool = False
    windrose_plus_launch_wrapper: bool = False
    windrose_plus_dashboard_launcher: bool = False
    windrose_plus_config: bool = False
    windrose_plus_partial: bool = False
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
            bits.append("UE4SS partial" if self.ue4ss_partial else "UE4SS")
        if self.rcon_mod:
            bits.append("RCON missing password" if self.rcon_missing_password else "RCON")
        if self.windrose_plus:
            if self.windrose_plus_partial:
                bits.append("WindrosePlus partial")
            elif self.windrose_plus_generated_paks:
                bits.append("WindrosePlus + generated PAK")
            else:
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
            ue4ss_partial=bool(raw.get("ue4ss_partial")),
            rcon_mod=bool(raw.get("rcon_mod")),
            rcon_configured=bool(raw.get("rcon_configured")),
            rcon_missing_password=bool(raw.get("rcon_missing_password")),
            windrose_plus=bool(raw.get("windrose_plus")),
            windrose_plus_package=bool(raw.get("windrose_plus_package")),
            windrose_plus_generated_paks=bool(raw.get("windrose_plus_generated_paks")),
            windrose_plus_install_script=bool(raw.get("windrose_plus_install_script")),
            windrose_plus_launch_wrapper=bool(raw.get("windrose_plus_launch_wrapper")),
            windrose_plus_dashboard_launcher=bool(raw.get("windrose_plus_dashboard_launcher")),
            windrose_plus_config=bool(raw.get("windrose_plus_config")),
            windrose_plus_partial=bool(raw.get("windrose_plus_partial")),
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
            runtime_injector_present = any(
                provider.path_exists(paths[key])
                for key in ("ue4ss_runtime_dwmapi", "ue4ss_runtime_dwmappi", "ue4ss_runtime_xinput")
            )
            runtime_core_present = any(
                provider.path_exists(paths[key])
                for key in ("ue4ss_runtime_dll", "ue4ss_runtime_settings", "ue4ss_runtime_folder_dll", "ue4ss_runtime_folder_settings")
            )
            runtime = runtime_injector_present or runtime_core_present
            ue4ss_mods_present = _remote_dir_has_files(provider, paths["ue4ss_mods"])
            windrose_plus = provider.path_exists(paths["windrose_plus"])
            windrose_plus_package = (
                windrose_plus
                or provider.path_exists(paths["windrose_plus_package"])
                or provider.path_exists(paths["windrose_plus_package_folder"])
            )
            windrose_plus_generated_paks = (
                provider.path_exists(paths["windrose_plus_generated_multipliers"])
                or provider.path_exists(paths["windrose_plus_generated_curvetables"])
                or provider.path_exists(paths["windrose_plus_generated_multipliers_mods"])
                or provider.path_exists(paths["windrose_plus_generated_curvetables_mods"])
            )
            windrose_plus_launch_wrapper = provider.path_exists(paths["windrose_plus_launch_wrapper"])
            windrose_plus_dashboard_launcher = provider.path_exists(paths["windrose_plus_dashboard_launcher"])
            windrose_plus_config = provider.path_exists(paths["windrose_plus_config"])
            windrose_plus_any = any(
                [
                    windrose_plus,
                    windrose_plus_package,
                    windrose_plus_generated_paks,
                    windrose_plus_launch_wrapper,
                    windrose_plus_dashboard_launcher,
                    windrose_plus_config,
                ]
            )
            rcon_installed = (
                provider.path_exists(paths["rcon_dll"])
                or _remote_dir_has_files(provider, paths["rcon_config_dir"])
                or _remote_dir_has_files(provider, paths["rcon_legacy_mod"])
            )
            return FrameworkTargetState(
                configured=True,
                ue4ss_runtime=runtime,
                ue4ss_partial=(runtime and not (runtime_injector_present and runtime_core_present)) or (ue4ss_mods_present and not runtime),
                rcon_mod=rcon_installed,
                rcon_configured=provider.path_exists(paths["rcon_settings"]) or provider.path_exists(paths["rcon_legacy_settings"]),
                rcon_missing_password=False,
                windrose_plus=windrose_plus,
                windrose_plus_package=windrose_plus_package,
                windrose_plus_generated_paks=windrose_plus_generated_paks,
                windrose_plus_launch_wrapper=windrose_plus_launch_wrapper,
                windrose_plus_dashboard_launcher=windrose_plus_dashboard_launcher,
                windrose_plus_config=windrose_plus_config,
                windrose_plus_partial=windrose_plus_any and not (windrose_plus and windrose_plus_launch_wrapper),
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


def _remote_dir_has_files(provider: RemoteProvider, remote_dir: str) -> bool:
    try:
        for entry in provider.list_entries(remote_dir):
            if not entry.is_dir:
                return True
            if _remote_dir_has_files(provider, entry.path):
                return True
    except Exception:
        return False
    return False
