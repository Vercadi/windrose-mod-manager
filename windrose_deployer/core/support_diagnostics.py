"""Redacted support report generation."""
from __future__ import annotations

import os
import platform
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

from .. import __app_name__, __version__
from ..models.app_paths import AppPaths
from ..models.deployment_record import DeploymentRecord
from ..models.mod_install import ModInstall, target_value_label
from ..models.remote_profile import RemoteProfile, normalize_remote_protocol
from .framework_state_service import FrameworkStateService, FrameworkTargetState
from .manifest_store import ManifestStore
from .remote_profile_store import RemoteProfileStore


SENSITIVE_FIELD_PATTERN = re.compile(
    r"(?i)\b(password|pass|token|api[_-]?key|private[_-]?key|secret)\b\s*[:=]\s*([^\r\n|]+)"
)


def redact_sensitive_text(text: str, *, secrets: Iterable[str] = ()) -> str:
    """Redact common secret fields and local Windows usernames from text."""
    redacted = str(text or "")
    for secret in secrets:
        if secret:
            redacted = redacted.replace(str(secret), "<redacted>")
    redacted = SENSITIVE_FIELD_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)
    redacted = _redact_windows_user_paths(redacted)
    username = os.environ.get("USERNAME") or os.environ.get("USER")
    if username:
        redacted = re.sub(
            rf"(?i)([A-Z]:\\Users\\){re.escape(username)}(?=\\)",
            r"\1<user>",
            redacted,
        )
    return redacted


def redact_path(path: Path | str | None) -> str:
    if path is None:
        return "Not configured"
    value = str(path)
    if not value:
        return "Not configured"
    return redact_sensitive_text(value)


def _redact_windows_user_paths(text: str) -> str:
    redacted = re.sub(r"(?i)([A-Z]:\\Users\\)[^\\\r\n|]+", r"\1<user>", text)
    return re.sub(r"(?i)([A-Z]:/Users/)[^/\r\n|]+", r"\1<user>", redacted)


