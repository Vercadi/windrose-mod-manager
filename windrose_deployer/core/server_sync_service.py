"""Compare managed client mods against local or hosted server state."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.mod_install import ModInstall


@dataclass
class SyncItem:
    name: str
    status: str
    client_summary: str = ""
    server_summary: str = ""
    details: str = ""


@dataclass
class SyncReport:
    items: list[SyncItem] = field(default_factory=list)

    @property
    def matched(self) -> int:
        return sum(1 for item in self.items if item.status == "matched")

    @property
    def review_needed(self) -> int:
        return sum(1 for item in self.items if item.status != "matched")

    @property
    def summary(self) -> str:
        if not self.items:
            return "No managed mods available for comparison."
        return f"{self.matched} matched, {self.review_needed} need review"


class ServerSyncService:
    """Produce user-facing parity reports for client/server mod state."""

    def compare_local(self, mods: list[ModInstall], *, target: str = "server") -> SyncReport:
        client_groups = self._mods_by_name(mods, target="client")
        server_groups = self._mods_by_name(mods, target=target)
        return self._compare_mod_groups(client_groups, server_groups, target=target)

    def compare_hosted(self, mods: list[ModInstall], remote_files: list[str]) -> SyncReport:
        client_mods = self._mods_for_target(mods, target="client")
        remote_names = {Path(path).name for path in remote_files}
        expected_names: set[str] = set()
        items: list[SyncItem] = []

        for mod in client_mods:
            expected = self._expected_server_file_names(mod)
            expected_names.update(expected)
            found = expected.intersection(remote_names)
            if expected and expected.issubset(remote_names):
                status = "matched"
                details = "All expected mod files are present on the hosted server."
            elif found:
                status = "version_mismatch"
                details = "Some expected files are present, but the hosted server is missing others."
            else:
                status = "missing_on_server"
                details = "Expected hosted files were not found on the server."
            items.append(
                SyncItem(
                    name=mod.display_name,
                    status=status,
                    client_summary=", ".join(sorted(expected)) or mod.display_name,
                    server_summary=", ".join(sorted(found)) if found else "Not present",
                    details=details,
                )
            )

        for remote_name in sorted(remote_names - expected_names):
            items.append(
                SyncItem(
                    name=remote_name,
                    status="unknown_manual_server_files",
                    client_summary="Not managed by the client manifest",
                    server_summary=remote_name,
                    details="This file exists on the hosted server but is not matched to a managed client mod.",
                )
            )

        return SyncReport(items=items)

    def _compare_mod_groups(
        self,
        client_groups: dict[str, list[ModInstall]],
        server_groups: dict[str, list[ModInstall]],
        *,
        target: str,
    ) -> SyncReport:
        items: list[SyncItem] = []
        target_label = self._target_label(target)
        for key in sorted(set(client_groups) | set(server_groups)):
            client_bucket = list(client_groups.get(key, []))
            remaining_servers = list(server_groups.get(key, []))

            unmatched_clients: list[ModInstall] = []
            for client in client_bucket:
                match_index = next(
                    (
                        index
                        for index, server in enumerate(remaining_servers)
                        if self._same_mod_revision(client, server)
                    ),
                    None,
                )
                if match_index is None:
                    unmatched_clients.append(client)
                    continue
                server = remaining_servers.pop(match_index)
                items.append(
                    SyncItem(
                        name=client.display_name,
                        status="matched",
                        client_summary=self._mod_summary(client),
                        server_summary=self._mod_summary(server),
                        details=f"Managed client and {target_label.lower()} installs are aligned.",
                    )
                )

            pairs = min(len(unmatched_clients), len(remaining_servers))
            for index in range(pairs):
                client = unmatched_clients[index]
                server = remaining_servers[index]
                items.append(
                    SyncItem(
                        name=client.display_name,
                        status="version_mismatch",
                        client_summary=self._mod_summary(client),
                        server_summary=self._mod_summary(server),
                        details=f"Client and {target_label.lower()} installs use different archive revisions or variants.",
                    )
                )

            for client in unmatched_clients[pairs:]:
                items.append(
                    SyncItem(
                        name=client.display_name,
                        status="missing_on_server",
                        client_summary=self._mod_summary(client),
                        server_summary="Not installed",
                        details=f"Installed for the client but missing from the {target_label.lower()} target.",
                    )
                )
            for server in remaining_servers[pairs:]:
                items.append(
                    SyncItem(
                        name=server.display_name,
                        status="missing_on_client",
                        client_summary="Not installed",
                        server_summary=self._mod_summary(server),
                        details=f"Installed for the {target_label.lower()} target but missing from the client target.",
                    )
                )
        return SyncReport(items=items)

    @staticmethod
    def _mods_for_target(mods: list[ModInstall], *, target: str) -> list[ModInstall]:
        filtered: list[ModInstall] = []
        for mod in mods:
            if not mod.enabled:
                continue
            targets = ServerSyncService._expanded_targets(mod)
            if target not in targets:
                continue
            filtered.append(mod)
        return sorted(filtered, key=ServerSyncService._sort_key)

    @classmethod
    def _mods_by_name(cls, mods: list[ModInstall], *, target: str) -> dict[str, list[ModInstall]]:
        grouped: dict[str, list[ModInstall]] = {}
        for mod in cls._mods_for_target(mods, target=target):
            grouped.setdefault(mod.display_name.strip().lower(), []).append(mod)
        return grouped

    @staticmethod
    def _sort_key(mod: ModInstall) -> tuple:
        archive_name = Path(mod.source_archive).name.lower() if mod.source_archive else ""
        return (
            mod.display_name.strip().lower(),
            mod.selected_variant or "",
            archive_name,
            mod.archive_hash or "",
            mod.install_time or "",
            mod.mod_id,
        )

    @staticmethod
    def _same_mod_revision(client: ModInstall, server: ModInstall) -> bool:
        if client.archive_hash and server.archive_hash:
            if client.archive_hash != server.archive_hash:
                return False
        if client.selected_variant != server.selected_variant:
            return False
        client_archive = Path(client.source_archive).name.lower() if client.source_archive else ""
        server_archive = Path(server.source_archive).name.lower() if server.source_archive else ""
        if client_archive and server_archive and client_archive != server_archive:
            return False
        return True

    @staticmethod
    def _mod_summary(mod: ModInstall) -> str:
        variant = f" ({mod.selected_variant})" if mod.selected_variant else ""
        return f"{Path(mod.source_archive).name}{variant}" if mod.source_archive else f"{mod.display_name}{variant}"

    @staticmethod
    def _expected_server_file_names(mod: ModInstall) -> set[str]:
        expected: set[str] = set()
        for file_path in mod.installed_files:
            name = Path(file_path).name
            if name.endswith(".disabled"):
                name = name[: -len(".disabled")]
            expected.add(name)
        return expected

    @staticmethod
    def _expanded_targets(mod: ModInstall) -> set[str]:
        targets = set(mod.targets)
        if "both" in targets:
            targets.update({"client", "server"})
        return targets

    @staticmethod
    def _target_label(target: str) -> str:
        labels = {
            "server": "bundled server",
            "dedicated_server": "dedicated server",
            "hosted": "hosted server",
        }
        return labels.get(target, target.replace("_", " "))
