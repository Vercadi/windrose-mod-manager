"""Mods screen with archive and applied state in one workspace."""
from __future__ import annotations

from collections import defaultdict
import logging
import os
import re
import threading
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.archive_handler import SUPPORTED_EXTENSIONS
from ...core.archive_inspector import inspect_archive
from ...core.conflict_detector import check_plan_conflicts
from ...core.deployment_planner import plan_deployment
from ...core.live_mod_inventory import (
    LiveModsFolderSnapshot,
    bundle_live_file_names,
    snapshot_live_mods_folder,
)
from ...models.archive_info import ArchiveInfo
from ...models.deployment_record import DeploymentRecord
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
    ("Mod archives", "*.zip *.7z *.rar"),
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
    "Available Archives": "available",
    "Applied Sources": "installed",
    "All Tracked Archives": "all",
    "Client": "client",
    "Local Server": "server",
    "Dedicated Server": "dedicated",
    "Client + Local Server": "client_local",
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
        self._applied_widgets: list[object] = []
        self._selected_library_path: Optional[str] = None
        self._selected_archive_paths: set[str] = set()
        self._selected_mod_ids: set[str] = set()
        self._selected_live_files: set[str] = set()
        self._live_file_bundle_members: dict[str, list[Path | str]] = {}
        self._live_file_bundle_meta: dict[str, dict[str, str]] = {}
        self._pending_click_path: Optional[Path] = None
        self._single_click_job = None
        self._hosted_inventory_request = 0
        self._details_visible = False

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_args: self._refresh_library_ui())
        self._filter_var = ctk.StringVar(value="Available Archives")
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
        self._lists_panes.add(left_host, minsize=300, width=360)
        self._lists_panes.add(right_host, minsize=320, width=420)

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
        ctk.CTkLabel(header, text="Applied Mods", font=self.app.ui_font("section_title")).grid(
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
        header.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(header, text="Archives", font=self.app.ui_font("section_title")).grid(
            row=0, column=0, sticky="w"
        )
        add_btn = ctk.CTkButton(
            header, text="Add", width=64, fg_color="#2980b9", hover_color="#2471a3", command=self.import_archives,
            height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body")
        )
        add_btn.grid(row=0, column=1, sticky="w", padx=(8, 6))
        self._action_buttons.append(add_btn)
        self._filter_menu = ctk.CTkOptionMenu(
            header,
            variable=self._filter_var,
            values=list(_FILTER_LABELS.keys()),
            width=156,
            command=lambda _value: self._refresh_library_ui(),
            font=self.app.ui_font("body"),
        )
        self._filter_menu.grid(row=0, column=2, sticky="e", padx=(0, 6))
        self._search_entry = ctk.CTkEntry(
            header, textvariable=self._search_var, placeholder_text="Search...", width=170, font=self.app.ui_font("body")
        )
        self._search_entry.grid(row=0, column=3, sticky="e", padx=(0, 6))
        self._selected_archives_label = ctk.CTkLabel(header, text="", anchor="e", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._selected_archives_label.grid(row=0, column=4, sticky="e", padx=(0, 6))
        self._install_selected_btn = ctk.CTkButton(
            header,
            text="Install Selected",
            width=128,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            state="disabled",
            command=self._on_install_selected_archives,
        )
        self._install_selected_btn.grid(row=0, column=5, sticky="e", padx=(0, 6))
        self._action_buttons.append(self._install_selected_btn)
        self._clear_archive_selection_btn = ctk.CTkButton(
            header,
            text="Clear",
            width=64,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            state="disabled",
            command=self._clear_selected_archives,
        )
        self._clear_archive_selection_btn.grid(row=0, column=6, sticky="e", padx=(0, 6))
        self._action_buttons.append(self._clear_archive_selection_btn)
        refresh_btn = ctk.CTkButton(
            header, text="Refresh", width=72, fg_color="#555555", hover_color="#666666", command=self.refresh_view,
            height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body")
        )
        refresh_btn.grid(row=0, column=7, sticky="e")
        self._action_buttons.append(refresh_btn)

        self._archive_hint_label = ctk.CTkLabel(
            panel,
            text="Double-click an archive to choose a target. Right-click rows for more actions. Drop archives anywhere in this pane.",
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
            panel, text="Select a mod or archive", font=self.app.ui_font("detail_title"), anchor="w"
        )
        self._detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 2))
        self._detail_meta = ctk.CTkLabel(panel, text="", anchor="w", justify="left", text_color="#95a5a6", font=self.app.ui_font("body"))
        self._detail_meta.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._detail_hint = ctk.CTkLabel(
            panel,
            text="Archive install actions and applied mod management now live in row menus. Double-click an archive to install quickly.",
            justify="left",
            wraplength=self.app.ui_tokens.detail_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._detail_hint.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        self._installed_box = self._add_text_section(panel, 3, "Applied State", 78)
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
            return "Not installed"
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
    def _target_label(target: InstallTarget) -> str:
        return install_target_label(target)

    def _library_path(self) -> Path:
        from ..app_window import DEFAULT_DATA_DIR

        return DEFAULT_DATA_DIR / "archive_library.json"

    def _load_library(self) -> None:
        self._normalize_combined_local_server_installs()
        self._library = read_json(self._library_path()).get("archives", [])
        self._refresh_library_ui()

    def _save_library(self) -> None:
        write_json(self._library_path(), {"archives": self._library})

    def _add_to_library(self, archive_path: Path) -> None:
        archive_str = str(archive_path)
        for entry in self._library:
            if entry.get("path") == archive_str:
                return
        self._library.append({"path": archive_str, "name": archive_path.stem, "ext": archive_path.suffix.lower()})
        self._save_library()

    def _update_library_entry(self, archive_path: Path, info: ArchiveInfo) -> None:
        for entry in self._library:
            if entry.get("path") == str(archive_path):
                entry["archive_type"] = info.archive_type.value.replace("_", " ")
                entry["total_files"] = info.total_files
                break
        self._save_library()

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
        self._refresh_library_ui()

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
        self._show_details_panel()
        self._load_archive(archive_path)

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
        return _FILTER_LABELS.get(self._filter_var.get(), "all")

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
        self._open_folder(archive_path.parent, label=f"{archive_path.name} folder")

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

            self.after(0, _show)

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
        if mod.source_archive:
            self._selected_library_path = mod.source_archive
            self._refresh_library_ui()
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
            menu.add_command(label="Open Archive Folder", command=lambda p=Path(mod.source_archive): self._open_archive_folder(p))
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
        self._applied_summary_label.configure(text=summary if (mods or live_snapshots) else "0 applied")

        has_live_issues = any(snapshot.warning or snapshot.unmanaged_files or snapshot.missing_managed_files for snapshot in live_snapshots.values())
        if not mods and not has_live_issues:
            empty = ctk.CTkLabel(
                self._applied_list,
                text="No applied mods yet. Install an archive to the client, local server, or dedicated server to track it here.",
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
                archive_name = Path(mod.source_archive).name if mod.source_archive else "(no archive)"
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

                subtitle_parts = [summarize_target_values(mod.targets), archive_name, f"{mod.file_count} files"]
                if mod.source_archive and not Path(mod.source_archive).is_file():
                    subtitle_parts.append("archive missing")
                subtitle = ctk.CTkLabel(
                    row_frame,
                    text=" | ".join(subtitle_parts),
                    anchor="w",
                    font=self.app.ui_font("small"),
                    text_color="#95a5a6",
                )
                subtitle.grid(row=1, column=1, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))

                if mod.source_archive:
                    for widget in (row_frame, title, subtitle):
                        widget.bind("<Button-1>", lambda _event, p=Path(mod.source_archive): self._load_archive(p))
                        widget.bind("<Button-3>", lambda event, m=mod: self._show_applied_menu(event, m))

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

    def _refresh_library_ui(self) -> None:
        for widget in self._library_widgets:
            widget.destroy()
        self._library_widgets.clear()
        self._refresh_applied_ui()

        display_entries = self._display_entries()
        if self._scope_var.get() == "hosted":
            applied_summary = "live hosted inventory"
        else:
            applied_count = sum(
                1 for mod in self.app.manifest.list_mods()
                if self._scope_matches_targets(self._effective_targets(mod))
            )
            applied_summary = f"{applied_count} applied"
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
        summary = f"{len(filtered_entries)} archives shown | {applied_summary} | {scope_label}"
        if hidden_count:
            summary += f" | {hidden_count} not tracked"
        self._summary_label.configure(text=summary)

        if not filtered_entries:
            empty_text = (
                "Drop archives into this list or use Add to track your first archive."
                if not self._search_var.get().strip() and self._selected_filter_value() == "available"
                else "No archives match the current search or filter."
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

    def _add_library_row(self, entry: dict, index: int) -> None:
        path = Path(entry["path"])
        exists = path.is_file()
        mods = self._mods_for_archive(str(path))
        is_synthetic = bool(entry.get("_synthetic"))
        if mods and is_synthetic and exists:
            status = "Applied"
        elif mods and is_synthetic and not exists:
            status = "Applied*"
        else:
            status = "Missing" if not exists else "Applied" if mods else "Ready"
        if mods and all(not mod.enabled for mod in mods) and status == "Applied":
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
        ).grid(
            row=0, column=0, rowspan=3, sticky="nw", padx=(8, 2), pady=(8, 4)
        )

        color = {
            "Ready": "#3498db",
            "Applied": "#2d8a4e",
            "Disabled": "#f39c12",
            "Applied*": "#f39c12",
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
        details = " | ".join(
            part for part in [
                type_label,
                f"{total_files} files" if total_files else "",
                f"Installed To: {self._installed_to_text(mods)}",
                "Not tracked" if is_synthetic else "",
            ] if part
        )
        detail_label = ctk.CTkLabel(
            row, text=details, anchor="w", text_color="#95a5a6", wraplength=self.app.ui_tokens.panel_wrap, font=self.app.ui_font("small")
        )
        detail_label.grid(row=1, column=1, columnspan=2, sticky="ew", padx=9, pady=(0, 1))
        action_label = ctk.CTkLabel(row, text=self._last_action_text(str(path)), anchor="w", text_color="#6f7a81", font=self.app.ui_font("tiny"))
        action_label.grid(row=2, column=1, columnspan=2, sticky="ew", padx=9, pady=(0, 5 + self.app.ui_tokens.row_pad_y))

        if is_synthetic and exists:
            action_btn = ctk.CTkButton(
                row,
                text="Track",
                width=64,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._track_in_library(value),
            )
            action_btn.grid(row=0, column=3, rowspan=3, padx=(6, 9), pady=6)
        elif not is_synthetic:
            action_btn = ctk.CTkButton(
                row,
                text="Untrack",
                width=76,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._remove_from_library(value),
            )
            action_btn.grid(row=0, column=3, rowspan=3, padx=(6, 9), pady=6)

        for widget in (row, badge, name, detail_label, action_label):
            widget.bind("<Button-1>", lambda _event, p=path: self._on_library_row_click(p))
            widget.bind("<Double-Button-1>", lambda event, p=path: self._on_library_row_double_click(event, p))
            widget.bind("<Button-3>", lambda event, p=path: self._show_library_menu(event, p))
        self._library_widgets.append(row)

    def _remove_from_library(self, path_str: str) -> None:
        mods = self._mods_for_archive(path_str)
        if mods and not self.app.confirm_action(
            "bulk",
            "Untrack Archive",
            "Remove this archive from the tracked archive list?\n\n"
            "This does not uninstall the applied mod. The install stays active and will remain visible in Applied Mods.",
        ):
            return
        self._library = [entry for entry in self._library if entry.get("path") != path_str]
        if self._selected_library_path == path_str:
            self._selected_library_path = None
            self._clear_details()
        self._save_library()
        self._refresh_library_ui()
        self._set_result(f"Removed {Path(path_str).name} from the tracked archive list.", level="info")

    def _track_in_library(self, path_str: str) -> None:
        archive_path = Path(path_str)
        if not archive_path.is_file():
            messagebox.showerror("Archive Missing", f"The archive is no longer available:\n{path_str}")
            return
        self._add_to_library(archive_path)
        self._refresh_library_ui()
        self._set_result(f"Added {archive_path.name} to the archive library.", level="success")

    def _show_library_menu(self, event, archive_path: Path) -> None:
        menu = tk.Menu(self, tearoff=0)
        if archive_path.is_file():
            install_menu = self._build_install_menu(menu, archive_path)
            menu.add_cascade(label="Install", menu=install_menu)
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
            menu.add_command(label="Open Archive Folder", command=lambda p=archive_path: self._open_archive_folder(p))
        if any(entry.get("path") == str(archive_path) for entry in self._library):
            menu.add_command(label="Untrack Archive", command=lambda: self._remove_from_library(str(archive_path)))
        elif archive_path.is_file():
            menu.add_command(label="Track Archive", command=lambda: self._track_in_library(str(archive_path)))
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
        for key, label, _detail in _INSTALL_PRESETS:
            if not include_hosted and key == "hosted":
                continue
            menu.add_command(
                label=label,
                command=lambda paths=tuple(archive_paths), preset=key: self._install_archives_with_preset(
                    [Path(path) for path in paths],
                    preset,
                ),
            )
        return menu

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
        valid = [path for path in self._parse_drop_data(event.data) if path.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not valid:
            self._set_result("The drop did not contain a supported archive.", level="warning")
            return
        for path in valid:
            self._add_to_library(path)
        self._save_library()
        self._refresh_library_ui()
        if len(valid) == 1:
            self._load_archive(valid[0])
        self._set_result(f"Added {len(valid)} archive(s) to the library.", level="success")

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
        paths = filedialog.askopenfilenames(title="Select Mod Archive(s)", filetypes=_FILETYPES)
        if not paths:
            return
        valid = [Path(path) for path in paths if Path(path).suffix.lower() in SUPPORTED_EXTENSIONS]
        for path in valid:
            self._add_to_library(path)
        self._save_library()
        self._refresh_library_ui()
        if len(valid) == 1:
            self._load_archive(valid[0])
        if valid:
            self._set_result(f"Added {len(valid)} archive(s) to the library.", level="success")

    def _load_archive(self, archive_path: Path, *, refresh_only: bool = False) -> None:
        self._selected_library_path = str(archive_path)
        self._refresh_library_ui()
        installed_mods = self._mods_for_archive(str(archive_path))
        try:
            info = inspect_archive(archive_path)
        except Exception as exc:
            self._current_info = None
            self._detail_header.configure(text=self._compact_name(archive_path.stem or archive_path.name))
            self._detail_meta.configure(
                text="\n".join(
                    [
                        f"Installed To: {self._installed_to_text(installed_mods)}",
                        f"Archive: {archive_path.name}",
                        f"Last Action: {self._last_action_text(str(archive_path))}",
                        f"Could not inspect archive: {exc}",
                    ]
                )
            )
            self._set_textbox(self._installed_box, self._installed_text(installed_mods))
            self._set_textbox(
                self._review_box,
                "Archive details are unavailable. Re-import the archive to inspect, reinstall, or repair this install.",
            )
            self._set_textbox(
                self._preview_box,
                "Archive contents are unavailable because the source archive is missing or could not be read.",
            )
            return

        self._current_info = info
        self._update_library_entry(archive_path, info)
        self._refresh_library_ui()
        meta_parts = [
            info.archive_type.value.replace("_", " ").title(),
            f"{info.total_files} files",
            f"Installed To: {self._installed_to_text(installed_mods)}",
        ]
        self._detail_header.configure(text=self._compact_name(archive_path.stem))
        self._detail_meta.configure(
            text="\n".join(
                [
                    " | ".join(part for part in meta_parts if part),
                    f"Archive: {archive_path.name}",
                    f"Last Action: {self._last_action_text(str(archive_path))}",
                ]
            )
        )
        self._mod_name_var.set(self._compact_name(archive_path.stem))

        self._set_textbox(self._installed_box, self._installed_text(installed_mods))
        self._set_textbox(self._review_box, self._build_install_review(info))
        self._set_textbox(self._preview_box, self._preview_text(info))
        if not refresh_only:
            log.info("Inspected archive: %s", archive_path.name)

    def _clear_details(self) -> None:
        self._current_info = None
        self._detail_header.configure(text="Select a mod or archive")
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
            return "This archive is not currently applied anywhere."
        lines: list[str] = []
        for mod in mods:
            target_text = summarize_target_values(mod.targets)
            lines.append(f"{self._compact_name(mod.display_name)} [{target_text}] - {'enabled' if mod.enabled else 'disabled'}")
            if mod.selected_variant:
                lines.append(f"  variant: {mod.selected_variant}")
            lines.append(f"  files: {mod.file_count}")
            lines.append(f"  archive: {Path(mod.source_archive).name}")
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
        lines.append("Hosted Server only: open the archive row menu or double-click the archive to launch the hosted upload flow.")
        if info.warnings:
            lines.append("")
            lines.append("Archive warnings:")
            lines.extend(f"- {warning}" for warning in info.warnings)
        return "\n".join(lines)

    def _preview_text(self, info: ArchiveInfo) -> str:
        lines = [
            f"Archive:     {Path(info.archive_path).name}",
            f"Source Path: {info.archive_path}",
            f"Type:        {info.archive_type.value}",
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
    ):
        paths = self.app.paths
        if target in (InstallTarget.CLIENT, InstallTarget.BOTH) and not paths.client_root:
            return None, "Configure the client path in Settings first."
        if target in (InstallTarget.SERVER, InstallTarget.BOTH) and not paths.server_root:
            return None, "Configure the local server path in Settings first."
        if target == InstallTarget.DEDICATED_SERVER and not paths.dedicated_server_root:
            return None, "Configure the dedicated server path in Settings first."
        plan = plan_deployment(info, paths, target, selected_variant, mod_name)
        if not plan.valid:
            return None, "\n".join(plan.warnings) if plan.warnings else "The install plan is not valid."
        return plan, None

    def _run_install_preset(
        self,
        info: ArchiveInfo,
        mod_name: str,
        preset_key: str,
        selected_variant: Optional[str],
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

        prepared = []
        warnings: list[str] = []
        conflict_lines: list[str] = []
        for target in targets:
            plan, error = self._prepare_install_target(info, mod_name, target, selected_variant)
            if plan is None:
                warnings.append(f"{self._target_label(target)}: {error}")
                continue
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

        installed_results: list[tuple[InstallTarget, ModInstall, object]] = []
        persisted_mod_ids: list[str] = []
        added_record_count = 0
        try:
            for target, plan in prepared:
                mod, record = self.app.installer.install(plan)
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
            self._set_result("Select an archive first.", level="info")
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
            self._set_result("Select an archive first.", level="info")
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
            self._set_result("Select one or more archive rows first.", level="info")
            return
        if not self.app.confirm_action(
            "bulk",
            "Install Selected Archives",
            f"Install {len(archives)} selected archive(s) to {self._install_preset_label(preset)}?",
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
                mod_name = self._compact_name(archive_path.stem)
                if self._run_install_preset(info, mod_name, preset, selected_variant, quiet=True, confirm_conflicts=True):
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                log.error("Bulk install failed for %s: %s", archive_path, exc)
                failed += 1

        self._clear_selected_archives()
        parts = [f"Installed {success} archive(s) to {self._install_preset_label(preset)}."]
        if failed:
            parts.append(f"{failed} failed.")
        if skipped:
            parts.append(f"{skipped} skipped because variant selection was canceled.")
        self._set_result(" | ".join(parts), level="success" if success and not failed else "warning")

    def _on_install_selected_archives(self) -> None:
        archives = self._selected_archives()
        if not archives:
            self._set_result("Select one or more archive rows first.", level="info")
            return
        preset = self._choose_install_preset(
            title=f"Install {len(archives)} Selected Archive(s)",
            subtitle="Bulk install uses the same target for every selected archive. Hosted uploads stay separate from bulk install.",
            include_hosted=False,
        )
        if not preset:
            return
        self._install_archive_batch(archives, preset)

    def _on_uninstall_selected_mods(self) -> None:
        mods = self._selected_mods()
        live_items = self._selected_live_items()
        if not mods and not live_items:
            self._set_result("Select one or more applied mod rows first.", level="info")
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
                target_label = metadata.get("target_label", "Applied Mods")
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
            self._set_result("All tracked archives are already applied or missing.", level="info")
            return
        if not self.app.confirm_action(
            "bulk",
            "Install All",
            f"Install {len(to_install)} archive(s) to the client target?\n\nArchives with variants will be skipped for manual review.",
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
                if self._run_install_preset(info, Path(entry["path"]).stem, "client", None, quiet=True):
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                log.error("Install All failed for %s: %s", entry["path"], exc)
                failed += 1
        lines = [f"Installed {success} archive(s)."]
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
            self._set_result("Select an archive first.", level="info")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            self._set_result("This archive is not currently installed.", level="info")
            return
        selected = self._choose_mod(mods, purpose="uninstall", allow_all=True)
        if selected is None:
            return
        targets = mods if selected == "all" else [selected]
        if not self.app.confirm_action("destructive", "Confirm Uninstall", f"Uninstall {len(targets)} install(s) from this archive?"):
            return
        for mod in targets:
            record = self.app.installer.uninstall(mod)
            self.app.manifest.add_record(record)
            self.app.manifest.remove_mod(mod.mod_id)
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self.refresh_view()
        self._set_result(f"Uninstalled {len(targets)} install(s) from the selected archive.", level="success")

    def _on_reinstall(self) -> None:
        if not self._selected_library_path:
            self._set_result("Select an archive first.", level="info")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            self._set_result("This archive is not currently installed.", level="info")
            return
        selected = self._choose_mod(mods, purpose="reinstall")
        if selected is None:
            return
        archive_path = Path(selected.source_archive) if selected.source_archive else None
        if not archive_path or not archive_path.is_file():
            messagebox.showerror("Archive Not Found", f"The original archive is no longer available:\n{selected.source_archive}")
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
            self._set_result("Select an archive first.", level="info")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            self._set_result("This archive is not currently installed.", level="info")
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