class SupportDiagnosticsService:
    """Build one copy/paste-friendly report for user support."""

    def build_report(
        self,
        *,
        paths: AppPaths,
        manifest: ManifestStore,
        remote_profiles: RemoteProfileStore,
        framework_state: FrameworkStateService,
        data_dir: Path,
        backup_root: Path,
        last_hosted_diagnostics: str = "",
        last_install_plan: str = "",
        log_tail_lines: int = 80,
        history_limit: int = 20,
    ) -> str:
        mods = manifest.list_mods()
        history = manifest.list_history()
        profiles = remote_profiles.list_profiles()
        secrets = self._profile_secrets(profiles)
        sections = [
            self._header(),
            self._target_summary(paths),
            self._hosted_summary(profiles),
            self._manifest_summary(mods, history),
            self._layout_metadata_summary(mods, history),
            self._framework_summary(paths, framework_state),
            self._activity_summary(history[-history_limit:]),
            self._install_plan_diagnostics(last_install_plan),
            self._hosted_diagnostics(last_hosted_diagnostics),
            self._log_tail(data_dir / "deployer.log", log_tail_lines),
            self._storage_summary(data_dir, backup_root),
        ]
        return redact_sensitive_text("\n\n".join(section for section in sections if section), secrets=secrets)

    @staticmethod
    def _profile_secrets(profiles: list[RemoteProfile]) -> list[str]:
        secrets: list[str] = []
        for profile in profiles:
            if profile.password:
                secrets.append(profile.password)
            if profile.private_key_path:
                secrets.append(profile.private_key_path)
        return secrets

    @staticmethod
    def _header() -> str:
        frozen = bool(getattr(sys, "frozen", False))
        return "\n".join(
            [
                "Windrose Mod Manager diagnostics",
                f"App: {__app_name__} v{__version__}",
                f"Build: {'frozen exe' if frozen else 'source/dev'}",
                f"Python: {platform.python_version()}",
                f"OS: {platform.platform()}",
            ]
        )

    @staticmethod
    def _target_summary(paths: AppPaths) -> str:
        rows = ["Targets:"]
        targets = [
            ("Client", paths.client_root),
            ("Local Server", paths.server_root),
            ("Dedicated Server", paths.dedicated_server_root),
            ("Client Mods", paths.client_mods),
            ("Local Server Mods", paths.server_mods),
            ("Dedicated Server Mods", paths.dedicated_server_mods),
        ]
        for label, path in targets:
            configured = "configured" if path else "missing"
            exists = "exists" if path and Path(path).exists() else "not found"
            rows.append(f"- {label}: {configured}; {exists}; {redact_path(path)}")
        return "\n".join(rows)

    @staticmethod
    def _hosted_summary(profiles: list[RemoteProfile]) -> str:
        rows = [f"Hosted profiles: {len(profiles)}"]
        for profile in profiles:
            normalized = profile.normalized_for_connection()
            protocol = normalize_remote_protocol(normalized.protocol).upper()
            rows.append(
                f"- {normalized.name}: {protocol} {normalized.host or '(host not set)'}:{normalized.port} "
                f"as {normalized.username or '(username not set)'}"
            )
            if normalized.remote_root_dir:
                rows.append(f"  Server Folder: {normalized.remote_root_dir}")
            if normalized.remote_mods_dir:
                rows.append(f"  Mods Override: {normalized.remote_mods_dir}")
            if normalized.remote_server_description_path:
                rows.append(f"  Server Settings Override: {normalized.remote_server_description_path}")
            if normalized.remote_save_root:
                rows.append(f"  World Saves Override: {normalized.remote_save_root}")
            if normalized.ue4ss_managed_externally:
                rows.append("  UE4SS: managed by host/provider")
        return "\n".join(rows)

    @staticmethod
    def _manifest_summary(mods: list[ModInstall], history: list[DeploymentRecord]) -> str:
        target_counts: Counter[str] = Counter()
        kind_counts: Counter[str] = Counter()
        for mod in mods:
            kind_counts[mod.install_kind or "standard_mod"] += 1
            for target in mod.targets or ["hosted"]:
                target_counts[target_value_label(target)] += 1
        rows = [
            "Manifest:",
            f"- Active installs: {sum(1 for mod in mods if mod.enabled)} / {len(mods)}",
            f"- History records: {len(history)}",
            "- Targets: " + (", ".join(f"{key}={value}" for key, value in sorted(target_counts.items())) or "none"),
            "- Install kinds: " + (", ".join(f"{key}={value}" for key, value in sorted(kind_counts.items())) or "none"),
        ]
        return "\n".join(rows)

    @staticmethod
    def _layout_metadata_summary(mods: list[ModInstall], history: list[DeploymentRecord]) -> str:
        layout_counts: Counter[str] = Counter()
        for mod in mods:
            if mod.layout_kind:
                layout_counts[mod.layout_kind] += 1
        for record in history:
            if record.layout_kind and not any(mod.mod_id == record.mod_id for mod in mods):
                layout_counts[record.layout_kind] += 1

        latest_record = next(
            (
                record
                for record in reversed(history)
                if record.layout_kind or record.selected_entries or record.installed_archive_entries or record.layout_warnings
            ),
            None,
        )
        latest_mod = next(
            (
                mod
                for mod in sorted(mods, key=lambda item: item.install_time or "", reverse=True)
                if mod.layout_kind or mod.selected_entries or mod.installed_archive_entries or mod.layout_warnings
            ),
            None,
        )

        rows = ["Layout metadata:"]
        rows.append(
            "- Layouts: "
            + (", ".join(f"{key}={value}" for key, value in sorted(layout_counts.items())) or "none recorded")
        )
        if latest_record is not None:
            rows.extend(SupportDiagnosticsService._layout_metadata_rows(
                label="Latest history",
                name=latest_record.display_name or latest_record.mod_id,
                layout_kind=latest_record.layout_kind,
                target_root_hint=latest_record.target_root_hint,
                selected_variant=latest_record.selected_variant,
                selected_entries=latest_record.selected_entries,
                installed_archive_entries=latest_record.installed_archive_entries,
                layout_warnings=latest_record.layout_warnings,
            ))
        elif latest_mod is not None:
            rows.extend(SupportDiagnosticsService._layout_metadata_rows(
                label="Latest install",
                name=latest_mod.display_name or latest_mod.mod_id,
                layout_kind=latest_mod.layout_kind,
                target_root_hint=latest_mod.target_root_hint,
                selected_variant=latest_mod.selected_variant,
                selected_entries=latest_mod.selected_entries,
                installed_archive_entries=latest_mod.installed_archive_entries,
                layout_warnings=latest_mod.layout_warnings,
            ))
        else:
            rows.append("- Latest: none recorded")
        return "\n".join(rows)

    @staticmethod
    def _layout_metadata_rows(
        *,
        label: str,
        name: str,
        layout_kind: str,
        target_root_hint: str,
        selected_variant: str | None,
        selected_entries: list[str],
        installed_archive_entries: list[str],
        layout_warnings: list[str],
    ) -> list[str]:
        parts = [name or "(unknown)"]
        if layout_kind:
            parts.append(layout_kind)
        if target_root_hint:
            parts.append(f"target hint: {target_root_hint}")
        if selected_variant:
            parts.append(f"variant: {selected_variant}")
        parts.append(f"selected entries: {len(selected_entries or [])}")
        parts.append(f"installed archive entries: {len(installed_archive_entries or [])}")
        rows = [f"- {label}: " + " | ".join(parts)]
        if selected_entries:
            rows.append("- Selected: " + ", ".join(selected_entries[:6]) + (" ..." if len(selected_entries) > 6 else ""))
        if installed_archive_entries:
            rows.append(
                "- Installed archive entries: "
                + ", ".join(installed_archive_entries[:8])
                + (" ..." if len(installed_archive_entries) > 8 else "")
            )
        if layout_warnings:
            rows.append("- Layout notes: " + "; ".join(layout_warnings[:4]) + (" ..." if len(layout_warnings) > 4 else ""))
        return rows

    @staticmethod
    def _framework_summary(paths: AppPaths, service: FrameworkStateService) -> str:
        states = service.all_local_states(paths)
        labels = {
            "client": "Client",
            "server": "Local Server",
            "dedicated_server": "Dedicated Server",
        }
        rows = ["Frameworks:"]
        for key, state in states.items():
            rows.append(f"- {labels.get(key, key)}: {SupportDiagnosticsService._state_summary(state)}")
        return "\n".join(rows)

    @staticmethod
    def _state_summary(state: FrameworkTargetState) -> str:
        if not state.configured:
            return "not configured"
        parts = []
        if state.ue4ss_external:
            parts.append("UE4SS external")
        elif state.ue4ss_runtime:
            parts.append("UE4SS partial" if state.ue4ss_partial else "UE4SS")
        elif state.ue4ss_partial:
            parts.append("UE4SS runtime missing")
        if state.rcon_mod:
            if not state.rcon_configured:
                parts.append("RCON installed, settings pending")
            elif state.rcon_missing_password:
                parts.append("RCON password review")
            else:
                parts.append("RCON configured")
        if state.windrose_plus:
            parts.append("WindrosePlus active")
        elif state.windrose_plus_package:
            parts.append("WindrosePlus files present")
        if state.windrose_plus_generated_paks:
            parts.append("WindrosePlus generated PAKs")
        if state.windrose_plus_partial:
            parts.append("WindrosePlus review")
        return "; ".join(parts) if parts else "missing"

    @staticmethod
    def _activity_summary(history: list[DeploymentRecord]) -> str:
        rows = [f"Recent activity: {len(history)} shown"]
        for record in history:
            name = record.display_name or record.mod_id or "(unknown)"
            target = target_value_label(record.target)
            rows.append(f"- {record.timestamp} | {record.action} | {target} | {name}")
        return "\n".join(rows)

    @staticmethod
    def _hosted_diagnostics(last_hosted_diagnostics: str) -> str:
        if not last_hosted_diagnostics.strip():
            return "Last hosted connection diagnostics: none"
        return "Last hosted connection diagnostics:\n" + last_hosted_diagnostics.strip()

    @staticmethod
    def _install_plan_diagnostics(last_install_plan: str) -> str:
        if not last_install_plan.strip():
            return "Last install review: none"
        return "Last install review:\n" + last_install_plan.strip()

    @staticmethod
    def _log_tail(log_path: Path, line_count: int) -> str:
        if not log_path.is_file():
            return "Recent log tail: log file not found"
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return f"Recent log tail: could not read log ({exc})"
        tail = lines[-line_count:]
        return "Recent log tail:\n" + "\n".join(tail)

    @staticmethod
    def _storage_summary(data_dir: Path, backup_root: Path) -> str:
        return "\n".join(
            [
                "Storage:",
                f"- Data dir: {redact_path(data_dir)}",
                f"- Backup root: {redact_path(backup_root)}",
            ]
        )
