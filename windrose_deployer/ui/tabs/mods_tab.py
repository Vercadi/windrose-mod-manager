"""Mods screen with active and inactive mod state in one workspace."""
from __future__ import annotations

from collections import defaultdict
import logging
import os
import re
import shutil
import threading
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.archive_handler import SUPPORTED_EXTENSIONS
from ...core.archive_library_service import manager_owned_archive_path
from ...core.archive_inspector import inspect_archive
from ...core.conflict_detector import check_plan_conflicts
from ...core.deployment_planner import plan_deployment
from ...core.framework_deployment_planner import is_server_only_framework_install_kind
from ...core.framework_detector import detect_framework_state
from ...core.live_mod_inventory import (
    LiveModsFolderSnapshot,
    bundle_live_file_names,
    snapshot_live_mods_folder,
)
from ...core.pak_bundle_importer import import_pak_bundles, is_pak_bundle_file
from ...core.version_hints import possible_update_hint_for_archive
from ...models.archive_info import ArchiveInfo
from ...models.deployment_record import DeployedFile, DeploymentRecord
from ...models.metadata import ModMetadata
from ...models.mod_install import (
    InstallTarget,
    ModInstall,
    expand_target_values,
    install_target_label,
    summarize_target_values,
)
from ...utils.filesystem import safe_delete
from ...utils.json_io import read_json, write_json
from ...utils.naming import generate_mod_id

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)

_FILETYPES = [
    ("Mod files", "*.zip *.7z *.rar *.pak *.utoc *.ucas"),
    ("Archives", "*.zip *.7z *.rar"),
    ("Pak / IoStore files", "*.pak *.utoc *.ucas"),
    ("Zip archives", "*.zip"),
    ("7-Zip archives", "*.7z"),
    ("RAR archives", "*.rar"),
    ("All files", "*.*"),
]

_SCOPE_LABELS = {
    "All": "all",
    "Client": "client",
    "Local Server": "server",
    "Dedicated Server": "dedicated_server",
    "Hosted Server": "hosted",
}

_FILTER_LABELS = {
    "Inactive Mods": "available",
    "Active Mods": "installed",
    "All Known Mods": "all",
    "Client": "client",
    "Local Server": "server",
    "Dedicated Server": "dedicated",
    "Client + Local Server": "client_local",
    "Missing Source": "missing archive",
}

_FILTER_VALUE_ALIASES = {
    **_FILTER_LABELS,
    "Available Archives": "available",
    "Applied Sources": "installed",
    "All Tracked Archives": "all",
    "Missing Archive": "missing archive",
}

_INSTALL_PRESETS = [
    ("client", "Client only", "Install to the Windrose client files on this PC."),
    ("client_local", "Client + Local Server", "Install to the client and the main Windrose install's local server files."),
    ("client_dedicated", "Client + Dedicated Server", "Install to the client and the standalone Windrose Dedicated Server install."),
    ("local", "Local Server only", "Install only to the main Windrose install's local server files."),
    ("dedicated", "Dedicated Server only", "Install only to the standalone Windrose Dedicated Server install."),
    ("hosted", "Hosted Server only", "Open the hosted upload flow for the currently selected hosted profile."),
]


class ModsTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._current_info: Optional[ArchiveInfo] = None
        self._library: list[dict] = []
        self._library_widgets: list[ctk.CTkFrame] = []
        self._library_row_frames: dict[str, ctk.CTkFrame] = {}
        self._applied_widgets: list[object] = []
        self._selected_library_path: Optional[str] = None
        self._selected_archive_paths: set[str] = set()
        self._selected_mod_ids: set[str] = set()
        self._selected_live_files: set[str] = set()
        self._archive_info_cache: dict[str, tuple[int, int, ArchiveInfo]] = {}
        self._live_file_bundle_members: dict[str, list[Path | str]] = {}
        self._live_file_bundle_meta: dict[str, dict[str, str]] = {}
        self._pending_click_path: Optional[Path] = None
        self._single_click_job = None
        self._hosted_inventory_request = 0
        self._details_visible = False
        self._expanded_archive_paths: set[str] = set()
        self._expanded_mod_ids: set[str] = set()
        self._archive_component_selections: dict[str, set[str]] = {}
        self._mod_component_selections: dict[str, set[str]] = {}

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_args: self._refresh_library_ui(refresh_applied=False))
        self._filter_var = ctk.StringVar(value="Inactive Mods")
        self._scope_var = ctk.StringVar(value="all")
        self._variant_var = ctk.StringVar(value="(none)")
        self._mod_name_var = ctk.StringVar()
        self._action_buttons: list[ctk.CTkButton] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_workspace()
        self._load_library()
        self._register_dnd()

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(bar, text="Mods", font=self.app.ui_font("title")).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )

        self._scope_switch = ctk.CTkSegmentedButton(
            bar,
            values=list(_SCOPE_LABELS.keys()),
            command=lambda value: self._on_scope_changed(value),
        )
        self._scope_switch.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self._scope_switch.set("All")

        self._summary_label = ctk.CTkLabel(bar, text="", anchor="w", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._summary_label.grid(row=0, column=2, sticky="ew", padx=(0, 12))
        self._details_toggle_btn = ctk.CTkButton(
            bar,
            text="Show Details",
            width=108,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._toggle_details_panel,
        )
        self._details_toggle_btn.grid(row=0, column=3, sticky="e")
        self._action_buttons.append(self._details_toggle_btn)
        self._result_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            justify="left",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._result_label.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

    def _build_workspace(self) -> None:
        self._panes = tk.PanedWindow(
            self,
            orient=tk.VERTICAL,
            sashwidth=8,
            showhandle=True,
            handlesize=8,
            bd=0,
            relief=tk.FLAT,
            bg="#2b2b2b",
            sashrelief=tk.RAISED,
        )
        self._panes.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self._top_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        self._details_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        self._panes.add(self._top_host, minsize=340, height=520, stretch="always")

        self._lists_panes = tk.PanedWindow(
            self._top_host,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            showhandle=True,
            handlesize=8,
            bd=0,
            relief=tk.FLAT,
            bg="#2b2b2b",
            sashrelief=tk.RAISED,
        )
        self._lists_panes.pack(fill="both", expand=True)

        left_host = ctk.CTkFrame(self._lists_panes, fg_color="transparent")
        right_host = ctk.CTkFrame(self._lists_panes, fg_color="transparent")
        self._lists_panes.add(left_host, minsize=400, width=470)
        self._lists_panes.add(right_host, minsize=260, width=320)

        self._build_applied_panel(left_host)
        self._build_archive_panel(right_host)
        self._build_details_panel(self._details_host)

    def _build_applied_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Active Mods", font=self.app.ui_font("section_title")).grid(
            row=0, column=0, sticky="w"
        )
        self._applied_summary_label = ctk.CTkLabel(header, text="", anchor="e", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._applied_summary_label.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self._selected_mods_label = ctk.CTkLabel(header, text="", anchor="e", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._selected_mods_label.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self._uninstall_selected_btn = ctk.CTkButton(
            header,
            text="Uninstall Selected",
            width=138,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            state="disabled",
            command=self._on_uninstall_selected_mods,
        )
        self._uninstall_selected_btn.grid(row=0, column=3, sticky="e", padx=(0, 6))
        self._action_buttons.append(self._uninstall_selected_btn)
        self._clear_mod_selection_btn = ctk.CTkButton(
            header,
            text="Clear",
            width=64,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            state="disabled",
            command=self._clear_selected_mods,
        )
        self._clear_mod_selection_btn.grid(row=0, column=4, sticky="e")
        self._action_buttons.append(self._clear_mod_selection_btn)

        self._applied_list = ctk.CTkScrollableFrame(panel)
        self._applied_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._applied_list.grid_columnconfigure(0, weight=1)

    def _build_archive_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent, border_width=1, border_color="#3b3b3b")
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)
        self._archive_panel = panel

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Inactive Mods", font=self.app.ui_font("section_title")).grid(
            row=0, column=0, sticky="w"
        )
        add_btn = ctk.CTkButton(
            header, text="Add", width=64, fg_color="#2980b9", hover_color="#2471a3", command=self.import_archives,
            height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body")
        )
        add_btn.grid(row=0, column=1, sticky="e", padx=(8, 6))
        self._action_buttons.append(add_btn)
        self._filter_menu = ctk.CTkOptionMenu(
            header,
            variable=self._filter_var,
            values=list(_FILTER_LABELS.keys()),
            width=152,
            command=lambda _value: self._refresh_library_ui(refresh_applied=False),
            font=self.app.ui_font("body"),
        )
        self._filter_menu.grid(row=0, column=2, sticky="e", padx=(0, 6))
        refresh_btn = ctk.CTkButton(
            header, text="Refresh", width=72, fg_color="#555555", hover_color="#666666", command=self.refresh_view,
            height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body")
        )
        refresh_btn.grid(row=0, column=3, sticky="e")
        self._action_buttons.append(refresh_btn)

        self._search_entry = ctk.CTkEntry(
            header, textvariable=self._search_var, placeholder_text="Search inactive mods...", width=150, font=self.app.ui_font("body")
        )
        self._search_entry.grid(row=1, column=0, sticky="ew", pady=(6, 0), padx=(0, 6))
        self._selected_archives_label = ctk.CTkLabel(header, text="", anchor="e", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._selected_archives_label.grid(row=1, column=1, sticky="e", pady=(6, 0), padx=(0, 6))
        self._install_selected_btn = ctk.CTkButton(
            header,
            text="Install",
            width=86,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            state="disabled",
            command=self._on_install_selected_archives,
        )
        self._install_selected_btn.grid(row=1, column=2, sticky="e", pady=(6, 0), padx=(0, 6))
        self._action_buttons.append(self._install_selected_btn)
        self._clear_archive_selection_btn = ctk.CTkButton(
            header,
            text="Clear",
            width=58,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            state="disabled",
            command=self._clear_selected_archives,
        )
        self._clear_archive_selection_btn.grid(row=1, column=3, sticky="e", pady=(6, 0))
        self._action_buttons.append(self._clear_archive_selection_btn)

        self._archive_hint_label = ctk.CTkLabel(
            panel,
            text="Double-click an inactive mod to choose a target. Right-click rows for more actions. Drop archives or pak files anywhere in this pane.",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._archive_hint_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        self._library_list = ctk.CTkScrollableFrame(panel)
        self._library_list.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._library_list.grid_columnconfigure(0, weight=1)

    def _build_details_panel(self, parent) -> None:
        panel = ctk.CTkScrollableFrame(parent)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)

        self._detail_header = ctk.CTkLabel(
            panel, text="Select a mod", font=self.app.ui_font("detail_title"), anchor="w"
        )
        self._detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 2))
        self._detail_meta = ctk.CTkLabel(panel, text="", anchor="w", justify="left", text_color="#95a5a6", font=self.app.ui_font("body"))
        self._detail_meta.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._detail_hint = ctk.CTkLabel(
            panel,
            text="Install actions and active mod management now live in row menus. Double-click an inactive mod to install quickly.",
            justify="left",
            wraplength=self.app.ui_tokens.detail_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._detail_hint.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        self._installed_box = self._add_text_section(panel, 3, "Active State", 78)
        self._review_box = self._add_text_section(panel, 4, "Review", 78)
        self._preview_box = self._add_text_section(panel, 5, "Contents", 120)

    def _add_text_section(self, parent, row: int, title: str, height: int) -> ctk.CTkTextbox:
        card = ctk.CTkFrame(parent)
        card.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        box = ctk.CTkTextbox(card, height=height, font=self.app.ui_font("mono_small"))
        box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        box.configure(state="disabled")
        return box

    def refresh_view(self) -> None:
        self._normalize_combined_local_server_installs()
        self._load_library()
        if self._selected_library_path and (
            Path(self._selected_library_path).is_file() or self._mods_for_archive(self._selected_library_path)
        ):
            self._load_archive(Path(self._selected_library_path), refresh_only=True)
        elif self._selected_library_path and not Path(self._selected_library_path).is_file():
            self._selected_library_path = None
            self._clear_details()

    def refresh_library(self) -> None:
        self.refresh_view()

    def import_archives(self) -> None:
        self._on_browse()

    def library_entries(self) -> list[dict]:
        return list(self._library)

    def selected_archive_path(self) -> Optional[str]:
        return self._selected_library_path

    def _mods_for_archive(self, archive_path_str: str) -> list[ModInstall]:
        return [mod for mod in self.app.manifest.list_mods() if mod.source_archive == archive_path_str]

    def _library_entry(self, archive_path_str: str) -> Optional[dict]:
        for entry in getattr(self, "_library", []):
            if str(entry.get("path", "")) == archive_path_str:
                return entry
        return None

    def _archive_metadata(self, archive_path_str: str) -> ModMetadata:
        entry = self._library_entry(archive_path_str)
        if entry is not None:
            return ModMetadata.from_dict(entry.get("metadata"))
        return ModMetadata()

    def _archive_update_hint(self, entry: dict) -> str:
        return possible_update_hint_for_archive(entry, self.app.manifest.list_mods())

    def _save_archive_metadata(self, archive_path_str: str, metadata: ModMetadata, *, sync_installs: bool = True) -> None:
        entry = self._library_entry(archive_path_str)
        if entry is None:
            return
        entry["metadata"] = metadata.to_dict()
        self._save_library()
        if sync_installs:
            changed = False
            for mod in self._mods_for_archive(archive_path_str):
                mod.metadata = metadata
                self.app.manifest.update_mod(mod)
                changed = True
            if changed:
                self.app.refresh_installed_tab()

    @staticmethod
    def _canonical_installed_path(path_str: str) -> Path:
        normalized = path_str[:-9] if path_str.endswith(".disabled") else path_str
        return Path(normalized)

    def _normalize_combined_local_server_installs(self) -> None:
        client_root = self.app.paths.client_root
        server_root = self.app.paths.server_root
        if not client_root or not server_root:
            return

        normalized_count = 0
        for mod in list(self.app.manifest.list_mods()):
            if self._effective_targets(mod) != {"client", "server"}:
                continue

            client_files: list[str] = []
            server_files: list[str] = []
            unknown_files: list[str] = []
            for file_path in mod.installed_files:
                canonical = self._canonical_installed_path(file_path)
                try:
                    canonical.relative_to(client_root)
                    client_files.append(file_path)
                    continue
                except ValueError:
                    pass
                try:
                    canonical.relative_to(server_root)
                    server_files.append(file_path)
                    continue
                except ValueError:
                    pass
                unknown_files.append(file_path)

            if unknown_files or not client_files or not server_files:
                continue

            def _backup_subset(paths: list[str]) -> tuple[list[str], dict[str, str]]:
                mapping = {key: value for key, value in mod.backup_map.items() if key in paths}
                backed_up = [value for value in mod.backed_up_files if value in mapping.values()]
                return backed_up, mapping

            client_backed_up, client_backup_map = _backup_subset(client_files)
            server_backed_up, server_backup_map = _backup_subset(server_files)

            client_mod = ModInstall(
                mod_id=generate_mod_id(),
                display_name=mod.display_name,
                source_archive=mod.source_archive,
                archive_hash=mod.archive_hash,
                install_type=mod.install_type,
                selected_variant=mod.selected_variant,
                targets=["client"],
                installed_files=client_files,
                backed_up_files=client_backed_up,
                backup_map=client_backup_map,
                install_time=mod.install_time,
                enabled=mod.enabled,
            )
            server_mod = ModInstall(
                mod_id=generate_mod_id(),
                display_name=mod.display_name,
                source_archive=mod.source_archive,
                archive_hash=mod.archive_hash,
                install_type=mod.install_type,
                selected_variant=mod.selected_variant,
                targets=["server"],
                installed_files=server_files,
                backed_up_files=server_backed_up,
                backup_map=server_backup_map,
                install_time=mod.install_time,
                enabled=mod.enabled,
            )
            self.app.manifest.remove_mod(mod.mod_id)
            self.app.manifest.add_mod(client_mod)
            self.app.manifest.add_mod(server_mod)
            normalized_count += 1

        if normalized_count:
            log.info("Normalized %s combined client/local installs into separate target records", normalized_count)

    @staticmethod
    def _effective_targets(mod: ModInstall) -> set[str]:
        return expand_target_values(mod.targets)

    def _archive_covers_target(self, archive_path_str: str, target: InstallTarget) -> bool:
        covered: set[str] = set()
        for mod in self._mods_for_archive(archive_path_str):
            covered.update(self._effective_targets(mod))
        if target == InstallTarget.CLIENT:
            return "client" in covered
        if target == InstallTarget.SERVER:
            return "server" in covered
        if target == InstallTarget.DEDICATED_SERVER:
            return "dedicated_server" in covered
        return {"client", "server"}.issubset(covered)

    def _archive_badge_text(self, archive_path_str: str) -> str:
        mods = self._mods_for_archive(archive_path_str)
        if not mods:
            return "   "
        covered: set[str] = set()
        for mod in mods:
            covered.update(self._effective_targets(mod))
        letters = "".join(
            letter for letter, key in (("C", "client"), ("S", "server"), ("D", "dedicated_server")) if key in covered
        )
        return f"{letters:<3}" if letters else f"{len(mods):>2} "

    def _installed_to_text(self, mods: list[ModInstall]) -> str:
        if not mods:
            return "Not active"
        labels = []
        for mod in mods:
            label = summarize_target_values(mod.targets)
            if mod.selected_variant:
                label += f" ({mod.selected_variant})"
            if not mod.enabled:
                label += " [disabled]"
            labels.append(label)
        return " | ".join(labels)

    def _last_action_text(self, archive_path_str: str) -> str:
        history = [record for record in self.app.manifest.list_history() if record.source_archive == archive_path_str]
        if not history:
            return "No actions yet"
        latest = max(history, key=lambda item: item.timestamp)
        return f"{latest.action.replace('_', ' ').title()} - {latest.timestamp[:19].replace('T', ' ')}"

    @staticmethod
    def _source_kind_label(entry: dict) -> str:
        if entry.get("source_kind") == "pak_bundle":
            return "Pak Files"
        return "Archive"

    @staticmethod
    def _install_kind_label(value: str | None) -> str:
        return {
            "ue4ss_runtime": "UE4SS Runtime",
            "ue4ss_mod": "UE4SS Mod",
            "rcon_mod": "RCON Mod",
            "windrose_plus": "WindrosePlus",
        }.get(value or "standard_mod", "")

    @staticmethod
    def _target_label(target: InstallTarget) -> str:
        return install_target_label(target)

    def _library_path(self) -> Path:
        from ..app_window import DEFAULT_DATA_DIR

        return DEFAULT_DATA_DIR / "archive_library.json"

    def _load_library(self) -> None:
        self._normalize_combined_local_server_installs()
        self._library = [
            self._normalize_library_entry(entry)
            for entry in read_json(self._library_path()).get("archives", [])
            if isinstance(entry, dict)
        ]
        self._refresh_library_ui()

    def _save_library(self) -> None:
        write_json(self._library_path(), {"archives": self._library})

    def _loose_import_dir(self) -> Path:
        return self._library_path().parent / "imports"

    def _archive_import_dir(self) -> Path:
        return self._library_path().parent / "archives"

    def _add_to_library(
        self,
        archive_path: Path,
        *,
        name: str | None = None,
        source_kind: str = "archive",
        original_files: list[str] | None = None,
        archive_hash: str | None = None,
        original_path: str | None = None,
        manager_owned: bool = False,
    ) -> None:
        archive_str = str(archive_path)
        for entry in self._library:
            if entry.get("path") == archive_str:
                changed = False
                for key, value in {
                    "archive_hash": archive_hash,
                    "original_path": original_path,
                    "manager_owned": manager_owned,
                }.items():
                    if value not in (None, "") and entry.get(key) != value:
                        entry[key] = value
                        changed = True
                if changed:
                    self._save_library()
                return
        self._library.append(
            self._normalize_library_entry(
                {
                    "path": archive_str,
                    "name": name or archive_path.stem,
                    "ext": archive_path.suffix.lower(),
                    "source_kind": source_kind,
                    "original_files": list(original_files or []),
                    "archive_hash": archive_hash or "",
                    "original_path": original_path or "",
                    "manager_owned": manager_owned,
                }
            )
        )
        self._save_library()

    def _manager_owned_archive(self, archive_path: Path) -> tuple[Path, str, bool]:
        return manager_owned_archive_path(archive_path, self._archive_import_dir(), self._library)

    def _import_source_paths(self, paths: list[Path]) -> tuple[list[Path], list[str]]:
        archive_paths: list[Path] = []
        pak_paths: list[Path] = []
        warnings: list[str] = []

        for path in paths:
            suffix = path.suffix.lower()
            if suffix in SUPPORTED_EXTENSIONS:
                archive_paths.append(path)
            elif is_pak_bundle_file(path):
                pak_paths.append(path)
            else:
                warnings.append(f"Skipped unsupported file: {path.name}")

        imported_paths: list[Path] = []
        for archive_path in archive_paths:
            managed_path, archive_hash, reused = self._manager_owned_archive(archive_path)
            self._add_to_library(
                managed_path,
                name=archive_path.stem,
                source_kind="archive",
                original_files=[str(archive_path)],
                archive_hash=archive_hash,
                original_path=str(archive_path),
                manager_owned=True,
            )
            imported_paths.append(managed_path)
            if reused:
                warnings.append(f"Reused existing library copy for {archive_path.name}.")

        bundle_result = import_pak_bundles(pak_paths, self._loose_import_dir())
        warnings.extend(bundle_result.warnings)
        for bundle in bundle_result.created_archives:
            self._add_to_library(
                bundle.archive_path,
                name=bundle.display_name,
                source_kind="pak_bundle",
                original_files=[str(path) for path in bundle.source_files],
            )
            imported_paths.append(bundle.archive_path)

        return imported_paths, warnings

    def _get_archive_info(self, archive_path: Path) -> ArchiveInfo:
        key = str(archive_path)
        stat = archive_path.stat()
        cached = self._archive_info_cache.get(key)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
        info = inspect_archive(archive_path)
        self._archive_info_cache[key] = (stat.st_mtime_ns, stat.st_size, info)
        return info

    def _update_library_entry(self, archive_path: Path, info: ArchiveInfo) -> bool:
        for entry in self._library:
            if entry.get("path") == str(archive_path):
                changed = False
                updates = {
                    "archive_type": info.archive_type.value.replace("_", " "),
                    "total_files": info.total_files,
                    "child_items": self._archive_child_names(info),
                    "content_category": info.content_category,
                    "install_kind": info.install_kind,
                    "framework_name": info.framework_name,
                    "dependency_warnings": list(info.dependency_warnings),
                    "likely_destinations": list(info.likely_destinations),
                }
                for key, value in updates.items():
                    if entry.get(key) != value:
                        entry[key] = value
                        changed = True
                if changed:
                    self._save_library()
                return changed
        return False

    @staticmethod
    def _normalize_library_entry(entry: dict) -> dict:
        metadata = ModMetadata.from_dict(entry.get("metadata")).to_dict()
        normalized = dict(entry)
        normalized.setdefault("name", Path(str(entry.get("path", ""))).stem)
        normalized.setdefault("ext", Path(str(entry.get("path", ""))).suffix.lower())
        normalized.setdefault("archive_type", "")
        normalized.setdefault("total_files", 0)
        normalized.setdefault("child_items", [])
        normalized.setdefault("source_kind", "archive")
        normalized.setdefault("original_files", [])
        normalized.setdefault("archive_hash", "")
        normalized.setdefault("original_path", "")
        normalized.setdefault("manager_owned", False)
        normalized.setdefault("content_category", "standard_mod")
        normalized.setdefault("install_kind", "standard_mod")
        normalized.setdefault("framework_name", "")
        normalized.setdefault("dependency_warnings", [])
        normalized.setdefault("likely_destinations", [])
        normalized["metadata"] = metadata
        return normalized

    @staticmethod
    def _set_textbox(widget: ctk.CTkTextbox, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _set_result(self, text: str, *, level: str = "info") -> None:
        colors = {
            "success": "#2d8a4e",
            "warning": "#e67e22",
            "error": "#c0392b",
            "info": "#95a5a6",
        }
        self._result_label.configure(text=text, text_color=colors.get(level, "#95a5a6"))

    def _update_selection_state(self) -> None:
        archive_count = len(self._selected_archive_paths)
        mod_count = len(self._selected_mod_ids) + len(self._selected_live_files)
        self._selected_archives_label.configure(
            text=f"{archive_count} selected" if archive_count else ""
        )
        self._selected_mods_label.configure(
            text=f"{mod_count} selected" if mod_count else ""
        )
        archive_state = "normal" if archive_count else "disabled"
        mod_state = "normal" if mod_count else "disabled"
        self._install_selected_btn.configure(state=archive_state)
        self._clear_archive_selection_btn.configure(state=archive_state)
        self._uninstall_selected_btn.configure(state=mod_state)
        self._clear_mod_selection_btn.configure(state=mod_state)

    def _toggle_archive_selection(self, archive_path_str: str, selected: bool) -> None:
        if selected:
            self._selected_archive_paths.add(archive_path_str)
        else:
            self._selected_archive_paths.discard(archive_path_str)
        self._update_selection_state()

    def _toggle_mod_selection(self, mod_id: str, selected: bool) -> None:
        if selected:
            self._selected_mod_ids.add(mod_id)
        else:
            self._selected_mod_ids.discard(mod_id)
        self._update_selection_state()

    def _toggle_live_file_selection(self, file_path: str, selected: bool) -> None:
        if selected:
            self._selected_live_files.add(file_path)
        else:
            self._selected_live_files.discard(file_path)
        self._update_selection_state()

    def _clear_selected_archives(self) -> None:
        if not self._selected_archive_paths:
            return
        self._selected_archive_paths.clear()
        self._refresh_library_ui(refresh_applied=False)

    def _clear_selected_mods(self) -> None:
        if not self._selected_mod_ids and not self._selected_live_files:
            return
        self._selected_mod_ids.clear()
        self._selected_live_files.clear()
        self._refresh_applied_ui()

    def apply_ui_preferences(self) -> None:
        tokens = self.app.ui_tokens
        self._summary_label.configure(font=self.app.ui_font("small"))
        self._result_label.configure(font=self.app.ui_font("small"), wraplength=tokens.detail_wrap)
        self._applied_summary_label.configure(font=self.app.ui_font("small"))
        self._selected_archives_label.configure(font=self.app.ui_font("small"))
        self._selected_mods_label.configure(font=self.app.ui_font("small"))
        self._archive_hint_label.configure(font=self.app.ui_font("small"), wraplength=tokens.panel_wrap)
        self._detail_meta.configure(font=self.app.ui_font("body"))
        self._detail_hint.configure(font=self.app.ui_font("small"), wraplength=tokens.detail_wrap)
        self._search_entry.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
        self._filter_menu.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height, width=156)
        self._scope_switch.configure(font=self.app.ui_font("body"), height=tokens.toolbar_button_height)
        self._details_toggle_btn.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
        for button in self._action_buttons:
            try:
                button.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
            except Exception:
                pass
        for box in (self._installed_box, self._review_box, self._preview_box):
            box.configure(font=self.app.ui_font("mono_small"))
        if self._library:
            self._refresh_library_ui()

    def _show_details_panel(self) -> None:
        if self._details_visible:
            return
        self._panes.add(self._details_host, minsize=130, height=185, stretch="never")
        self._details_visible = True
        self._details_toggle_btn.configure(text="Hide Details")

    def _hide_details_panel(self) -> None:
        if not self._details_visible:
            return
        self._panes.forget(self._details_host)
        self._details_visible = False
        self._details_toggle_btn.configure(text="Show Details")

    def _toggle_details_panel(self) -> None:
        if self._details_visible:
            self._hide_details_panel()
        else:
            self._show_details_panel()

    def _inspect_archive(self, archive_path: Path) -> None:
        self._load_archive(archive_path)
        if self._current_info is not None:
            self._open_inspect_dialog(archive_path, self._current_info, self._mods_for_archive(str(archive_path)))

    def _on_scope_changed(self, value: str) -> None:
        scope = _SCOPE_LABELS.get(value, "all")
        self._scope_var.set(scope)
        self._refresh_library_ui()
        if self._selected_library_path:
            self._load_archive(Path(self._selected_library_path), refresh_only=True)

    @staticmethod
    def _compact_name(raw: str) -> str:
        text = (raw or "").strip()
        if not text:
            return "(unnamed)"
        text = Path(text).stem
        text = re.sub(r"[-_]\d+(?:[-_]\d+){2,}$", "", text)
        text = re.sub(r"(?i)(?:[-_ ]+v(?:er(?:sion)?)?\.?\d+(?:[._-]\d+){1,})(?:[-_ ]+\d+)*$", "", text)
        text = re.sub(r"(?i)(?:[-_ ]+\d{8,})+$", "", text)
        text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
        text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
        text = text.replace("_", " ").replace("-", " ")
        text = re.sub(r"(?i)^windrose\s+", "", text)
        text = re.sub(r"(?i)\b(?:zip|7z|rar)\b$", "", text)
        text = re.sub(r"\s+", " ", text).strip(" ._-")
        return text or raw

    def _display_name_legacy(self, raw: str, *, max_len: int = 34) -> str:
        text = self._compact_name(raw)
        if len(text) <= max_len:
            return text
        clipped = text[: max_len - 1].rstrip(" ._-")
        return clipped + "…"

    def _display_name(self, raw: str, *, max_len: int | None = None) -> str:
        text = self._compact_name(raw)
        if max_len is None:
            max_len = self.app.ui_tokens.compact_name_len
        if len(text) <= max_len:
            return text
        clipped = text[: max(3, max_len - 3)].rstrip(" ._-")
        return clipped + "..."

    def _scope_matches_targets(self, targets: set[str]) -> bool:
        scope = self._scope_var.get()
        if scope == "all":
            return True
        if scope == "hosted":
            return False
        return scope in targets

    def _selected_filter_value(self) -> str:
        return _FILTER_VALUE_ALIASES.get(self._filter_var.get(), "all")

    def _applied_group_label(self, mod: ModInstall) -> str:
        targets = self._effective_targets(mod)
        if targets == {"client"}:
            return "Client"
        if targets == {"server"}:
            return "Local Server"
        if targets == {"dedicated_server"}:
            return "Dedicated Server"
        return "Other"

    def _selected_hosted_profile(self):
        server_tab = getattr(self.app, "_server_tab", None)
        if server_tab is None:
            return None
        try:
            return server_tab._selected_remote_profile()
        except Exception:
            return None

    def _mods_dir_for_target(self, target: str) -> Optional[Path]:
        paths = self.app.paths
        return {
            "client": paths.client_mods,
            "server": paths.server_mods,
            "dedicated_server": paths.dedicated_server_mods,
        }.get(target)

    def _visible_live_targets(self) -> list[str]:
        scope = self._scope_var.get()
        if scope == "all":
            return ["client", "server", "dedicated_server"]
        if scope in {"client", "server", "dedicated_server"}:
            return [scope]
        return []

    def _live_target_label(self, target: str) -> str:
        return {
            "client": "Client",
            "server": "Local Server",
            "dedicated_server": "Dedicated Server",
        }.get(target, target.replace("_", " ").title())

    def _live_snapshots(self, mods: list[ModInstall]) -> dict[str, LiveModsFolderSnapshot]:
        snapshots: dict[str, LiveModsFolderSnapshot] = {}
        for target in self._visible_live_targets():
            snapshots[target] = snapshot_live_mods_folder(
                self._mods_dir_for_target(target),
                mods,
                target=target,
            )
        return snapshots

    def _bundle_live_items(self, folder: Optional[Path], file_names: list[str], *, target_label: str) -> list[dict]:
        if folder is None:
            return []
        items: list[dict] = []
        for bundle in bundle_live_file_names(file_names):
            bundle_paths = [folder / name for name in bundle.file_names]
            bundle_id = "||".join(str(path) for path in bundle_paths)
            self._live_file_bundle_members[bundle_id] = bundle_paths
            self._live_file_bundle_meta[bundle_id] = {"kind": "local", "target_label": target_label}
            items.append(
                {
                    "bundle_id": bundle_id,
                    "display_name": bundle.display_name,
                    "file_names": list(bundle.file_names),
                    "paths": bundle_paths,
                }
            )
        return items

    def _bundle_hosted_items(self, remote_files: list[str]) -> list[dict]:
        by_name: dict[str, list[str]] = defaultdict(list)
        for remote_path in remote_files:
            by_name[PurePosixPath(remote_path).name].append(remote_path)
        items: list[dict] = []
        for bundle in bundle_live_file_names(by_name.keys()):
            member_paths: list[str] = []
            for file_name in bundle.file_names:
                member_paths.extend(by_name[file_name])
            bundle_id = "hosted::" + "||".join(member_paths)
            self._live_file_bundle_members[bundle_id] = member_paths
            self._live_file_bundle_meta[bundle_id] = {"kind": "hosted", "target_label": "Hosted Server"}
            items.append(
                {
                    "bundle_id": bundle_id,
                    "display_name": bundle.display_name,
                    "file_names": list(bundle.file_names),
                    "paths": member_paths,
                    "is_pak": any(name.lower().endswith(".pak") for name in bundle.file_names),
                }
            )
        return items

    def _resolve_live_file_paths(self, file_ref: str | Path) -> list[Path | str]:
        if isinstance(file_ref, Path):
            return [file_ref]
        bundle_members = getattr(self, "_live_file_bundle_members", {})
        if file_ref in bundle_members:
            return bundle_members[file_ref]
        return [Path(file_ref)]

    def _open_folder(self, folder: Path, *, label: str) -> None:
        try:
            os.startfile(str(folder))
            self._set_result(f"Opened {label}.", level="info")
        except Exception as exc:
            self._set_result(f"Could not open {label}: {exc}", level="error")

    def _open_archive_folder(self, archive_path: Path) -> None:
        self._open_folder(archive_path.parent, label=f"{archive_path.name} source folder")

    def _open_mod_folder(self, mod: ModInstall) -> None:
        if not mod.installed_files:
            self._set_result("This install does not have any recorded files yet.", level="info")
            return
        self._open_folder(self._canonical_installed_path(mod.installed_files[0]).parent, label=f"{mod.display_name} install folder")

    def _open_live_item_folder(self, file_ref: str | Path, target_label: str) -> None:
        bundle_paths = self._resolve_live_file_paths(file_ref)
        if not bundle_paths:
            self._set_result("No live files are available for this row.", level="info")
            return
        first = bundle_paths[0]
        if isinstance(first, str):
            self._set_result(f"{target_label} uses a remote folder. Open it through your host or SSH/SFTP client.", level="info")
            return
        self._open_folder(first.parent, label=f"{target_label.lower()} ~mods")

    def _remove_unmanaged_live_file(self, file_ref: str | Path, target_label: str) -> None:
        metadata = getattr(self, "_live_file_bundle_meta", {}).get(str(file_ref), {})
        kind = metadata.get("kind", "local")
        bundle_paths = self._resolve_live_file_paths(file_ref)
        if kind == "hosted":
            profile = self._selected_hosted_profile()
            if profile is None:
                self._set_result("Choose a hosted profile first.", level="info")
                return
            remote_paths = [str(path) for path in bundle_paths]
            if not remote_paths:
                self._set_result("This hosted item is no longer present.", level="info")
                self._refresh_applied_ui()
                return
            names_text = (
                PurePosixPath(remote_paths[0]).name
                if len(remote_paths) == 1
                else f"{PurePosixPath(remote_paths[0]).name} and {len(remote_paths) - 1} companion file(s)"
            )
            if not self.app.confirm_action(
                "destructive",
                "Remove Hosted Files",
                f"Remove {names_text} from the hosted server?\n\nThese files are not tracked by the manifest.",
            ):
                return
            deleted, failed = self.app.remote_deployer.delete_remote_files(profile, remote_paths)
            if failed:
                self._set_result("Could not remove hosted file(s): " + " | ".join(failed[:3]), level="error")
                return
            self.app.manifest.add_record(
                DeploymentRecord(
                    mod_id=f"hosted:{profile.profile_id}",
                    action="hosted_remove",
                    target="hosted",
                    display_name=PurePosixPath(remote_paths[0]).stem,
                    notes=f"Removed {len(deleted)} hosted file(s) from {profile.name}",
                )
            )
            self._set_result(f"Removed {len(deleted)} hosted file(s) from {profile.name}.", level="success")
            self.refresh_view()
            return

        existing_paths = [path for path in bundle_paths if isinstance(path, Path) and path.is_file()]
        if not existing_paths:
            missing_name = Path(str(bundle_paths[0])).name if bundle_paths else "selected file"
            self._set_result(f"{missing_name} is no longer present in {target_label.lower()} ~mods.", level="info")
            self._refresh_applied_ui()
            return
        names_text = existing_paths[0].name if len(existing_paths) == 1 else f"{existing_paths[0].name} and {len(existing_paths) - 1} companion file(s)"
        if not self.app.confirm_action(
            "destructive",
            "Remove Unmanaged File",
            f"Remove {names_text} from {target_label} ~mods?\n\nThese files are not tracked by the manifest.",
        ):
            return
        failed_paths = [path.name for path in existing_paths if not safe_delete(path)]
        if failed_paths:
            failed_label = failed_paths[0] if len(failed_paths) == 1 else f"{failed_paths[0]} (+{len(failed_paths) - 1} more)"
            self._set_result(f"Could not remove {failed_label}.", level="error")
            return
        if len(existing_paths) == 1:
            self._set_result(f"Removed unmanaged file {existing_paths[0].name} from {target_label.lower()} ~mods.", level="success")
        else:
            self._set_result(
                f"Removed unmanaged bundle {existing_paths[0].stem} ({len(existing_paths)} files) from {target_label.lower()} ~mods.",
                level="success",
            )
        self.refresh_view()

    def _request_hosted_inventory(self) -> None:
        profile = self._selected_hosted_profile()
        self._live_file_bundle_members = {}
        self._live_file_bundle_meta = {}
        if profile is None:
            self._applied_summary_label.configure(text="No hosted profile selected")
            empty = ctk.CTkLabel(
                self._applied_list,
                text="Choose a hosted profile in Server first. Then switch back to Hosted Server in Mods to view the live remote mod list.",
                justify="left",
                wraplength=330,
                text_color="#95a5a6",
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._applied_widgets.append(empty)
            self._update_selection_state()
            return

        request_id = self._hosted_inventory_request = self._hosted_inventory_request + 1
        self._applied_summary_label.configure(text=f"Loading {profile.name}...")
        loading = ctk.CTkLabel(
            self._applied_list,
            text=f"Loading hosted mod inventory from {profile.name}...",
            justify="left",
            wraplength=330,
            text_color="#95a5a6",
        )
        loading.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        self._applied_widgets.append(loading)

        def _work() -> None:
            try:
                remote_files = self.app.remote_deployer.list_remote_files(profile)
                error = None
            except Exception as exc:
                remote_files = []
                error = str(exc)

            def _show() -> None:
                if request_id != self._hosted_inventory_request or self._scope_var.get() != "hosted":
                    return
                self._render_hosted_inventory(profile.name, remote_files, error=error)

            self.app.dispatch_to_ui(_show)

        threading.Thread(target=_work, daemon=True).start()

    def _render_hosted_inventory(self, profile_name: str, remote_files: list[str], *, error: Optional[str] = None) -> None:
        for widget in self._applied_widgets:
            widget.destroy()
        self._applied_widgets.clear()

        if error:
            self._applied_summary_label.configure(text="Hosted inventory unavailable")
            message = ctk.CTkLabel(
                self._applied_list,
                text=f"Could not load hosted inventory for {profile_name}.\n\n{error}",
                justify="left",
                wraplength=330,
                text_color="#c0392b",
            )
            message.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._applied_widgets.append(message)
            self._update_selection_state()
            return

        hosted_items = self._bundle_hosted_items(remote_files)
        visible_bundle_ids = {item["bundle_id"] for item in hosted_items}
        self._selected_live_files.intersection_update(visible_bundle_ids)
        pak_items = [item for item in hosted_items if item["is_pak"]]
        other_items = [item for item in hosted_items if not item["is_pak"]]
        self._applied_summary_label.configure(text=f"{len(hosted_items)} hosted item(s)")

        if not hosted_items:
            empty = ctk.CTkLabel(
                self._applied_list,
                text=f"No files were found in the hosted mods folder for {profile_name}.",
                justify="left",
                wraplength=330,
                text_color="#95a5a6",
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._applied_widgets.append(empty)
            self._update_selection_state()
            return

        row = 0
        sections = [("PAK Mods", pak_items), ("Other Files", other_items)]
        for heading_text, items in sections:
            if not items:
                continue
            heading = ctk.CTkLabel(
                self._applied_list,
                text=heading_text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#c1c7cd",
                anchor="w",
            )
            heading.grid(row=row, column=0, sticky="ew", pady=(3 if row else 0, 3))
            self._applied_widgets.append(heading)
            row += 1

            for item in items:
                row_frame = ctk.CTkFrame(self._applied_list, fg_color="#2f2f2f")
                row_frame.grid(row=row, column=0, sticky="ew", pady=1)
                row_frame.grid_columnconfigure(1, weight=1)
                selected_var = tk.BooleanVar(value=item["bundle_id"] in self._selected_live_files)
                ctk.CTkCheckBox(
                    row_frame,
                    text="",
                    width=18,
                    variable=selected_var,
                    command=lambda value=item["bundle_id"], var=selected_var: self._toggle_live_file_selection(value, bool(var.get())),
                ).grid(
                    row=0, column=0, rowspan=2, sticky="nw", padx=(8, 2), pady=(8, 4)
                )
                title = ctk.CTkLabel(
                    row_frame,
                    text=self._display_name(item["display_name"], max_len=max(24, self.app.ui_tokens.compact_name_len - 4)),
                    anchor="w",
                    font=self.app.ui_font("row_title"),
                    text_color="#ffffff",
                )
                title.grid(row=0, column=1, sticky="ew", padx=9, pady=(5 + self.app.ui_tokens.row_pad_y, 1))
                file_hint = (
                    item["file_names"][0]
                    if len(item["file_names"]) == 1
                    else f"{item['file_names'][0]} (+{len(item['file_names']) - 1} more)"
                )
                subtitle = ctk.CTkLabel(
                    row_frame,
                    text=f"Hosted Server | remote ~mods | {file_hint}",
                    anchor="w",
                    font=self.app.ui_font("small"),
                    text_color="#95a5a6",
                )
                subtitle.grid(row=1, column=1, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))
                for widget in (row_frame, title, subtitle):
                    widget.bind(
                        "<Button-3>",
                        lambda event, p=item["bundle_id"]: self._show_unmanaged_file_menu(event, p, "Hosted Server"),
                    )
                self._applied_widgets.append(row_frame)
                row += 1
        self._update_selection_state()

    def _show_applied_menu(self, event, mod: ModInstall) -> None:
        menu = tk.Menu(self, tearoff=0)
        if mod.source_archive:
            menu.add_command(label="Inspect", command=lambda p=Path(mod.source_archive): self._inspect_archive(p))
        if mod.source_archive and Path(mod.source_archive).is_file():
            install_menu = self._build_install_menu(menu, Path(mod.source_archive))
            menu.add_cascade(label="Install To...", menu=install_menu)
        if mod.source_archive and Path(mod.source_archive).is_file():
            menu.add_command(label="Reinstall", command=self._on_reinstall)
            menu.add_command(label="Repair", command=self._on_repair)
        menu.add_command(label="Uninstall", command=self._on_uninstall)
        selected_mods, selected_live = self._selected_applied_context(mod=mod)
        if len(selected_mods) + len(selected_live) > 1:
            menu.add_command(label="Uninstall Selected", command=self._on_uninstall_selected_mods)
        menu.add_separator()
        menu.add_command(label="Open Installed Folder", command=lambda m=mod: self._open_mod_folder(m))
        if mod.source_archive and Path(mod.source_archive).is_file():
            menu.add_command(label="Open Source Folder", command=lambda p=Path(mod.source_archive): self._open_archive_folder(p))
        menu.add_separator()
        menu.add_command(label="Compare with Server", command=self._on_compare_with_server)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_unmanaged_file_menu(self, event, file_ref: str | Path, target_label: str) -> None:
        menu = tk.Menu(self, tearoff=0)
        selected_mods, selected_live = self._selected_applied_context(live_bundle_id=str(file_ref))
        menu.add_command(label="Uninstall", command=lambda p=file_ref, label=target_label: self._remove_unmanaged_live_file(p, label))
        if len(selected_mods) + len(selected_live) > 1:
            menu.add_command(label="Uninstall Selected", command=self._on_uninstall_selected_mods)
        menu.add_separator()
        menu.add_command(label="Open Folder", command=lambda p=file_ref, label=target_label: self._open_live_item_folder(p, label))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_mod_component_menu(self, event, mod: ModInstall, group: dict[str, object]) -> None:
        label = str(group.get("label", "Selected Pak"))
        selected_entries = {str(path) for path in group.get("entry_paths", [])}
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=f"Uninstall {label}",
            command=lambda current=mod, entries=selected_entries, item_label=label: self._uninstall_mod_component_group(current, entries, item_label),
        )
        menu.add_separator()
        menu.add_command(label="Open Installed Folder", command=lambda current=mod: self._open_mod_folder(current))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_archive_component_menu(self, event, archive_path: Path, info: ArchiveInfo | None, group: dict[str, object]) -> None:
        label = str(group.get("label", "Selected Pak"))
        selected_entries = {str(path) for path in group.get("entry_paths", [])}
        installed_targets = self._component_targets_text(self._mods_for_archive(str(archive_path)), group)
        menu = tk.Menu(self, tearoff=0)
        if info is not None and self._supports_selected_child_install(info):
            menu.add_command(
                label=f"Install {label}",
                command=lambda current=archive_path, current_info=info, entries=selected_entries: self._install_archive_components(current, current_info, entries),
            )
        if installed_targets != "Not active":
            menu.add_command(
                label=f"Uninstall {label}",
                command=lambda current=archive_path, entries=selected_entries: self._uninstall_archive_components(current, entries),
            )
        menu.add_separator()
        menu.add_command(label="Inspect Mod", command=lambda current=archive_path: self._inspect_archive(current))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _refresh_applied_ui(self) -> None:
        for widget in self._applied_widgets:
            widget.destroy()
        self._applied_widgets.clear()

        if self._scope_var.get() == "hosted":
            self._selected_mod_ids.clear()
            self._selected_live_files.clear()
            self._update_selection_state()
            self._request_hosted_inventory()
            return

        mods = [
            mod for mod in self.app.manifest.list_mods()
            if self._scope_matches_targets(self._effective_targets(mod))
        ]
        live_snapshots = self._live_snapshots(mods)
        self._live_file_bundle_members = {}
        self._live_file_bundle_meta = {}
        visible_mod_ids = {mod.mod_id for mod in mods}
        self._selected_mod_ids.intersection_update(visible_mod_ids)
        enabled_count = sum(1 for mod in mods if mod.enabled)
        disabled_count = len(mods) - enabled_count
        summary = f"{enabled_count} active"
        if disabled_count:
            summary += f" | {disabled_count} disabled"
        unmanaged_count = sum(len(bundle_live_file_names(snapshot.unmanaged_files)) for snapshot in live_snapshots.values())
        missing_count = sum(len(snapshot.missing_managed_files) for snapshot in live_snapshots.values())
        if unmanaged_count:
            summary += f" | {unmanaged_count} unmanaged items"
        if missing_count:
            summary += f" | {missing_count} missing files"
        self._applied_summary_label.configure(text=summary if (mods or live_snapshots) else "0 active")

        has_live_issues = any(snapshot.warning or snapshot.unmanaged_files or snapshot.missing_managed_files for snapshot in live_snapshots.values())
        if not mods and not has_live_issues:
            empty = ctk.CTkLabel(
                self._applied_list,
                text="No active mods yet. Install an inactive mod to the client, local server, or dedicated server to track it here.",
                justify="left",
                wraplength=self.app.ui_tokens.panel_wrap,
                text_color="#95a5a6",
                font=self.app.ui_font("small"),
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._applied_widgets.append(empty)
            self._update_selection_state()
            return

        grouped: dict[str, list[ModInstall]] = defaultdict(list)
        for mod in mods:
            grouped[self._applied_group_label(mod)].append(mod)
        live_by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
        missing_by_group: dict[str, list[str]] = defaultdict(list)
        label_to_target = {
            "Client": "client",
            "Local Server": "server",
            "Dedicated Server": "dedicated_server",
        }
        for group_name, target in label_to_target.items():
            snapshot = live_snapshots.get(target)
            if snapshot is None or snapshot.folder is None:
                continue
            live_by_group[group_name] = self._bundle_live_items(snapshot.folder, snapshot.unmanaged_files, target_label=group_name)
            missing_by_group[group_name] = list(snapshot.missing_managed_files)
        self._selected_live_files.intersection_update(self._live_file_bundle_members.keys())

        order = ["Client", "Local Server", "Dedicated Server", "Other"]
        row = 0
        for group_name in order:
            items = grouped.get(group_name, [])
            unmanaged_items = live_by_group.get(group_name, [])
            missing_items = missing_by_group.get(group_name, [])
            if not items and not unmanaged_items and not missing_items:
                continue
            heading = ctk.CTkLabel(
                self._applied_list,
                text=group_name,
                font=self.app.ui_font("card_title"),
                text_color="#c1c7cd",
                anchor="w",
            )
            heading.grid(row=row, column=0, sticky="ew", pady=(3 if row else 0, 3))
            self._applied_widgets.append(heading)
            row += 1

            for mod in sorted(items, key=lambda item: (not item.enabled, item.display_name.lower(), item.install_time), reverse=False):
                archive_name = Path(mod.source_archive).name if mod.source_archive else "(no source)"
                component_groups = self._mod_component_groups(mod)
                is_expanded = mod.mod_id in self._expanded_mod_ids
                row_frame = ctk.CTkFrame(
                    self._applied_list,
                    fg_color="#213040" if mod.source_archive == self._selected_library_path else "#2f2f2f",
                    cursor="hand2" if mod.source_archive else "arrow",
                )
                row_frame.grid(row=row, column=0, sticky="ew", pady=1)
                row_frame.grid_columnconfigure(1, weight=1)

                selected_var = tk.BooleanVar(value=mod.mod_id in self._selected_mod_ids)
                ctk.CTkCheckBox(
                    row_frame,
                    text="",
                    width=18,
                    variable=selected_var,
                    command=lambda value=mod.mod_id, var=selected_var: self._toggle_mod_selection(value, bool(var.get())),
                ).grid(
                    row=0, column=0, rowspan=2, sticky="nw", padx=(8, 2), pady=(8, 4)
                )

                title_parts = [self._display_name(mod.display_name, max_len=32)]
                if mod.selected_variant:
                    title_parts.append(f"({mod.selected_variant})")
                if not mod.enabled:
                    title_parts.append("[disabled]")
                title = ctk.CTkLabel(
                    row_frame,
                    text=" ".join(title_parts),
                    anchor="w",
                    font=self.app.ui_font("row_title"),
                    text_color="#ffffff",
                )
                title.grid(row=0, column=1, sticky="ew", padx=9, pady=(5 + self.app.ui_tokens.row_pad_y, 1))

                subtitle_parts = [summarize_target_values(mod.targets)]
                install_kind_label = self._install_kind_label(mod.install_kind)
                if install_kind_label:
                    subtitle_parts.append(install_kind_label)
                subtitle_parts.extend([archive_name, f"{mod.file_count} files"])
                if mod.metadata.version_tag:
                    subtitle_parts.append(f"version {mod.metadata.version_tag}")
                elif mod.metadata.source_label:
                    subtitle_parts.append(mod.metadata.source_label)
                if mod.source_archive and not Path(mod.source_archive).is_file():
                    subtitle_parts.append("source missing")
                subtitle = ctk.CTkLabel(
                    row_frame,
                    text=" | ".join(subtitle_parts),
                    anchor="w",
                    font=self.app.ui_font("small"),
                    text_color="#95a5a6",
                )
                subtitle.grid(row=1, column=1, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))

                if len(component_groups) > 1:
                    expand_btn = ctk.CTkButton(
                        row_frame,
                        text="▾" if is_expanded else "▸",
                        width=28,
                        height=self.app.ui_tokens.compact_button_height,
                        font=self.app.ui_font("body"),
                        fg_color="#444444",
                        hover_color="#666666",
                        command=lambda value=mod.mod_id: self._toggle_mod_expanded(value),
                    )
                    expand_btn.grid(row=0, column=2, rowspan=2, padx=(0, 8), pady=6)
                    expand_btn.configure(text="v" if is_expanded else ">")

                if mod.source_archive:
                    for widget in (row_frame, title, subtitle):
                        widget.bind("<Button-1>", lambda _event, p=Path(mod.source_archive): self._load_archive(p))
                        widget.bind("<Button-3>", lambda event, m=mod: self._show_applied_menu(event, m))

                if False and is_expanded and component_groups:
                    for component_index, component in enumerate(component_groups, start=2):
                        component_label = ctk.CTkLabel(
                            row_frame,
                            text=f"• {component['label']} | {len(component['installed_paths'])} installed file(s)",
                            anchor="w",
                            justify="left",
                            text_color="#c1c7cd",
                            font=self.app.ui_font("small"),
                        )
                        component_label.grid(
                            row=component_index,
                            column=1,
                            columnspan=2,
                            sticky="ew",
                            padx=(24, 8),
                            pady=(0, 2),
                        )

                if is_expanded and component_groups:
                    selected_keys = self._mod_component_selections.get(mod.mod_id, set())
                    visible_groups = component_groups[:12]
                    for component_index, component in enumerate(visible_groups, start=2):
                        child_row = ctk.CTkFrame(row_frame, fg_color="#27323a")
                        child_row.grid(
                            row=component_index,
                            column=1,
                            columnspan=2,
                            sticky="ew",
                            padx=(20, 8),
                            pady=(0, 2),
                        )
                        child_row.grid_columnconfigure(1, weight=1)
                        selection_key = str(component.get("selection_key", ""))
                        selected_var = tk.BooleanVar(value=selection_key in selected_keys)
                        ctk.CTkCheckBox(
                            child_row,
                            text="",
                            width=18,
                            variable=selected_var,
                            command=lambda mod_id=mod.mod_id, key=selection_key, var=selected_var: self._toggle_mod_component_selection(mod_id, key, bool(var.get())),
                        ).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(8, 4), pady=(8, 4))
                        child_title = ctk.CTkLabel(
                            child_row,
                            text=str(component["label"]),
                            anchor="w",
                            justify="left",
                            text_color="#ffffff",
                            font=self.app.ui_font("small"),
                        )
                        child_title.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(6, 1))
                        child_subtitle = ctk.CTkLabel(
                            child_row,
                            text=f"{len(component['installed_paths'])} installed file(s)",
                            anchor="w",
                            justify="left",
                            text_color="#95a5a6",
                            font=self.app.ui_font("tiny"),
                        )
                        child_subtitle.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
                        for widget in (child_row, child_title, child_subtitle):
                            widget.bind(
                                "<Button-3>",
                                lambda event, current=mod, group=component: self._show_mod_component_menu(event, current, group),
                            )

                    action_row = ctk.CTkFrame(row_frame, fg_color="transparent")
                    action_row.grid(
                        row=len(visible_groups) + 2,
                        column=1,
                        columnspan=2,
                        sticky="w",
                        padx=(20, 8),
                        pady=(2, 6),
                    )
                    ctk.CTkButton(
                        action_row,
                        text="Uninstall Checked",
                        width=138,
                        height=self.app.ui_tokens.compact_button_height,
                        font=self.app.ui_font("body"),
                        fg_color="#555555",
                        hover_color="#666666",
                        command=lambda current=mod: self._uninstall_selected_mod_components(current),
                    ).pack(side="left")
                    if len(component_groups) > len(visible_groups):
                        more_label = ctk.CTkLabel(
                            row_frame,
                            text=f"+ {len(component_groups) - len(visible_groups)} more pak item(s). Use Inspect for the full list.",
                            anchor="w",
                            justify="left",
                            text_color="#95a5a6",
                            font=self.app.ui_font("small"),
                        )
                        more_label.grid(
                            row=len(visible_groups) + 3,
                            column=1,
                            columnspan=2,
                            sticky="ew",
                            padx=(24, 8),
                            pady=(0, 6),
                        )

                self._applied_widgets.append(row_frame)
                row += 1

            for item in unmanaged_items:
                row_frame = ctk.CTkFrame(self._applied_list, fg_color="#2f2f2f")
                row_frame.grid(row=row, column=0, sticky="ew", pady=1)
                row_frame.grid_columnconfigure(1, weight=1)

                selected_var = tk.BooleanVar(value=item["bundle_id"] in self._selected_live_files)
                ctk.CTkCheckBox(
                    row_frame,
                    text="",
                    width=18,
                    variable=selected_var,
                    command=lambda value=item["bundle_id"], var=selected_var: self._toggle_live_file_selection(value, bool(var.get())),
                ).grid(
                    row=0, column=0, rowspan=2, sticky="nw", padx=(8, 2), pady=(8, 4)
                )

                subtitle_text = (
                    f"{group_name} | untracked file | {item['file_names'][0]}"
                    if len(item["file_names"]) == 1
                    else f"{group_name} | untracked bundle | {item['file_names'][0]} (+{len(item['file_names']) - 1} more)"
                )
                title = ctk.CTkLabel(
                    row_frame,
                    text=self._display_name(item["display_name"], max_len=32),
                    anchor="w",
                    font=self.app.ui_font("row_title"),
                    text_color="#ffffff",
                )
                title.grid(row=0, column=1, sticky="ew", padx=9, pady=(5 + self.app.ui_tokens.row_pad_y, 1))
                subtitle = ctk.CTkLabel(
                    row_frame,
                    text=subtitle_text,
                    anchor="w",
                    font=self.app.ui_font("small"),
                    text_color="#f39c12",
                )
                subtitle.grid(row=1, column=1, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))

                for widget in (row_frame, title, subtitle):
                    widget.bind(
                        "<Button-3>",
                        lambda event, p=item["bundle_id"], label=group_name: self._show_unmanaged_file_menu(event, p, label),
                    )

                self._applied_widgets.append(row_frame)
                row += 1

            for name in missing_items:
                row_frame = ctk.CTkFrame(self._applied_list, fg_color="#2f2f2f")
                row_frame.grid(row=row, column=0, sticky="ew", pady=1)
                row_frame.grid_columnconfigure(0, weight=1)
                title = ctk.CTkLabel(
                    row_frame,
                    text=self._display_name(name, max_len=32),
                    anchor="w",
                    font=self.app.ui_font("row_title"),
                    text_color="#ffffff",
                )
                title.grid(row=0, column=0, sticky="ew", padx=9, pady=(5 + self.app.ui_tokens.row_pad_y, 1))
                subtitle = ctk.CTkLabel(
                    row_frame,
                    text=f"{group_name} | managed install missing file | {name}",
                    anchor="w",
                    font=self.app.ui_font("small"),
                    text_color="#c0392b",
                )
                subtitle.grid(row=1, column=0, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))
                self._applied_widgets.append(row_frame)
                row += 1

        for target in self._visible_live_targets():
            snapshot = live_snapshots.get(target)
            if snapshot is None or not snapshot.warning:
                continue
            warning = ctk.CTkLabel(
                self._applied_list,
                text=f"{self._live_target_label(target)}: {snapshot.warning}",
                justify="left",
                wraplength=self.app.ui_tokens.panel_wrap,
                text_color="#e67e22",
                font=self.app.ui_font("small"),
                anchor="w",
            )
            warning.grid(row=row, column=0, sticky="ew", pady=(1, 4), padx=8)
            self._applied_widgets.append(warning)
            row += 1
        self._update_selection_state()

    def _display_entries(self) -> list[dict]:
        entries = list(self._library)
        known_paths = {str(entry.get("path", "")) for entry in entries}
        synthetic_entries: list[dict] = []
        seen_synthetic: set[str] = set()
        for mod in self.app.manifest.list_mods():
            path_str = (mod.source_archive or "").strip()
            if not path_str or path_str in known_paths or path_str in seen_synthetic:
                continue
            archive_path = Path(path_str)
            synthetic_entries.append(
                {
                    "path": path_str,
                    "name": archive_path.stem or mod.display_name,
                    "ext": archive_path.suffix.lower(),
                    "_synthetic": True,
                }
            )
            seen_synthetic.add(path_str)
        return entries + synthetic_entries

    def _filtered_entries(self) -> list[dict]:
        search = self._search_var.get().strip().lower()
        selected_filter = self._selected_filter_value()
        entries: list[dict] = []
        for entry in self._display_entries():
            path_str = str(entry["path"])
            mods = self._mods_for_archive(path_str)
            targets = {target for mod in mods for target in self._effective_targets(mod)}
            exists = Path(path_str).is_file()
            name = entry.get("name", Path(path_str).stem).lower()
            haystack = " ".join(
                [
                    name,
                    path_str.lower(),
                    self._installed_to_text(mods).lower(),
                    self._last_action_text(path_str).lower(),
                    "not tracked" if entry.get("_synthetic") else "tracked",
                ]
            )
            if search and search not in haystack:
                continue
            if selected_filter == "available" and mods:
                continue
            if selected_filter == "installed" and not mods:
                continue
            if selected_filter == "client" and "client" not in targets:
                continue
            if selected_filter == "server" and "server" not in targets:
                continue
            if selected_filter == "dedicated" and "dedicated_server" not in targets:
                continue
            if selected_filter == "client_local" and targets != {"client", "server"}:
                continue
            if selected_filter == "missing archive" and exists:
                continue
            if self._scope_var.get() == "hosted":
                if not exists:
                    continue
            elif mods and not self._scope_matches_targets(targets):
                continue
            entries.append(entry)
        return entries

    def _refresh_library_selection_styles(self) -> None:
        for path_str, row in list(self._library_row_frames.items()):
            if not row.winfo_exists():
                self._library_row_frames.pop(path_str, None)
                continue
            row.configure(fg_color="#213040" if path_str == self._selected_library_path else "transparent")

    def _refresh_library_ui(self, *, refresh_applied: bool = True) -> None:
        for widget in self._library_widgets:
            widget.destroy()
        self._library_widgets.clear()
        self._library_row_frames.clear()
        if refresh_applied:
            self._refresh_applied_ui()

        display_entries = self._display_entries()
        if self._scope_var.get() == "hosted":
            active_summary = "live hosted inventory"
        else:
            active_count = sum(
                1 for mod in self.app.manifest.list_mods()
                if self._scope_matches_targets(self._effective_targets(mod))
            )
            active_summary = f"{active_count} active"
        hidden_count = sum(1 for entry in display_entries if entry.get("_synthetic"))
        scope_label = {
            "all": "all targets",
            "client": "client",
            "server": "local server",
            "dedicated_server": "dedicated server",
            "hosted": "hosted server",
        }.get(self._scope_var.get(), "all targets")
        filtered_entries = self._filtered_entries()
        visible_paths = {str(entry["path"]) for entry in filtered_entries}
        self._selected_archive_paths.intersection_update(visible_paths)
        summary = f"{len(filtered_entries)} inactive mod(s) shown | {active_summary} | {scope_label}"
        if hidden_count:
            summary += f" | {hidden_count} not tracked"
        self._summary_label.configure(text=summary)

        if not filtered_entries:
            empty_text = (
                "Drop archives or pak files into this list, or use Add to track your first inactive mod."
                if not self._search_var.get().strip() and self._selected_filter_value() == "available"
                else "No inactive mods match the current search or filter."
            )
            empty = ctk.CTkLabel(
                self._library_list,
                text=empty_text,
                justify="left",
                wraplength=self.app.ui_tokens.panel_wrap,
                text_color="#95a5a6",
                font=self.app.ui_font("small"),
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(6, 6), padx=10)
            self._library_widgets.append(empty)
            self._update_selection_state()
            return

        for index, entry in enumerate(filtered_entries):
            self._add_library_row(entry, index)
        self._update_selection_state()
        self._refresh_library_selection_styles()

    def _add_library_row_legacy_unused(self, entry: dict, index: int) -> None:
        path = Path(entry["path"])
        exists = path.is_file()
        mods = self._mods_for_archive(str(path))
        is_synthetic = bool(entry.get("_synthetic"))
        child_items = list(entry.get("child_items", []) or [])
        is_expanded = str(path) in self._expanded_archive_paths
        update_hint = self._archive_update_hint(entry)
        component_groups: list[dict[str, object]] = []
        component_info = None
        if is_expanded and exists and child_items:
            try:
                component_info = self._get_archive_info(path)
                component_groups = self._archive_component_groups(component_info)
            except Exception as exc:
                log.warning("Could not inspect archive for inline bundle view: %s", exc)
        if mods and is_synthetic and exists:
            status = "Active"
        elif mods and is_synthetic and not exists:
            status = "Active*"
        else:
            status = "Missing" if not exists else "Active" if mods else "Inactive"
        if mods and all(not mod.enabled for mod in mods) and status == "Active":
            status = "Disabled"

        row = ctk.CTkFrame(
            self._library_list,
            fg_color="#213040" if str(path) == self._selected_library_path else "transparent",
            cursor="hand2" if exists or mods else "arrow",
        )
        row.grid(row=index, column=0, sticky="ew", pady=1)
        row.grid_columnconfigure(2, weight=1)
        self._library_row_frames[str(path)] = row

        selected_var = tk.BooleanVar(value=str(path) in self._selected_archive_paths)
        ctk.CTkCheckBox(
            row,
            text="",
            width=18,
            variable=selected_var,
            command=lambda value=str(path), var=selected_var: self._toggle_archive_selection(value, bool(var.get())),
        ).grid(
            row=0, column=0, rowspan=3, sticky="nw", padx=(8, 2), pady=(8, 4)
        )

        color = {
            "Inactive": "#3498db",
            "Active": "#2d8a4e",
            "Disabled": "#f39c12",
            "Active*": "#f39c12",
            "Missing": "#c0392b",
        }.get(status, "#95a5a6")
        badge = ctk.CTkLabel(row, text=status, text_color=color, width=58, anchor="w", font=self.app.ui_font("small"))
        badge.grid(row=0, column=1, sticky="w", padx=(4, 4), pady=(5 + self.app.ui_tokens.row_pad_y, 1))
        name = ctk.CTkLabel(
            row,
            text=self._display_name(entry.get("name", path.stem), max_len=max(24, self.app.ui_tokens.compact_name_len - 6)),
            anchor="w",
            font=self.app.ui_font("row_title"),
            text_color="#ffffff" if exists else "#777777",
        )
        name.grid(row=0, column=2, sticky="w", padx=4, pady=(5 + self.app.ui_tokens.row_pad_y, 1))

        type_label = str(entry.get("archive_type", "Unknown")).title()
        total_files = int(entry.get("total_files", 0) or 0)
        category_label = self._install_kind_label(str(entry.get("install_kind", "standard_mod"))) or {
            "framework_runtime": "Framework Runtime",
            "framework_mod": "Framework-Dependent Mod",
        }.get(str(entry.get("content_category", "standard_mod")), "")
        details = " | ".join(
            part for part in [
                self._source_kind_label(entry),
                type_label,
                category_label,
                f"{total_files} files" if total_files else "",
                f"Active On: {self._installed_to_text(mods)}",
                "Not tracked" if is_synthetic else "",
            ] if part
        )
        detail_label = ctk.CTkLabel(
            row, text=details, anchor="w", text_color="#95a5a6", wraplength=self.app.ui_tokens.panel_wrap, font=self.app.ui_font("small")
        )
        detail_label.grid(row=1, column=1, columnspan=2, sticky="ew", padx=9, pady=(0, 1))
        footer_text = self._last_action_text(str(path))
        if entry.get("dependency_warnings"):
            footer_text += " | dependency review recommended"
        if update_hint:
            footer_text += " | possible update available"
        action_label = ctk.CTkLabel(row, text=footer_text, anchor="w", text_color="#6f7a81", font=self.app.ui_font("tiny"))
        action_label.grid(row=2, column=1, columnspan=2, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))

        if child_items:
            expand_btn = ctk.CTkButton(
                row,
                text="▾" if is_expanded else "▸",
                width=28,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._toggle_archive_expanded(value),
            )
            expand_btn.configure(text="v" if is_expanded else ">")
            expand_btn.grid(row=0, column=3, rowspan=3, padx=(0, 6), pady=6)

        if is_synthetic and exists:
            action_btn = ctk.CTkButton(
                row,
                text="Add",
                width=64,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._track_in_library(value),
            )
            action_btn.grid(row=0, column=4, rowspan=3, padx=(6, 9), pady=6)
        elif not is_synthetic:
            action_btn = ctk.CTkButton(
                row,
                text="Remove",
                width=76,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._remove_from_library(value),
            )
            action_btn.grid(row=0, column=4, rowspan=3, padx=(6, 9), pady=6)

        if is_expanded and child_items:
            for child_index, child_name in enumerate(child_items[:12], start=3):
                child_label = ctk.CTkLabel(
                    row,
                    text=f"• {child_name}",
                    anchor="w",
                    justify="left",
                    text_color="#c1c7cd",
                    font=self.app.ui_font("small"),
                )
                child_label.grid(
                    row=child_index,
                    column=1,
                    columnspan=4,
                    sticky="ew",
                    padx=(24, 9),
                    pady=(0, 2),
                )
            if len(child_items) > 12:
                more_label = ctk.CTkLabel(
                    row,
                    text=f"+ {len(child_items) - 12} more item(s). Use Inspect for the full list.",
                    anchor="w",
                    justify="left",
                    text_color="#95a5a6",
                    font=self.app.ui_font("small"),
                )
                more_label.grid(
                    row=15,
                    column=1,
                    columnspan=4,
                    sticky="ew",
                    padx=(24, 9),
                    pady=(0, 6),
                )

        for widget in (row, badge, name, detail_label, action_label):
            widget.bind("<Button-1>", lambda _event, p=path: self._on_library_row_click(p))
            widget.bind("<Double-Button-1>", lambda event, p=path: self._on_library_row_double_click(event, p))
            widget.bind("<Button-3>", lambda event, p=path: self._show_library_menu(event, p))
        self._library_widgets.append(row)

    def _add_library_row(self, entry: dict, index: int) -> None:
        path = Path(entry["path"])
        exists = path.is_file()
        mods = self._mods_for_archive(str(path))
        is_synthetic = bool(entry.get("_synthetic"))
        child_items = list(entry.get("child_items", []) or [])
        is_expanded = str(path) in self._expanded_archive_paths
        update_hint = self._archive_update_hint(entry)
        component_groups: list[dict[str, object]] = []
        component_info = None
        if is_expanded and exists and child_items:
            try:
                component_info = self._get_archive_info(path)
                component_groups = self._archive_component_groups(component_info)
            except Exception as exc:
                log.warning("Could not inspect archive for inline bundle view: %s", exc)

        if mods and is_synthetic and exists:
            status = "Active"
        elif mods and is_synthetic and not exists:
            status = "Active*"
        else:
            status = "Missing" if not exists else "Active" if mods else "Inactive"
        if mods and all(not mod.enabled for mod in mods) and status == "Active":
            status = "Disabled"

        row = ctk.CTkFrame(
            self._library_list,
            fg_color="#213040" if str(path) == self._selected_library_path else "transparent",
            cursor="hand2" if exists or mods else "arrow",
        )
        row.grid(row=index, column=0, sticky="ew", pady=1)
        row.grid_columnconfigure(2, weight=1)

        selected_var = tk.BooleanVar(value=str(path) in self._selected_archive_paths)
        ctk.CTkCheckBox(
            row,
            text="",
            width=18,
            variable=selected_var,
            command=lambda value=str(path), var=selected_var: self._toggle_archive_selection(value, bool(var.get())),
        ).grid(row=0, column=0, rowspan=3, sticky="nw", padx=(8, 2), pady=(8, 4))

        color = {
            "Inactive": "#3498db",
            "Active": "#2d8a4e",
            "Disabled": "#f39c12",
            "Active*": "#f39c12",
            "Missing": "#c0392b",
        }.get(status, "#95a5a6")
        badge = ctk.CTkLabel(row, text=status, text_color=color, width=58, anchor="w", font=self.app.ui_font("small"))
        badge.grid(row=0, column=1, sticky="w", padx=(4, 4), pady=(5 + self.app.ui_tokens.row_pad_y, 1))
        name = ctk.CTkLabel(
            row,
            text=self._display_name(entry.get("name", path.stem), max_len=max(24, self.app.ui_tokens.compact_name_len - 6)),
            anchor="w",
            font=self.app.ui_font("row_title"),
            text_color="#ffffff" if exists else "#777777",
        )
        name.grid(row=0, column=2, sticky="w", padx=4, pady=(5 + self.app.ui_tokens.row_pad_y, 1))

        type_label = str(entry.get("archive_type", "Unknown")).title()
        total_files = int(entry.get("total_files", 0) or 0)
        category_label = self._install_kind_label(str(entry.get("install_kind", "standard_mod"))) or {
            "framework_runtime": "Framework Runtime",
            "framework_mod": "Framework-Dependent Mod",
        }.get(str(entry.get("content_category", "standard_mod")), "")
        details = " | ".join(
            part for part in [
                self._source_kind_label(entry),
                type_label,
                category_label,
                f"{total_files} files" if total_files else "",
                f"Active On: {self._installed_to_text(mods)}",
                "Not tracked" if is_synthetic else "",
            ] if part
        )
        detail_label = ctk.CTkLabel(
            row, text=details, anchor="w", text_color="#95a5a6", wraplength=self.app.ui_tokens.panel_wrap, font=self.app.ui_font("small")
        )
        detail_label.grid(row=1, column=1, columnspan=2, sticky="ew", padx=9, pady=(0, 1))
        footer_text = self._last_action_text(str(path))
        if entry.get("dependency_warnings"):
            footer_text += " | dependency review recommended"
        if update_hint:
            footer_text += " | possible update available"
        action_label = ctk.CTkLabel(row, text=footer_text, anchor="w", text_color="#6f7a81", font=self.app.ui_font("tiny"))
        action_label.grid(row=2, column=1, columnspan=2, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))

        if child_items:
            expand_btn = ctk.CTkButton(
                row,
                        text="v" if is_expanded else ">",
                width=28,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._toggle_archive_expanded(value),
            )
            expand_btn.grid(row=0, column=3, rowspan=3, padx=(0, 6), pady=6)

        if is_synthetic and exists:
            action_btn = ctk.CTkButton(
                row,
                text="Add",
                width=64,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._track_in_library(value),
            )
            action_btn.grid(row=0, column=4, rowspan=3, padx=(6, 9), pady=6)
        elif not is_synthetic:
            action_btn = ctk.CTkButton(
                row,
                text="Remove",
                width=76,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._remove_from_library(value),
            )
            action_btn.grid(row=0, column=4, rowspan=3, padx=(6, 9), pady=6)

        if is_expanded and child_items:
            if component_groups:
                selected_keys = self._archive_component_selections.get(str(path), set())
                for child_index, group in enumerate(component_groups[:12], start=3):
                    child_row = ctk.CTkFrame(row, fg_color="#27323a")
                    child_row.grid(row=child_index, column=1, columnspan=4, sticky="ew", padx=(20, 9), pady=(0, 2))
                    child_row.grid_columnconfigure(1, weight=1)
                    selection_key = str(group.get("selection_key", ""))
                    selectable = bool(group.get("selectable", True))
                    selected_var = tk.BooleanVar(value=selection_key in selected_keys)
                    ctk.CTkCheckBox(
                        child_row,
                        text="",
                        width=18,
                        variable=selected_var,
                        state="normal" if selectable else "disabled",
                        command=lambda archive_key=str(path), key=selection_key, var=selected_var: self._toggle_archive_component_selection(archive_key, key, bool(var.get())),
                    ).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(8, 4), pady=(8, 4))
                    child_title = ctk.CTkLabel(
                        child_row,
                        text=str(group["label"]),
                        anchor="w",
                        justify="left",
                        text_color="#ffffff",
                        font=self.app.ui_font("small"),
                    )
                    child_title.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(6, 1))
                    child_subtitle = ctk.CTkLabel(
                        child_row,
                        text=f"Active: {self._component_targets_text(mods, group)}",
                        anchor="w",
                        justify="left",
                        text_color="#95a5a6",
                        font=self.app.ui_font("tiny"),
                    )
                    child_subtitle.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
                    for widget in (child_row, child_title, child_subtitle):
                        widget.bind(
                            "<Button-3>",
                            lambda event, current=path, current_info=component_info, current_group=group: self._show_archive_component_menu(
                                event,
                                current,
                                current_info,
                                current_group,
                            ),
                        )

                action_row = ctk.CTkFrame(row, fg_color="transparent")
                action_row.grid(row=min(len(component_groups), 12) + 3, column=1, columnspan=4, sticky="w", padx=(20, 9), pady=(2, 6))
                ctk.CTkButton(
                    action_row,
                    text="Install Checked",
                    width=126,
                    height=self.app.ui_tokens.compact_button_height,
                    font=self.app.ui_font("body"),
                    state="normal" if component_info and self._supports_selected_child_install(component_info) else "disabled",
                    command=lambda archive_path=path, info=component_info, groups=component_groups: self._install_archive_components(
                        archive_path,
                        info,
                        self._selected_component_entry_paths(set(self._archive_component_selections.get(str(archive_path), set())), groups),
                    ),
                ).pack(side="left", padx=(0, 6))
                ctk.CTkButton(
                    action_row,
                    text="Uninstall Checked",
                    width=138,
                    height=self.app.ui_tokens.compact_button_height,
                    font=self.app.ui_font("body"),
                    fg_color="#555555",
                    hover_color="#666666",
                    command=lambda archive_path=path, groups=component_groups: self._uninstall_archive_components(
                        archive_path,
                        self._selected_component_entry_paths(set(self._archive_component_selections.get(str(archive_path), set())), groups),
                    ),
                ).pack(side="left")
                if len(component_groups) > 12:
                    more_label = ctk.CTkLabel(
                        row,
                        text=f"+ {len(component_groups) - 12} more pak item(s). Use Inspect for the full list.",
                        anchor="w",
                        justify="left",
                        text_color="#95a5a6",
                        font=self.app.ui_font("small"),
                    )
                    more_label.grid(row=min(len(component_groups), 12) + 4, column=1, columnspan=4, sticky="ew", padx=(24, 9), pady=(0, 6))
            else:
                for child_index, child_name in enumerate(child_items[:12], start=3):
                    child_label = ctk.CTkLabel(
                        row,
                        text=f"â€¢ {child_name}",
                        anchor="w",
                        justify="left",
                        text_color="#c1c7cd",
                        font=self.app.ui_font("small"),
                    )
                    child_label.grid(row=child_index, column=1, columnspan=4, sticky="ew", padx=(24, 9), pady=(0, 2))
                if len(child_items) > 12:
                    more_label = ctk.CTkLabel(
                        row,
                        text=f"+ {len(child_items) - 12} more item(s). Use Inspect for the full list.",
                        anchor="w",
                        justify="left",
                        text_color="#95a5a6",
                        font=self.app.ui_font("small"),
                    )
                    more_label.grid(row=15, column=1, columnspan=4, sticky="ew", padx=(24, 9), pady=(0, 6))

        for widget in (row, badge, name, detail_label, action_label):
            widget.bind("<Button-1>", lambda _event, p=path: self._on_library_row_click(p))
            widget.bind("<Double-Button-1>", lambda event, p=path: self._on_library_row_double_click(event, p))
            widget.bind("<Button-3>", lambda event, p=path: self._show_library_menu(event, p))
        self._library_widgets.append(row)

    def _remove_from_library(self, path_str: str) -> None:
        mods = self._mods_for_archive(path_str)
        if mods and not self.app.confirm_action(
            "bulk",
            "Remove from Library",
            "Remove this source from the inactive mod list?\n\n"
            "This does not uninstall the active mod. The install stays active and will remain visible in Active Mods.",
        ):
            return
        self._library = [entry for entry in self._library if entry.get("path") != path_str]
        if self._selected_library_path == path_str:
            self._selected_library_path = None
            self._clear_details()
        self._save_library()
        self._refresh_library_ui()
        self._set_result(f"Removed {Path(path_str).name} from the inactive mod list.", level="info")

    def _toggle_archive_expanded(self, path_str: str) -> None:
        if path_str in self._expanded_archive_paths:
            self._expanded_archive_paths.remove(path_str)
            self._refresh_library_ui(refresh_applied=False)
            return
        archive_path = Path(path_str)
        entry = self._library_entry(path_str)
        if archive_path.is_file() and (entry is None or not entry.get("child_items")):
            try:
                info = self._get_archive_info(archive_path)
                self._update_library_entry(archive_path, info)
            except Exception as exc:
                log.warning("Could not inspect archive for expansion: %s", exc)
        self._expanded_archive_paths.add(path_str)
        self._refresh_library_ui(refresh_applied=False)

    def _toggle_mod_expanded(self, mod_id: str) -> None:
        if mod_id in self._expanded_mod_ids:
            self._expanded_mod_ids.remove(mod_id)
        else:
            self._expanded_mod_ids.add(mod_id)
        self._refresh_applied_ui()

    def _track_in_library(self, path_str: str) -> None:
        archive_path = Path(path_str)
        if not archive_path.is_file():
            messagebox.showerror("Source Missing", f"The source file is no longer available:\n{path_str}")
            return
        if archive_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            managed_path, archive_hash, reused = self._manager_owned_archive(archive_path)
            self._add_to_library(
                managed_path,
                name=archive_path.stem,
                source_kind="archive",
                original_files=[str(archive_path)],
                archive_hash=archive_hash,
                original_path=str(archive_path),
                manager_owned=True,
            )
            archive_path = managed_path
            if reused:
                self._set_result(f"Reused existing library copy for {archive_path.name}.", level="info")
        else:
            self._add_to_library(archive_path)
        self._refresh_library_ui()
        self._set_result(f"Added {archive_path.name} to the inactive mod list.", level="success")

    def _show_library_menu(self, event, archive_path: Path) -> None:
        menu = tk.Menu(self, tearoff=0)
        if archive_path.is_file():
            install_menu = self._build_install_menu(menu, archive_path)
            entry = self._library_entry(str(archive_path)) or {}
            install_label = {
                "ue4ss_runtime": "Install UE4SS Runtime",
                "ue4ss_mod": "Install UE4SS Mod",
                "rcon_mod": "Install RCON Mod",
                "windrose_plus": "Install WindrosePlus",
            }.get(str(entry.get("install_kind", "standard_mod")), "Install")
            menu.add_cascade(label=install_label, menu=install_menu)
            selected_archives = self._selected_archive_context(archive_path)
            if len(selected_archives) > 1:
                bulk_menu = self._build_install_menu(menu, selected_archives, include_hosted=False)
                menu.add_cascade(label="Install Selected", menu=bulk_menu)
        if self._mods_for_archive(str(archive_path)):
            menu.add_separator()
            menu.add_command(label="Reinstall", command=lambda p=archive_path: self._on_reinstall_for_archive(p))
            menu.add_command(label="Uninstall", command=lambda p=archive_path: self._on_uninstall_for_archive(p))
            menu.add_command(label="Repair", command=lambda p=archive_path: self._on_repair_for_archive(p))
        menu.add_separator()
        menu.add_command(label="Inspect", command=lambda: self._inspect_archive(archive_path))
        if archive_path.is_file():
            menu.add_command(label="Open Source Folder", command=lambda p=archive_path: self._open_archive_folder(p))
        if any(entry.get("path") == str(archive_path) for entry in self._library):
            menu.add_command(label="Remove from Library", command=lambda: self._remove_from_library(str(archive_path)))
        elif archive_path.is_file():
            menu.add_command(label="Add to Library", command=lambda: self._track_in_library(str(archive_path)))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_library_row_click(self, archive_path: Path) -> str:
        if self._single_click_job is not None:
            self.after_cancel(self._single_click_job)
        self._pending_click_path = archive_path
        self._single_click_job = self.after(220, self._flush_single_click)
        return "break"

    def _on_library_row_double_click(self, event, archive_path: Path) -> str:
        if self._single_click_job is not None:
            self.after_cancel(self._single_click_job)
            self._single_click_job = None
            self._pending_click_path = None
        self._load_archive(archive_path)
        if archive_path.is_file():
            install_menu = self._build_install_menu(self, archive_path)
            try:
                install_menu.tk_popup(event.x_root, event.y_root)
            finally:
                install_menu.grab_release()
        return "break"

    def _flush_single_click(self) -> None:
        path = self._pending_click_path
        self._single_click_job = None
        self._pending_click_path = None
        if path is not None:
            self._load_archive(path)

    def _build_install_menu(self, parent, archive_path: Path | list[Path], *, include_hosted: bool = True) -> tk.Menu:
        archive_paths = [archive_path] if isinstance(archive_path, Path) else list(archive_path)
        menu = tk.Menu(parent, tearoff=0)
        install_kinds = [self._install_kind_for_archive_path(path) for path in archive_paths]
        for key, label, _detail in _INSTALL_PRESETS:
            if not include_hosted and key == "hosted":
                continue
            if not self._install_preset_allowed_for_kinds(key, install_kinds):
                continue
            menu.add_command(
                label=label,
                command=lambda paths=tuple(archive_paths), preset=key: self._install_archives_with_preset(
                    [Path(path) for path in paths],
                    preset,
                ),
            )
        return menu

    def _install_kind_for_archive_path(self, archive_path: Path) -> str:
        entry = self._library_entry(str(archive_path))
        if entry is not None and entry.get("install_kind"):
            return str(entry.get("install_kind"))
        if archive_path.is_file():
            try:
                return self._get_archive_info(archive_path).install_kind
            except Exception:
                return "standard_mod"
        return "standard_mod"

    @staticmethod
    def _install_preset_allowed_for_kinds(preset_key: str, install_kinds: list[str]) -> bool:
        if any(is_server_only_framework_install_kind(kind) for kind in install_kinds):
            return preset_key not in {"client", "client_local", "client_dedicated"}
        return True

    def _install_archives_with_preset(self, archive_paths: list[Path], preset_key: str) -> None:
        if len(archive_paths) == 1:
            self._install_path_with_preset(archive_paths[0], preset_key)
            return
        self._install_archive_batch(archive_paths, preset_key)

    def _selected_archive_context(self, archive_path: Path) -> list[Path]:
        if str(archive_path) in self._selected_archive_paths and len(self._selected_archive_paths) > 1:
            return self._selected_archives()
        return [archive_path] if archive_path.is_file() else []

    def _selected_applied_context(
        self,
        *,
        mod: Optional[ModInstall] = None,
        live_bundle_id: Optional[str] = None,
    ) -> tuple[list[ModInstall], list[tuple[str, list[Path | str]]]]:
        selection_count = len(self._selected_mod_ids) + len(self._selected_live_files)
        if mod is not None and mod.mod_id in self._selected_mod_ids and selection_count > 1:
            return self._selected_mods(), self._selected_live_items()
        if live_bundle_id is not None and live_bundle_id in self._selected_live_files and selection_count > 1:
            return self._selected_mods(), self._selected_live_items()
        if mod is not None:
            return [mod], []
        if live_bundle_id is not None:
            return [], [(live_bundle_id, self._resolve_live_file_paths(live_bundle_id))]
        return [], []

    def _select_archive_context(self, archive_path: Path, *, inspect_if_present: bool = True) -> None:
        self._selected_library_path = str(archive_path)
        if inspect_if_present and archive_path.is_file():
            self._load_archive(archive_path)
        else:
            self._refresh_library_ui()

    def _on_uninstall_for_archive(self, archive_path: Path) -> None:
        self._select_archive_context(archive_path, inspect_if_present=archive_path.is_file())
        self._on_uninstall()

    def _on_reinstall_for_archive(self, archive_path: Path) -> None:
        self._select_archive_context(archive_path, inspect_if_present=archive_path.is_file())
        self._on_reinstall()

    def _on_repair_for_archive(self, archive_path: Path) -> None:
        self._select_archive_context(archive_path, inspect_if_present=archive_path.is_file())
        self._on_repair()

    def _choose_install_preset(self, *, title: str, subtitle: str, include_hosted: bool = True) -> Optional[str]:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Choose Install Target")
        self.app.center_dialog(dialog, 460, 420)
        dialog.minsize(420, 360)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(dialog, text=title, font=self.app.ui_font("detail_title"), wraplength=400).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 6)
        )
        ctk.CTkLabel(
            dialog,
            text=subtitle,
            text_color="#95a5a6",
            font=self.app.ui_font("body"),
            wraplength=400,
            justify="left",
        ).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(0, 10)
        )

        result = {"value": None}

        def _accept(value: str) -> None:
            result["value"] = value
            dialog.destroy()

        options = ctk.CTkScrollableFrame(dialog)
        options.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        options.grid_columnconfigure(0, weight=1)
        row = 0
        for key, label, detail in _INSTALL_PRESETS:
            if key == "hosted" and not include_hosted:
                continue
            card = ctk.CTkFrame(options, fg_color="#2f2f2f")
            card.grid(row=row, column=0, sticky="ew", pady=3)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(
                card,
                text=label,
                anchor="w",
                width=220,
                height=self.app.ui_tokens.button_height,
                font=self.app.ui_font("body"),
                command=lambda value=key: _accept(value),
            ).grid(
                row=0, column=0, sticky="ew", padx=10, pady=(10, 4)
            )
            ctk.CTkLabel(
                card,
                text=detail,
                anchor="w",
                justify="left",
                wraplength=360,
                text_color="#95a5a6",
                font=self.app.ui_font("small"),
            ).grid(
                row=1, column=0, sticky="ew", padx=12, pady=(0, 10)
            )
            row += 1

        ctk.CTkButton(
            dialog,
            text="Cancel",
            width=120,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#444444",
            hover_color="#555555",
            command=dialog.destroy,
        ).grid(
            row=3, column=0, sticky="e", padx=16, pady=(0, 16)
        )
        self.wait_window(dialog)
        return result["value"]

    def _register_dnd(self) -> None:
        if not getattr(self.app, "_dnd_enabled", False):
            return
        try:
            for widget in (self._archive_panel, self._library_list, self._archive_hint_label):
                widget.drop_target_register("DND_Files")
                widget.dnd_bind("<<Drop>>", self._on_drop)
                widget.dnd_bind("<<DragEnter>>", self._on_drag_enter)
                widget.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            log.info("Drag-and-drop registered on Mods tab")
        except Exception as exc:
            log.warning("Could not register drag-and-drop: %s", exc)

    def _on_drag_enter(self, _event) -> None:
        self._archive_panel.configure(border_color="#2d8a4e")
        self._archive_hint_label.configure(text_color="#2d8a4e")

    def _on_drag_leave(self, _event) -> None:
        self._archive_panel.configure(border_color="#3b3b3b")
        self._archive_hint_label.configure(text_color="#95a5a6")

    def _on_drop(self, event) -> None:
        self._archive_panel.configure(border_color="#3b3b3b")
        self._archive_hint_label.configure(text_color="#95a5a6")
        imported, warnings = self._import_source_paths(self._parse_drop_data(event.data))
        if not imported:
            warning_text = " ".join(warnings[:2]) if warnings else "The drop did not contain a supported mod file."
            self._set_result(warning_text, level="warning")
            return
        self._save_library()
        self._refresh_library_ui()
        if len(imported) == 1:
            self._load_archive(imported[0])
        suffix = " " + " ".join(warnings[:2]) if warnings else ""
        self._set_result(f"Added {len(imported)} inactive mod(s).{suffix}", level="success" if not warnings else "warning")

    def _parse_drop_data(self, data: str) -> list[Path]:
        paths: list[Path] = []
        data = data.strip()
        if not data:
            return paths
        if "{" in data:
            import re

            for match in re.finditer(r"\{([^}]+)\}", data):
                paths.append(Path(match.group(1)))
            remaining = re.sub(r"\{[^}]+\}", "", data).strip()
            for part in remaining.split():
                if part:
                    paths.append(Path(part))
        else:
            for part in data.split("\n"):
                part = part.strip()
                if part:
                    paths.append(Path(part))
        return paths

    def _on_browse(self) -> None:
        paths = filedialog.askopenfilenames(title="Select Mod File(s)", filetypes=_FILETYPES)
        if not paths:
            return
        valid, warnings = self._import_source_paths([Path(path) for path in paths])
        self._save_library()
        self._refresh_library_ui()
        if len(valid) == 1:
            self._load_archive(valid[0])
        if valid:
            suffix = " " + " ".join(warnings[:2]) if warnings else ""
            self._set_result(f"Added {len(valid)} inactive mod(s).{suffix}", level="success" if not warnings else "warning")
        elif warnings:
            self._set_result(" ".join(warnings[:2]), level="warning")

    def _load_archive(self, archive_path: Path, *, refresh_only: bool = False) -> None:
        archive_str = str(archive_path)
        if self._selected_library_path != archive_str:
            self._selected_library_path = archive_str
            self._refresh_library_selection_styles()
        installed_mods = self._mods_for_archive(str(archive_path))
        library_entry = self._library_entry(archive_str)
        display_name = str(library_entry.get("name") or archive_path.stem) if library_entry else archive_path.stem
        try:
            info = self._get_archive_info(archive_path)
        except Exception as exc:
            self._current_info = None
            self._detail_header.configure(text=self._compact_name(display_name or archive_path.name))
            self._detail_meta.configure(
                text="\n".join(
                    [
                        f"Active On: {self._installed_to_text(installed_mods)}",
                        f"Source: {archive_path.name}",
                        f"Last Action: {self._last_action_text(str(archive_path))}",
                        f"Could not inspect archive: {exc}",
                    ]
                )
            )
            self._set_textbox(self._installed_box, self._installed_text(installed_mods))
            self._set_textbox(
                self._review_box,
                "Source details are unavailable. Re-import this mod to inspect, reinstall, or repair this install.",
            )
            self._set_textbox(
                self._preview_box,
                "Source contents are unavailable because the source file is missing or could not be read.",
            )
            return

        self._current_info = info
        if self._update_library_entry(archive_path, info):
            self._refresh_library_ui(refresh_applied=False)
        meta_parts = [
            info.archive_type.value.replace("_", " ").title(),
            f"{info.total_files} files",
            f"Active On: {self._installed_to_text(installed_mods)}",
        ]
        self._detail_header.configure(text=self._compact_name(display_name))
        self._detail_meta.configure(
            text="\n".join(
                [
                    " | ".join(part for part in meta_parts if part),
                    f"Source: {archive_path.name}",
                    f"Last Action: {self._last_action_text(str(archive_path))}",
                ]
            )
        )
        self._mod_name_var.set(self._compact_name(display_name))

        self._set_textbox(self._installed_box, self._installed_text(installed_mods))
        self._set_textbox(self._review_box, self._build_install_review(info))
        self._set_textbox(self._preview_box, self._preview_text(info))
        if not refresh_only:
            log.info("Inspected archive: %s", archive_path.name)

    def _clear_details(self) -> None:
        self._current_info = None
        self._detail_header.configure(text="Select a mod")
        self._detail_meta.configure(text="")
        self._mod_name_var.set("")
        self._set_textbox(self._installed_box, "")
        self._set_textbox(self._review_box, "")
        self._set_textbox(self._preview_box, "")

    def _prompt_variant_choice(self, info: ArchiveInfo) -> Optional[str]:
        variant_names = [name for group in info.variant_groups for name in group.variant_names]
        if not variant_names:
            return None
        if len(variant_names) == 1:
            return variant_names[0]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Choose Variant")
        self.app.center_dialog(dialog, 460, 520)
        dialog.minsize(420, 360)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            dialog,
            text="Choose a variant",
            font=self.app.ui_font("detail_title"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(
            dialog,
            text=Path(info.archive_path).name,
            text_color="#95a5a6",
            wraplength=400,
            justify="left",
            font=self.app.ui_font("body"),
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        choice_var = tk.StringVar(value=variant_names[0])
        options = ctk.CTkScrollableFrame(dialog)
        options.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        options.grid_columnconfigure(0, weight=1)
        for name in variant_names:
            ctk.CTkRadioButton(
                options,
                text=name,
                variable=choice_var,
                value=name,
                font=self.app.ui_font("body"),
            ).grid(sticky="w", padx=6, pady=4)

        result = {"value": None}

        def _accept() -> None:
            result["value"] = choice_var.get()
            dialog.destroy()

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        ctk.CTkButton(
            buttons, text="Use Variant", width=120, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), command=_accept
        ).pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#444444",
            hover_color="#555555",
            command=dialog.destroy,
        ).pack(side="right")
        self.wait_window(dialog)
        return result["value"]

    def _installed_text(self, mods: list[ModInstall]) -> str:
        if not mods:
            return "This mod is not currently active anywhere."
        lines: list[str] = []
        for mod in mods:
            target_text = summarize_target_values(mod.targets)
            lines.append(f"{self._compact_name(mod.display_name)} [{target_text}] - {'enabled' if mod.enabled else 'disabled'}")
            if mod.selected_variant:
                lines.append(f"  variant: {mod.selected_variant}")
            lines.append(f"  files: {mod.file_count}")
            lines.append(f"  source: {Path(mod.source_archive).name}")
            lines.append("")
        return "\n".join(lines).strip()

    def _build_install_review(self, info: ArchiveInfo) -> str:
        mod_name = self._mod_name_var.get().strip() or Path(info.archive_path).stem
        selected_variant = self._selected_variant()
        preset_targets = [
            ("Client only", [InstallTarget.CLIENT]),
            ("Client + Local Server", [InstallTarget.CLIENT, InstallTarget.SERVER]),
            ("Client + Dedicated Server", [InstallTarget.CLIENT, InstallTarget.DEDICATED_SERVER]),
            ("Local Server only", [InstallTarget.SERVER]),
            ("Dedicated Server only", [InstallTarget.DEDICATED_SERVER]),
        ]
        lines: list[str] = []
        for label, targets in preset_targets:
            warnings: list[str] = []
            conflict_count = 0
            for target in targets:
                plan = plan_deployment(info, self.app.paths, target, selected_variant, mod_name)
                if not plan.valid:
                    warnings.append(f"{self._target_label(target)}: {'; '.join(plan.warnings[:2]) if plan.warnings else 'Not available'}")
                    continue
                conflict_report = check_plan_conflicts(plan, self.app.manifest)
                if conflict_report.has_conflicts:
                    conflict_count += len(conflict_report.conflicts)
            if warnings:
                lines.append(f"{label}: {' | '.join(warnings)}")
            elif conflict_count:
                lines.append(f"{label}: {conflict_count} managed conflict(s)")
            else:
                lines.append(f"{label}: ready")
        lines.append("Hosted Server only: open the inactive mod row menu or double-click the mod to launch the hosted upload flow.")
        if info.warnings:
            lines.append("")
            lines.append("Source warnings:")
            lines.extend(f"- {warning}" for warning in info.warnings)
        if info.dependency_warnings:
            lines.append("")
            lines.append("Dependency review:")
            lines.extend(f"- {warning}" for warning in info.dependency_warnings)
        return "\n".join(lines)

    def _preview_text(self, info: ArchiveInfo) -> str:
        lines = [
            f"Source:      {Path(info.archive_path).name}",
            f"Source Path: {info.archive_path}",
            f"Type:        {info.archive_type.value}",
            f"Category:    {info.content_category}",
            f"Install Kind:{info.install_kind}",
            f"Files:       {info.total_files}",
            "",
        ]
        if info.pak_entries:
            lines.append("PAK files:")
            lines.extend(f"  {PurePosixPath(entry.path).name}" for entry in info.pak_entries)
        if info.companion_entries:
            lines.append("")
            lines.append("Companion files:")
            lines.extend(f"  {PurePosixPath(entry.path).name}" for entry in info.companion_entries)
        if info.loose_entries:
            lines.append("")
            lines.append("Loose files:")
            lines.extend(f"  {entry.path}" for entry in info.loose_entries[:30])
        if info.variant_groups:
            lines.append("")
            lines.append("Variant groups:")
            for group in info.variant_groups:
                lines.append(f"  {group.base_name}")
                for variant in group.variants:
                    lines.append(f"    - {PurePosixPath(variant.path).name}")
        return "\n".join(lines)

    @staticmethod
    def _archive_child_names(info: ArchiveInfo) -> list[str]:
        return [str(group["label"]) for group in ModsTab._archive_component_groups(info)]

    @staticmethod
    def _archive_component_groups(info: ArchiveInfo) -> list[dict[str, object]]:
        grouped: dict[str, dict[str, object]] = {}

        for entry in info.pak_entries:
            posix = PurePosixPath(entry.path)
            stem = posix.stem
            grouped.setdefault(
                stem,
                {
                    "label": posix.name,
                    "selection_key": entry.path,
                    "entry_paths": [],
                    "display_paths": [],
                    "kind": "asset",
                    "selectable": True,
                },
            )
            grouped[stem]["entry_paths"].append(entry.path)
            grouped[stem]["display_paths"].append(posix.name)
            grouped[stem]["label"] = posix.name
            grouped[stem]["selection_key"] = entry.path

        for entry in info.companion_entries:
            posix = PurePosixPath(entry.path)
            stem = posix.stem
            grouped.setdefault(
                stem,
                {
                    "label": posix.name,
                    "selection_key": entry.path,
                    "entry_paths": [],
                    "display_paths": [],
                    "kind": "asset",
                    "selectable": True,
                },
            )
            grouped[stem]["entry_paths"].append(entry.path)
            grouped[stem]["display_paths"].append(posix.name)

        return sorted(grouped.values(), key=lambda item: str(item["label"]).lower())

    @staticmethod
    def _mod_component_groups(mod: ModInstall) -> list[dict[str, object]]:
        component_map = mod.component_map or {}
        if not component_map:
            component_map = {Path(path).name: [path] for path in mod.installed_files}

        grouped: dict[str, dict[str, object]] = {}
        for entry_path, installed_paths in component_map.items():
            posix = PurePosixPath(entry_path)
            suffix = posix.suffix.lower()
            group_key = posix.stem if suffix in {".pak", ".utoc", ".ucas"} else entry_path
            group = grouped.setdefault(
                group_key,
                {
                    "label": posix.name,
                    "selection_key": entry_path,
                    "entry_paths": [],
                    "installed_paths": [],
                },
            )
            group["entry_paths"].append(entry_path)
            group["installed_paths"].extend(list(installed_paths))
            if suffix == ".pak":
                group["label"] = posix.name
                group["selection_key"] = entry_path
        values = sorted(grouped.values(), key=lambda item: str(item["label"]).lower())
        pak_values = [item for item in values if str(item.get("label", "")).lower().endswith(".pak")]
        return pak_values or values

    @classmethod
    def _supports_selected_child_install(cls, info: ArchiveInfo) -> bool:
        groups = cls._archive_component_groups(info)
        selectable = [group for group in groups if bool(group.get("selectable"))]
        return len(selectable) >= 2 and not info.loose_entries

    def _toggle_archive_component_selection(self, archive_path: str, selection_key: str, selected: bool) -> None:
        selected_keys = self._archive_component_selections.setdefault(archive_path, set())
        if selected:
            selected_keys.add(selection_key)
        else:
            selected_keys.discard(selection_key)
        if not selected_keys:
            self._archive_component_selections.pop(archive_path, None)

    def _toggle_mod_component_selection(self, mod_id: str, selection_key: str, selected: bool) -> None:
        selected_keys = self._mod_component_selections.setdefault(mod_id, set())
        if selected:
            selected_keys.add(selection_key)
        else:
            selected_keys.discard(selection_key)
        if not selected_keys:
            self._mod_component_selections.pop(mod_id, None)

    def _selected_component_entry_paths(self, selection_keys: set[str], groups: list[dict[str, object]]) -> set[str]:
        selected_entries: set[str] = set()
        for group in groups:
            if str(group.get("selection_key", "")) in selection_keys:
                selected_entries.update(str(path) for path in group.get("entry_paths", []))
        return selected_entries

    def _component_targets_text(self, mods: list[ModInstall], group: dict[str, object]) -> str:
        targets: set[str] = set()
        group_entries = {str(path) for path in group.get("entry_paths", [])}
        for mod in mods:
            component_entries = set(mod.component_map.keys()) if mod.component_map else set()
            if component_entries and component_entries.intersection(group_entries):
                targets.update(self._effective_targets(mod))
        if not targets:
            return "Not active"
        return summarize_target_values(sorted(targets))

    def _open_inspect_dialog(self, archive_path: Path, info: ArchiveInfo, installed_mods: list[ModInstall]) -> None:
        library_entry = self._library_entry(str(archive_path))
        display_name = str(library_entry.get("name") or archive_path.stem) if library_entry else archive_path.stem
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Inspect Mod - {self._compact_name(display_name)}")
        self.app.center_dialog(dialog, 860, 720)
        dialog.minsize(760, 620)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=self._compact_name(display_name), font=self.app.ui_font("detail_title")).grid(
            row=0, column=0, sticky="w"
        )
        meta = self._archive_metadata(str(archive_path))
        meta_bits = [
            info.archive_type.value.replace("_", " ").title(),
            f"{info.total_files} files",
            summarize_target_values([target for mod in installed_mods for target in mod.targets]) if installed_mods else "Not active",
        ]
        ctk.CTkLabel(
            header,
            text=" | ".join(bit for bit in meta_bits if bit),
            text_color="#95a5a6",
            font=self.app.ui_font("body"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

        body = ctk.CTkScrollableFrame(dialog)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)

        overview = ctk.CTkFrame(body)
        overview.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        overview.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(overview, text="Mod Source Overview", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        overview_text = [
            f"Source: {archive_path.name}",
            f"Type: {info.archive_type.value.replace('_', ' ').title()}",
            f"Suggested destination: {', '.join(info.likely_destinations) if info.likely_destinations else (info.suggested_target or 'Review recommended')}",
            f"Category: {info.content_category.replace('_', ' ').title()}",
            f"Install kind: {self._install_kind_label(info.install_kind) or info.install_kind.replace('_', ' ').title()}",
        ]
        update_hint = self._archive_update_hint(self._library_entry(str(archive_path)) or {"path": str(archive_path), "name": archive_path.stem, "metadata": meta.to_dict()})
        if update_hint:
            overview_text.append(update_hint)
        if info.framework_name:
            overview_text.append(f"Framework: {info.framework_name}")
        if info.root_prefix:
            overview_text.append(f"Wrapper folder: {info.root_prefix}")
        ctk.CTkLabel(
            overview,
            text="\n".join(overview_text),
            justify="left",
            anchor="w",
            font=self.app.ui_font("body"),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        warnings_card = ctk.CTkFrame(body)
        warnings_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        warnings_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(warnings_card, text="Warnings and Review", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        warning_lines = list(info.warnings) + list(info.dependency_warnings)
        if not warning_lines:
            warning_lines = ["No immediate warnings. Review the install target before applying."]
        ctk.CTkLabel(
            warnings_card,
            text="\n".join(f"- {line}" for line in warning_lines),
            justify="left",
            anchor="w",
            wraplength=760,
            text_color="#c1c7cd",
            font=self.app.ui_font("body"),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        installed_card = ctk.CTkFrame(body)
        installed_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        installed_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(installed_card, text="Installed Targets", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        ctk.CTkLabel(
            installed_card,
            text=self._installed_text(installed_mods),
            justify="left",
            anchor="w",
            wraplength=760,
            font=self.app.ui_font("body"),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        child_card = ctk.CTkFrame(body)
        child_card.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        child_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(child_card, text="Bundle Items", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        component_groups = self._archive_component_groups(info)
        selected_group_vars: dict[str, tk.BooleanVar] = {}
        for row_index, group in enumerate(component_groups, start=1):
            group_row = ctk.CTkFrame(child_card, fg_color="#2f2f2f")
            group_row.grid(row=row_index, column=0, sticky="ew", padx=12, pady=2)
            group_row.grid_columnconfigure(1, weight=1)
            selectable = bool(group.get("selectable"))
            value = tk.BooleanVar(value=selectable)
            selected_group_vars[str(group["label"])] = value
            ctk.CTkCheckBox(
                group_row,
                text="",
                width=18,
                variable=value,
                state="normal" if selectable else "disabled",
            ).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(8, 4), pady=(8, 4))
            ctk.CTkLabel(
                group_row,
                text=str(group["label"]),
                font=self.app.ui_font("row_title"),
                anchor="w",
            ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(6, 1))
            subtitle = " | ".join(str(path) for path in group.get("display_paths", []))
            if not selectable:
                subtitle += " | whole-bundle install only"
            ctk.CTkLabel(
                group_row,
                text=subtitle,
                anchor="w",
                wraplength=700,
                text_color="#95a5a6",
                font=self.app.ui_font("small"),
            ).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))

        metadata_card = ctk.CTkFrame(body)
        metadata_card.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        metadata_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(metadata_card, text="Metadata", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6)
        )
        metadata_fields = [
            ("Nexus URL", "nexus_mod_url"),
            ("Nexus Mod ID", "nexus_mod_id"),
            ("Nexus File ID", "nexus_file_id"),
            ("Version Tag", "version_tag"),
            ("Source Label", "source_label"),
            ("Author Label", "author_label"),
        ]
        metadata_vars: dict[str, ctk.StringVar] = {}
        for row_index, (label, key) in enumerate(metadata_fields, start=1):
            ctk.CTkLabel(metadata_card, text=label + ":", font=self.app.ui_font("body")).grid(
                row=row_index, column=0, sticky="w", padx=(12, 6), pady=4
            )
            var = ctk.StringVar(value=getattr(meta, key))
            metadata_vars[key] = var
            ctk.CTkEntry(metadata_card, textvariable=var, font=self.app.ui_font("body")).grid(
                row=row_index, column=1, sticky="ew", padx=(0, 12), pady=4
            )

        button_row = ctk.CTkFrame(body, fg_color="transparent")
        button_row.grid(row=5, column=0, sticky="ew", pady=(4, 14))

        def _save_metadata() -> None:
            metadata = ModMetadata(
                nexus_mod_url=metadata_vars["nexus_mod_url"].get().strip(),
                nexus_mod_id=metadata_vars["nexus_mod_id"].get().strip(),
                nexus_file_id=metadata_vars["nexus_file_id"].get().strip(),
                version_tag=metadata_vars["version_tag"].get().strip(),
                source_label=metadata_vars["source_label"].get().strip(),
                author_label=metadata_vars["author_label"].get().strip(),
            )
            self._save_archive_metadata(str(archive_path), metadata, sync_installs=True)
            self.refresh_view()
            self._set_result(f"Saved metadata for {archive_path.name}.", level="success")

        def _install_whole_bundle() -> None:
            preset = self._choose_install_preset(
                title=f"Install {archive_path.name}",
                subtitle="Choose the install target for the full bundle.",
            )
            if not preset:
                return
            selected_variant = self._prompt_variant_choice(info)
            if info.has_variants and not selected_variant:
                return
            mod_name = self._mod_name_var.get().strip() or self._compact_name(display_name)
            if self._run_install_preset(info, mod_name, preset, selected_variant):
                dialog.destroy()

        def _install_selected_children() -> None:
            selected_entries: set[str] = set()
            for group in component_groups:
                if selected_group_vars[str(group["label"])].get():
                    selected_entries.update(str(path) for path in group.get("entry_paths", []))
            if not selected_entries:
                self._set_result("Select one or more bundle items first.", level="info")
                return
            preset = self._choose_install_preset(
                title=f"Install Selected Items - {archive_path.name}",
                subtitle="Selected-child install is only used when the mod source structure looks safe for partial install.",
            )
            if not preset:
                return
            mod_name = self._mod_name_var.get().strip() or self._compact_name(display_name)
            if self._run_install_preset(info, mod_name, preset, None, selected_entries=selected_entries):
                dialog.destroy()

        save_btn = ctk.CTkButton(
            button_row,
            text="Save Metadata",
            width=120,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=_save_metadata,
        )
        save_btn.pack(side="left", padx=(0, 6))
        whole_btn = ctk.CTkButton(
            button_row,
            text="Install Whole Bundle",
            width=150,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=_install_whole_bundle,
        )
        whole_btn.pack(side="left", padx=6)
        child_btn = ctk.CTkButton(
            button_row,
            text="Install Selected Items",
            width=164,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            state="normal" if self._supports_selected_child_install(info) else "disabled",
            command=_install_selected_children,
        )
        child_btn.pack(side="left", padx=6)
        close_btn = ctk.CTkButton(
            button_row,
            text="Close",
            width=90,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=dialog.destroy,
        )
        close_btn.pack(side="right")
        open_btn = ctk.CTkButton(
            button_row,
            text="Open Source Folder",
            width=138,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=lambda p=archive_path: self._open_archive_folder(p),
        )
        open_btn.pack(side="right", padx=(0, 6))

        self.wait_window(dialog)

    @staticmethod
    def _target_enum_for_value(target: str) -> Optional[InstallTarget]:
        mapping = {
            "client": InstallTarget.CLIENT,
            "server": InstallTarget.SERVER,
            "dedicated_server": InstallTarget.DEDICATED_SERVER,
        }
        return mapping.get(target)

    def _install_archive_components(self, archive_path: Path, info: ArchiveInfo, selected_entries: set[str]) -> None:
        if not selected_entries:
            self._set_result("Select one or more pak items first.", level="info")
            return
        preset = self._choose_install_preset(
            title=f"Install Selected Items - {archive_path.name}",
            subtitle="Selected-child install is only used when the mod source structure looks safe for partial install.",
        )
        if not preset:
            return
        entry = self._library_entry(str(archive_path))
        display_name = str(entry.get("name") or archive_path.stem) if entry else archive_path.stem
        field_name = self._mod_name_var.get().strip() if self._selected_library_path == str(archive_path) else ""
        mod_name = field_name or self._compact_name(display_name)
        self._run_install_preset(info, mod_name, preset, None, selected_entries=selected_entries)

    def _uninstall_mod_components(self, mod: ModInstall, selected_entries: set[str]) -> bool:
        if not selected_entries:
            return False
        component_map = mod.component_map or {}
        target_paths: set[str] = set()
        for entry_path, installed_paths in component_map.items():
            if entry_path in selected_entries:
                target_paths.update(installed_paths)
        if not target_paths:
            return False

        removed: list[DeployedFile] = []
        restored_count = 0
        remaining_files: list[str] = []
        remaining_backup_map: dict[str, str] = {}
        remaining_component_map: dict[str, list[str]] = {}

        for entry_path, installed_paths in component_map.items():
            keep_paths: list[str] = []
            for file_path in installed_paths:
                canonical_path = self._canonical_installed_path(file_path)
                backup_path = mod.backup_map.get(str(canonical_path)) or mod.backup_map.get(file_path)
                if file_path in target_paths:
                    if Path(file_path).exists():
                        safe_delete(Path(file_path))
                    disabled = Path(file_path + ".disabled")
                    if disabled.exists():
                        safe_delete(disabled)
                    if backup_path and Path(backup_path).is_file():
                        canonical_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_path, canonical_path)
                        restored_count += 1
                    removed.append(
                        DeployedFile(
                            source_archive_path=entry_path,
                            dest_path=file_path,
                            backup_path=backup_path,
                        )
                    )
                else:
                    keep_paths.append(file_path)
                    remaining_files.append(file_path)
                    if backup_path:
                        remaining_backup_map[str(canonical_path)] = backup_path
            if keep_paths:
                remaining_component_map[entry_path] = keep_paths

        if not removed:
            return False

        mod.installed_files = remaining_files
        mod.backup_map = remaining_backup_map
        mod.component_map = remaining_component_map

        record = DeploymentRecord(
            mod_id=mod.mod_id,
            target=",".join(mod.targets),
            action="uninstall_component",
            display_name=mod.display_name,
            source_archive=mod.source_archive,
            files=removed,
            notes=f"Removed {len(removed)} file(s) from selected bundle items"
            + (f", restored {restored_count} originals" if restored_count else ""),
        )
        self.app.manifest.add_record(record)
        if mod.installed_files:
            self.app.manifest.update_mod(mod)
        else:
            self.app.manifest.remove_mod(mod.mod_id)
        return True

    def _uninstall_archive_components(self, archive_path: Path, selected_entries: set[str]) -> None:
        if not selected_entries:
            self._set_result("Select one or more pak items first.", level="info")
            return
        mods = self._mods_for_archive(str(archive_path))
        targets = [mod for mod in mods if set(mod.component_map.keys()).intersection(selected_entries)]
        if not targets:
            self._set_result("None of the selected pak items are currently installed.", level="info")
            return
        if not self.app.confirm_action(
            "destructive",
            "Uninstall Selected Items",
            f"Uninstall selected pak item(s) from {len(targets)} install(s)?",
        ):
            return
        removed = 0
        failed = 0
        for mod in targets:
            try:
                if self._uninstall_mod_components(mod, selected_entries):
                    removed += 1
            except Exception as exc:
                log.error("Component uninstall failed for %s: %s", mod.mod_id, exc)
                failed += 1
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self.refresh_view()
        self._set_result(
            f"Updated {removed} install(s)." + (f" {failed} failed." if failed else ""),
            level="success" if removed and not failed else "warning",
        )

    def _uninstall_selected_mod_components(self, mod: ModInstall) -> None:
        groups = self._mod_component_groups(mod)
        selected_keys = set(self._mod_component_selections.get(mod.mod_id, set()))
        selected_entries = self._selected_component_entry_paths(selected_keys, groups)
        if not selected_entries:
            self._set_result("Select one or more pak items first.", level="info")
            return
        self._uninstall_mod_component_group(mod, selected_entries, "selected pak item(s)")

    def _uninstall_mod_component_group(self, mod: ModInstall, selected_entries: set[str], item_label: str) -> None:
        if not selected_entries:
            self._set_result("Select one or more pak items first.", level="info")
            return
        if not self.app.confirm_action(
            "destructive",
            "Uninstall Selected Items",
            f"Uninstall {item_label} from '{mod.display_name}'?",
        ):
            return
        try:
            changed = self._uninstall_mod_components(mod, selected_entries)
        except Exception as exc:
            log.error("Selected component uninstall failed for %s: %s", mod.mod_id, exc)
            self._set_result(f"Could not uninstall selected items: {exc}", level="error")
            return
        if changed:
            self.app.refresh_installed_tab()
            self.app.refresh_backups_tab()
            self.refresh_view()
            self._set_result(f"Updated {mod.display_name}.", level="success")

    def _profile_preview_text(self, profile, comparison) -> str:
        lines = [
            f"Profile: {profile.name}",
            f"Matching: {len(comparison.matching)}",
            f"Install: {len(comparison.to_install)}",
            f"Uninstall: {len(comparison.to_uninstall)}",
            f"Missing archives: {len(comparison.missing_archives)}",
            "",
        ]
        if comparison.to_install:
            lines.append("Will install:")
            for entry in comparison.to_install[:12]:
                lines.append(
                    f"  {entry.display_name} [{summarize_target_values(entry.targets)}]"
                    + (f" | variant: {entry.selected_variant}" if entry.selected_variant else "")
                )
            lines.append("")
        if comparison.to_uninstall:
            lines.append("Will uninstall:")
            for mod in comparison.to_uninstall[:12]:
                lines.append(f"  {mod.display_name} [{summarize_target_values(mod.targets)}]")
            lines.append("")
        if comparison.missing_archives:
            lines.append("Missing source archives:")
            for entry in comparison.missing_archives[:12]:
                lines.append(f"  {entry.display_name} | {entry.source_archive}")
        return "\n".join(lines).strip()

    def _apply_profile(self, profile) -> None:
        comparison = self.app.profile_service.compare(profile, self.app.manifest.list_mods())
        preview = self._profile_preview_text(profile, comparison)
        if not self.app.confirm_action(
            "destructive",
            "Apply Profile",
            preview + "\n\nApply this profile now?",
        ):
            return

        installed = 0
        removed = 0
        failed: list[str] = []

        for entry in comparison.to_install:
            archive_path = Path(entry.source_archive)
            try:
                info = inspect_archive(archive_path)
            except Exception as exc:
                failed.append(f"{entry.display_name}: {exc}")
                continue

            selected_entries = set(entry.component_entries) if entry.component_entries else None
            for target_value in entry.targets:
                target_enum = self._target_enum_for_value(target_value)
                if target_enum is None:
                    continue
                try:
                    plan, error = self._prepare_install_target(
                        info,
                        entry.display_name,
                        target_enum,
                        entry.selected_variant or None,
                        selected_entries,
                    )
                except TypeError:
                    plan, error = self._prepare_install_target(
                        info,
                        entry.display_name,
                        target_enum,
                        entry.selected_variant or None,
                    )
                if plan is None:
                    failed.append(f"{entry.display_name}: {error}")
                    continue
                try:
                    mod, record = self.app.installer.install(plan)
                    mod.metadata = entry.metadata
                    self.app.manifest.add_mod(mod)
                    self.app.manifest.add_record(record)
                    installed += 1
                except Exception as exc:
                    failed.append(f"{entry.display_name}: {exc}")

        for mod in comparison.to_uninstall:
            try:
                record = self.app.installer.uninstall(mod)
                self.app.manifest.add_record(record)
                self.app.manifest.remove_mod(mod.mod_id)
                removed += 1
            except Exception as exc:
                failed.append(f"{mod.display_name}: {exc}")

        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self.refresh_view()
        if failed:
            self._set_result(
                f"Profile applied with warnings. Installed {installed}, removed {removed}, failed {len(failed)} item(s).",
                level="warning",
            )
        else:
            self._set_result(f"Applied profile '{profile.name}'. Installed {installed}, removed {removed}.", level="success")

    def _open_profiles_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Profiles")
        self.app.center_dialog(dialog, 860, 620)
        dialog.minsize(760, 540)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(1, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(dialog, text="Profiles", font=self.app.ui_font("detail_title")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8)
        )

        left = ctk.CTkScrollableFrame(dialog, width=260)
        left.grid(row=1, column=0, sticky="nsw", padx=(16, 8), pady=(0, 16))
        left.grid_columnconfigure(0, weight=1)
        right = ctk.CTkFrame(dialog)
        right.grid(row=1, column=1, sticky="nsew", padx=(0, 16), pady=(0, 16))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        name_var = ctk.StringVar(value="")
        notes_var = ctk.StringVar(value="")
        selected = {"profile_id": None}

        ctk.CTkLabel(right, text="Name", font=self.app.ui_font("small")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 2))
        name_entry = ctk.CTkEntry(right, textvariable=name_var, font=self.app.ui_font("body"))
        name_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkLabel(right, text="Notes", font=self.app.ui_font("small")).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 2))
        notes_entry = ctk.CTkEntry(right, textvariable=notes_var, font=self.app.ui_font("body"))
        notes_entry.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 6))
        preview_box = ctk.CTkTextbox(right, font=self.app.ui_font("mono_small"))
        preview_box.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 8))
        preview_box.configure(state="disabled")

        def _set_preview(text: str) -> None:
            preview_box.configure(state="normal")
            preview_box.delete("1.0", "end")
            preview_box.insert("1.0", text)
            preview_box.configure(state="disabled")

        def _select_profile(profile_id: str) -> None:
            selected["profile_id"] = profile_id
            profile = self.app.profiles.get_profile(profile_id)
            if profile is None:
                return
            name_var.set(profile.name)
            notes_var.set(profile.notes)
            comparison = self.app.profile_service.compare(profile, self.app.manifest.list_mods())
            _set_preview(self._profile_preview_text(profile, comparison))

        def _refresh_profile_rows() -> None:
            for widget in left.winfo_children():
                widget.destroy()
            profiles = self.app.profiles.list_profiles()
            if not profiles:
                ctk.CTkLabel(
                    left,
                    text="No saved profiles yet.",
                    text_color="#95a5a6",
                    font=self.app.ui_font("small"),
                ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
                _set_preview("Save the current setup as a profile to compare and re-apply it later.")
                return
            for index, profile in enumerate(profiles):
                row = ctk.CTkFrame(left, fg_color="#213040" if profile.profile_id == selected["profile_id"] else "#2f2f2f")
                row.grid(row=index, column=0, sticky="ew", pady=2)
                row.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(row, text=profile.name, anchor="w", font=self.app.ui_font("row_title")).grid(
                    row=0, column=0, sticky="ew", padx=10, pady=(8, 2)
                )
                ctk.CTkLabel(
                    row,
                    text=f"{len(profile.entries)} item(s) | {profile.created_at[:19].replace('T', ' ')}",
                    anchor="w",
                    text_color="#95a5a6",
                    font=self.app.ui_font("small"),
                ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
                for widget in row.winfo_children() + [row]:
                    widget.bind("<Button-1>", lambda _event, value=profile.profile_id: _select_profile(value))

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

        def _save_current_profile() -> None:
            name = name_var.get().strip() or "New Profile"
            profile = self.app.profile_service.capture_current_state(
                name=name,
                mods=self.app.manifest.list_mods(),
                notes=notes_var.get().strip(),
            )
            existing = selected["profile_id"]
            if existing:
                profile.profile_id = existing
            self.app.profiles.upsert(profile)
            selected["profile_id"] = profile.profile_id
            _refresh_profile_rows()
            _select_profile(profile.profile_id)
            self._set_result(f"Saved profile '{profile.name}'.", level="success")

        def _compare_selected_profile() -> None:
            profile = self.app.profiles.get_profile(selected["profile_id"] or "")
            if profile is None:
                self._set_result("Choose a profile first.", level="info")
                return
            comparison = self.app.profile_service.compare(profile, self.app.manifest.list_mods())
            _set_preview(self._profile_preview_text(profile, comparison))

        def _apply_selected_profile() -> None:
            profile = self.app.profiles.get_profile(selected["profile_id"] or "")
            if profile is None:
                self._set_result("Choose a profile first.", level="info")
                return
            self._apply_profile(profile)
            _compare_selected_profile()

        def _delete_selected_profile() -> None:
            profile = self.app.profiles.get_profile(selected["profile_id"] or "")
            if profile is None:
                self._set_result("Choose a profile first.", level="info")
                return
            if not self.app.confirm_action(
                "destructive",
                "Delete Profile",
                f"Delete profile '{profile.name}'?",
            ):
                return
            self.app.profiles.remove(profile.profile_id)
            selected["profile_id"] = None
            name_var.set("")
            notes_var.set("")
            _refresh_profile_rows()
            self._set_result(f"Deleted profile '{profile.name}'.", level="info")

        ctk.CTkButton(actions, text="Save Current State", width=148, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), command=_save_current_profile).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Compare", width=96, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), command=_compare_selected_profile).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Apply", width=96, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), fg_color="#2d8a4e", hover_color="#236b3d", command=_apply_selected_profile).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Delete", width=96, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), fg_color="#c0392b", hover_color="#962d22", command=_delete_selected_profile).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Close", width=96, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), fg_color="#555555", hover_color="#666666", command=dialog.destroy).pack(side="right")

        _refresh_profile_rows()
        self.wait_window(dialog)

    def _selected_variant(self) -> Optional[str]:
        value = self._variant_var.get()
        return None if value == "(none)" else value

    @staticmethod
    def _install_preset_label(preset_key: str) -> str:
        for key, label, _detail in _INSTALL_PRESETS:
            if key == preset_key:
                return label
        return preset_key.replace("_", " ").title()

    @staticmethod
    def _install_targets_for_preset(preset_key: str) -> list[InstallTarget]:
        mapping = {
            "client": [InstallTarget.CLIENT],
            "client_local": [InstallTarget.CLIENT, InstallTarget.SERVER],
            "client_dedicated": [InstallTarget.CLIENT, InstallTarget.DEDICATED_SERVER],
            "local": [InstallTarget.SERVER],
            "dedicated": [InstallTarget.DEDICATED_SERVER],
        }
        return mapping.get(preset_key, [])

    def _prepare_install_target(
        self,
        info: ArchiveInfo,
        mod_name: str,
        target: InstallTarget,
        selected_variant: Optional[str],
        selected_entries: Optional[set[str]] = None,
    ):
        paths = self.app.paths
        if target in (InstallTarget.CLIENT, InstallTarget.BOTH) and not paths.client_root:
            return None, "Configure the client path in Settings first."
        if target in (InstallTarget.SERVER, InstallTarget.BOTH) and not paths.server_root:
            return None, "Configure the local server path in Settings first."
        if target == InstallTarget.DEDICATED_SERVER and not paths.dedicated_server_root:
            return None, "Configure the dedicated server path in Settings first."
        if is_server_only_framework_install_kind(info.install_kind) and target == InstallTarget.CLIENT:
            return None, f"{self._install_kind_label(info.install_kind) or 'This framework'} is server-only and should be installed to Local Server or Dedicated Server."
        plan = plan_deployment(info, paths, target, selected_variant, mod_name, selected_entries)
        if not plan.valid:
            return None, "\n".join(plan.warnings) if plan.warnings else "The install plan is not valid."
        if info.install_kind in {"ue4ss_mod", "windrose_plus"}:
            framework_root = {
                InstallTarget.CLIENT: paths.client_root,
                InstallTarget.SERVER: paths.server_root,
                InstallTarget.DEDICATED_SERVER: paths.dedicated_server_root,
            }.get(target)
            framework_state = detect_framework_state(framework_root)
            if not framework_state.get("ue4ss_runtime", False):
                plan.warnings.append("Likely depends on UE4SS, but that runtime was not detected for this target.")
        return plan, None

    def _run_install_preset(
        self,
        info: ArchiveInfo,
        mod_name: str,
        preset_key: str,
        selected_variant: Optional[str],
        selected_entries: Optional[set[str]] = None,
        *,
        quiet: bool = False,
        confirm_conflicts: Optional[bool] = None,
    ) -> bool:
        if preset_key == "hosted":
            self.app.open_remote_deploy(Path(info.archive_path))
            if not quiet:
                self._set_result(f"Opened the hosted upload flow for {Path(info.archive_path).name}.", level="info")
            return True

        targets = self._install_targets_for_preset(preset_key)
        if not targets:
            if not quiet:
                messagebox.showerror("Install Target Error", f"Unknown install preset: {preset_key}")
            return False
        if is_server_only_framework_install_kind(getattr(info, "install_kind", "standard_mod")) and InstallTarget.CLIENT in targets:
            if not quiet:
                messagebox.showerror(
                    "Install Target Error",
                    f"{self._install_kind_label(getattr(info, 'install_kind', 'standard_mod')) or 'This framework'} is server-only. Choose Local Server, Dedicated Server, or Hosted Server.",
                )
            return False

        prepared = []
        warnings: list[str] = []
        plan_warning_lines: list[str] = []
        conflict_lines: list[str] = []
        for target in targets:
            try:
                plan, error = self._prepare_install_target(
                    info,
                    mod_name,
                    target,
                    selected_variant,
                    selected_entries,
                )
            except TypeError:
                plan, error = self._prepare_install_target(info, mod_name, target, selected_variant)
            if plan is None:
                warnings.append(f"{self._target_label(target)}: {error}")
                continue
            plan_warnings = getattr(plan, "warnings", [])
            if plan_warnings:
                plan_warning_lines.extend(
                    f"{self._target_label(target)}: {warning}"
                    for warning in plan_warnings
                )
            conflict_report = check_plan_conflicts(plan, self.app.manifest)
            if conflict_report.has_conflicts:
                conflict_lines.extend(
                    f"{self._target_label(target)}: {Path(conflict.file_path).name}"
                    for conflict in conflict_report.conflicts[:6]
                )
            prepared.append((target, plan))

        if warnings:
            if not quiet:
                messagebox.showerror("Install Plan Error", "\n\n".join(warnings))
            return False

        should_confirm_conflicts = (not quiet) if confirm_conflicts is None else confirm_conflicts
        if conflict_lines and should_confirm_conflicts:
            if not self.app.confirm_action(
                "conflict",
                "Managed File Conflicts",
                "Existing managed files will be backed up before they are overwritten.\n\n" + "\n".join(conflict_lines),
            ):
                return False

        if plan_warning_lines and not quiet:
            if not self.app.confirm_action(
                "conflict",
                "Review Install Warnings",
                "Review these notes before installing:\n\n" + "\n".join(plan_warning_lines[:10]),
            ):
                return False

        installed_results: list[tuple[InstallTarget, ModInstall, object]] = []
        persisted_mod_ids: list[str] = []
        added_record_count = 0
        try:
            for target, plan in prepared:
                mod, record = self.app.installer.install(plan)
                mod.metadata = self._archive_metadata(str(Path(info.archive_path)))
                installed_results.append((target, mod, record))

            for _, mod, _ in installed_results:
                self.app.manifest.add_mod(mod)
                persisted_mod_ids.append(mod.mod_id)

            for _, _, record in installed_results:
                self.app.manifest.add_record(record)
                added_record_count += 1
        except Exception as exc:
            log.error("Install failed: %s", exc)
            if added_record_count:
                try:
                    self.app.manifest.remove_last_records(added_record_count)
                except Exception as rollback_exc:
                    log.error("Failed to remove partial install history: %s", rollback_exc)
            for mod_id in reversed(persisted_mod_ids):
                try:
                    self.app.manifest.remove_mod(mod_id)
                except Exception as rollback_exc:
                    log.error("Failed to remove partial manifest entry %s: %s", mod_id, rollback_exc)
            for _, mod, _ in reversed(installed_results):
                try:
                    self.app.installer.uninstall(mod)
                except Exception as rollback_exc:
                    log.error("Failed to roll back partial install %s: %s", mod.mod_id, rollback_exc)
            if not quiet:
                detail = str(exc)
                if installed_results:
                    detail += "\n\nAny completed target installs from this preset were rolled back."
                messagebox.showerror("Install Failed", detail)
            return False

        installed_labels = [self._target_label(target) for target, _, _ in installed_results]
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self.refresh_view()
        if not quiet:
            preset_label = self._install_preset_label(preset_key)
            self._set_result(f"Installed '{mod_name}' to {preset_label}.", level="success")
        log.info("Installed from Mods tab: %s -> %s", mod_name, ", ".join(installed_labels))
        return True

    def _install_current(self, preset_key: str) -> None:
        if self._current_info is None:
            self._set_result("Select an inactive mod first.", level="info")
            return
        if preset_key == "hosted":
            self.app.open_remote_deploy(Path(self._current_info.archive_path))
            self._set_result(f"Opened the hosted upload flow for {Path(self._current_info.archive_path).name}.", level="info")
            return
        selected_variant = self._prompt_variant_choice(self._current_info)
        if self._current_info.has_variants and not selected_variant:
            return
        mod_name = self._mod_name_var.get().strip() or self._compact_name(Path(self._current_info.archive_path).stem)
        self._run_install_preset(self._current_info, mod_name, preset_key, selected_variant)

    def _install_path_with_preset(self, archive_path: Path, preset_key: str) -> None:
        self._load_archive(archive_path)
        self._install_current(preset_key)

    def _on_install_to_hosted(self) -> None:
        if self._current_info is None:
            self._set_result("Select an inactive mod first.", level="info")
            return
        self.app.open_remote_deploy(self._current_info.archive_path)

    def _selected_archives(self) -> list[Path]:
        return [Path(path_str) for path_str in sorted(self._selected_archive_paths) if Path(path_str).is_file()]

    def _selected_mods(self) -> list[ModInstall]:
        selected = [mod for mod in self.app.manifest.list_mods() if mod.mod_id in self._selected_mod_ids]
        return sorted(selected, key=lambda mod: (mod.display_name.lower(), mod.install_time))

    def _selected_live_items(self) -> list[tuple[str, list[Path | str]]]:
        return [
            (bundle_id, self._resolve_live_file_paths(bundle_id))
            for bundle_id in sorted(self._selected_live_files)
        ]

    def _install_archive_batch(self, archives: list[Path], preset: str) -> None:
        if not archives:
            self._set_result("Select one or more inactive mod rows first.", level="info")
            return
        if not self.app.confirm_action(
            "bulk",
            "Install Selected Mods",
            f"Install {len(archives)} selected inactive mod(s) to {self._install_preset_label(preset)}?",
        ):
            return

        success = 0
        failed = 0
        skipped = 0
        for archive_path in archives:
            try:
                info = inspect_archive(archive_path)
                selected_variant = self._prompt_variant_choice(info)
                if info.has_variants and not selected_variant:
                    skipped += 1
                    continue
                entry = self._library_entry(str(archive_path))
                mod_name = self._compact_name(str(entry.get("name") or archive_path.stem) if entry else archive_path.stem)
                if self._run_install_preset(info, mod_name, preset, selected_variant, quiet=True, confirm_conflicts=True):
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                log.error("Bulk install failed for %s: %s", archive_path, exc)
                failed += 1

        self._clear_selected_archives()
        parts = [f"Installed {success} inactive mod(s) to {self._install_preset_label(preset)}."]
        if failed:
            parts.append(f"{failed} failed.")
        if skipped:
            parts.append(f"{skipped} skipped because variant selection was canceled.")
        self._set_result(" | ".join(parts), level="success" if success and not failed else "warning")

    def _on_install_selected_archives(self) -> None:
        archives = self._selected_archives()
        if not archives:
            self._set_result("Select one or more inactive mod rows first.", level="info")
            return
        preset = self._choose_install_preset(
            title=f"Install {len(archives)} Selected Inactive Mod(s)",
            subtitle="Bulk install uses the same target for every selected mod. Hosted uploads stay separate from bulk install.",
            include_hosted=False,
        )
        if not preset:
            return
        self._install_archive_batch(archives, preset)

    def _on_uninstall_selected_mods(self) -> None:
        mods = self._selected_mods()
        live_items = self._selected_live_items()
        if not mods and not live_items:
            self._set_result("Select one or more active mod rows first.", level="info")
            return
        if not self.app.confirm_action(
            "destructive",
            "Uninstall Selected Mods",
            f"Uninstall {len(mods) + len(live_items)} selected item(s)?",
        ):
            return

        count = 0
        failed = 0
        for mod in mods:
            try:
                record = self.app.installer.uninstall(mod)
                self.app.manifest.add_record(record)
                self.app.manifest.remove_mod(mod.mod_id)
                count += 1
            except Exception as exc:
                log.error("Bulk uninstall failed for %s: %s", mod.mod_id, exc)
                failed += 1
        for bundle_id, bundle_paths in live_items:
            try:
                metadata = getattr(self, "_live_file_bundle_meta", {}).get(bundle_id, {})
                target_label = metadata.get("target_label", "Active Mods")
                kind = metadata.get("kind", "local")
                if kind == "hosted":
                    profile = self._selected_hosted_profile()
                    if profile is None:
                        failed += 1
                        continue
                    deleted, delete_errors = self.app.remote_deployer.delete_remote_files(
                        profile,
                        [str(path) for path in bundle_paths],
                    )
                    if delete_errors:
                        failed += 1
                    else:
                        self.app.manifest.add_record(
                            DeploymentRecord(
                                mod_id=f"hosted:{profile.profile_id}",
                                action="hosted_remove",
                                target="hosted",
                                display_name=PurePosixPath(str(bundle_paths[0])).stem if bundle_paths else "Hosted file",
                                notes=f"Removed {len(deleted)} hosted file(s) from {profile.name}",
                            )
                        )
                        count += 1
                    continue

                existing_paths = [path for path in bundle_paths if isinstance(path, Path) and path.is_file()]
                if not existing_paths:
                    count += 1
                    continue
                if all(safe_delete(path) for path in existing_paths):
                    count += 1
                else:
                    failed += 1
            except Exception as exc:
                log.error("Bulk unmanaged-file removal failed for %s (%s): %s", target_label, bundle_paths, exc)
                failed += 1
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self._selected_mod_ids.clear()
        self._selected_live_files.clear()
        self.refresh_view()
        parts = [f"Uninstalled {count} selected item(s)."]
        if failed:
            parts.append(f"{failed} failed.")
        self._set_result(" | ".join(parts), level="success" if count and not failed else "warning")

    def _on_install_all(self) -> None:
        to_install = [entry for entry in self._library if Path(entry["path"]).is_file() and not self._mods_for_archive(str(entry["path"]))]
        if not to_install:
            self._set_result("All inactive mods are already active or missing.", level="info")
            return
        if not self.app.confirm_action(
            "bulk",
            "Install All",
            f"Install {len(to_install)} inactive mod(s) to the client target?\n\nMods with variants will be skipped for manual review.",
        ):
            return
        success = 0
        failed = 0
        skipped_variants = 0
        for entry in to_install:
            try:
                info = inspect_archive(Path(entry["path"]))
                if info.has_variants:
                    skipped_variants += 1
                    continue
                mod_name = self._compact_name(str(entry.get("name") or Path(entry["path"]).stem))
                if self._run_install_preset(info, mod_name, "client", None, quiet=True):
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                log.error("Install All failed for %s: %s", entry["path"], exc)
                failed += 1
        lines = [f"Installed {success} inactive mod(s)."]
        if failed:
            lines.append(f"{failed} failed.")
        if skipped_variants:
            lines.append(f"{skipped_variants} skipped because they need a manual variant choice.")
        self._set_result(" | ".join(lines), level="success" if success else "warning")
        self.refresh_view()

    def _choose_mod(self, mods: list[ModInstall], *, purpose: str, allow_all: bool = False):
        if not mods:
            return None
        if len(mods) == 1 and not allow_all:
            return mods[0]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Choose Install")
        self.app.center_dialog(dialog, 460, 320)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Choose which install to {purpose}.", font=self.app.ui_font("card_title")).pack(
            anchor="w", padx=16, pady=(16, 6)
        )
        choice_var = tk.StringVar(value=mods[0].mod_id)
        for mod in mods:
            label = f"{self._compact_name(mod.display_name)} [{summarize_target_values(mod.targets)}]"
            if mod.selected_variant:
                label += f" - {mod.selected_variant}"
            ctk.CTkRadioButton(dialog, text=label, variable=choice_var, value=mod.mod_id, font=self.app.ui_font("body")).pack(anchor="w", padx=18, pady=4)
        result = {"value": None}

        def _selected() -> None:
            result["value"] = next((mod for mod in mods if mod.mod_id == choice_var.get()), None)
            dialog.destroy()

        def _all() -> None:
            result["value"] = "all"
            dialog.destroy()

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(16, 16))
        ctk.CTkButton(
            buttons, text="Use Selected", width=130, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), command=_selected
        ).pack(side="left")
        if allow_all:
            ctk.CTkButton(
                buttons,
                text="Use All",
                width=100,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#e67e22",
                hover_color="#ca6b18",
                command=_all,
            ).pack(
                side="left", padx=8
            )
        ctk.CTkButton(buttons, text="Cancel", width=100, fg_color="#444444", hover_color="#555555", command=dialog.destroy).pack(
            side="right"
        )
        self.wait_window(dialog)
        return result["value"]

    def _on_uninstall(self) -> None:
        if not self._selected_library_path:
            self._set_result("Select a mod first.", level="info")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            self._set_result("This mod is not currently active.", level="info")
            return
        selected = self._choose_mod(mods, purpose="uninstall", allow_all=True)
        if selected is None:
            return
        targets = mods if selected == "all" else [selected]
        if not self.app.confirm_action("destructive", "Confirm Uninstall", f"Uninstall {len(targets)} active install(s) from this mod?"):
            return
        for mod in targets:
            record = self.app.installer.uninstall(mod)
            self.app.manifest.add_record(record)
            self.app.manifest.remove_mod(mod.mod_id)
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self.refresh_view()
        self._set_result(f"Uninstalled {len(targets)} active install(s) from the selected mod.", level="success")

    def _on_reinstall(self) -> None:
        if not self._selected_library_path:
            self._set_result("Select a mod first.", level="info")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            self._set_result("This mod is not currently active.", level="info")
            return
        selected = self._choose_mod(mods, purpose="reinstall")
        if selected is None:
            return
        archive_path = Path(selected.source_archive) if selected.source_archive else None
        if not archive_path or not archive_path.is_file():
            messagebox.showerror("Source Not Found", f"The original mod source is no longer available:\n{selected.source_archive}")
            return
        try:
            info = inspect_archive(archive_path)
            if "both" in selected.targets:
                target = InstallTarget.BOTH
            elif "dedicated_server" in selected.targets:
                target = InstallTarget.DEDICATED_SERVER
            else:
                target = InstallTarget(selected.targets[0])
            plan = plan_deployment(info, self.app.paths, target, selected.selected_variant, selected.display_name)
        except Exception as exc:
            messagebox.showerror("Reinstall Failed", f"Could not prepare reinstall:\n{exc}")
            return
        if not plan.valid:
            messagebox.showerror("Reinstall Failed", "\n".join(plan.warnings))
            return
        if not self.app.confirm_action("routine", "Confirm Reinstall", f"Reinstall '{selected.display_name}' from:\n{archive_path.name}"):
            return
        uninstall_record = self.app.installer.uninstall(selected)
        self.app.manifest.add_record(uninstall_record)
        self.app.manifest.remove_mod(selected.mod_id)
        try:
            mod, install_record = self.app.installer.install(plan)
            self.app.manifest.add_mod(mod)
            self.app.manifest.add_record(install_record)
        except Exception as exc:
            messagebox.showerror("Reinstall Failed", f"Uninstall succeeded but reinstall failed:\n{exc}")
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self.refresh_view()
        self._set_result(f"Reinstalled {selected.display_name}.", level="success")

    def _on_repair(self) -> None:
        if not self._selected_library_path:
            self._set_result("Select a mod first.", level="info")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            self._set_result("This mod is not currently active.", level="info")
            return
        selected = self._choose_mod(mods, purpose="repair")
        if selected is None:
            return
        result = self.app.integrity.repair_mod(selected)
        message = result.summary
        if result.failed:
            message += "\n\nFailed:\n" + "\n".join(result.failed)
        if result.warnings:
            message += "\n\nWarnings:\n" + "\n".join(result.warnings)
        self._set_result(message.replace("\n\n", " | "), level="success" if not result.failed else "warning")
        self.app.refresh_backups_tab()
        self.refresh_view()

    def _on_compare_with_server(self) -> None:
        self.app._tabview.set("Server")
        self.app._server_tab.compare_now()

    def _do_install(
        self,
        info: ArchiveInfo,
        mod_name: str,
        target: InstallTarget,
        selected_variant: Optional[str] = None,
        quiet: bool = False,
    ) -> bool:
        paths = self.app.paths
        if target in (InstallTarget.CLIENT, InstallTarget.BOTH) and not paths.client_root:
            if not quiet:
                messagebox.showerror("Missing Client Path", "Configure the client path in Settings first.")
            return False
        if target in (InstallTarget.SERVER, InstallTarget.BOTH) and not paths.server_root:
            if not quiet:
                messagebox.showerror("Missing Server Path", "Configure the local server path in Settings first.")
            return False
        if target == InstallTarget.DEDICATED_SERVER and not paths.dedicated_server_root:
            if not quiet:
                messagebox.showerror("Missing Dedicated Server Path", "Configure the dedicated server path in Settings first.")
            return False
        plan = plan_deployment(info, paths, target, selected_variant, mod_name)
        if not plan.valid:
            if not quiet:
                messagebox.showerror("Install Plan Error", "\n".join(plan.warnings))
            return False
        conflict_report = check_plan_conflicts(plan, self.app.manifest)
        if conflict_report.has_conflicts and not quiet:
            conflict_lines = [f"{conflict.existing_mod_id}: {Path(conflict.file_path).name}" for conflict in conflict_report.conflicts[:10]]
            if not self.app.confirm_action(
                "conflict",
                "Managed File Conflicts",
                "Existing managed files will be backed up before they are overwritten.\n\n" + "\n".join(conflict_lines),
            ):
                return False
        try:
            mod, record = self.app.installer.install(plan)
            self.app.manifest.add_mod(mod)
            self.app.manifest.add_record(record)
            self.app.refresh_installed_tab()
            self.app.refresh_backups_tab()
            self.refresh_view()
            if not quiet:
                self._set_result(f"Installed '{mod.display_name}' to {self._target_label(target)}.", level="success")
            log.info("Installed from Mods tab: %s", mod.display_name)
            return True
        except Exception as exc:
            log.error("Install failed: %s", exc)
            if not quiet:
                messagebox.showerror("Install Failed", str(exc))
            return False
