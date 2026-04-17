"""Mods screen with archive and applied state in one workspace."""
from __future__ import annotations

from collections import defaultdict
import logging
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
from ...models.archive_info import ArchiveInfo
from ...models.mod_install import InstallTarget, ModInstall
from ...utils.json_io import read_json, write_json

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


class ModsTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._current_info: Optional[ArchiveInfo] = None
        self._library: list[dict] = []
        self._library_widgets: list[ctk.CTkFrame] = []
        self._applied_widgets: list[object] = []
        self._selected_library_path: Optional[str] = None
        self._pending_click_path: Optional[Path] = None
        self._single_click_job = None
        self._hosted_inventory_request = 0

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_args: self._refresh_library_ui())
        self._filter_var = ctk.StringVar(value="all")
        self._scope_var = ctk.StringVar(value="all")
        self._variant_var = ctk.StringVar(value="(none)")
        self._mod_name_var = ctk.StringVar()

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

        ctk.CTkLabel(bar, text="Mods", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )

        self._scope_switch = ctk.CTkSegmentedButton(
            bar,
            values=["All", "Client", "Server", "Dedicated", "Hosted"],
            command=lambda value: self._on_scope_changed(value),
        )
        self._scope_switch.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self._scope_switch.set("All")

        self._summary_label = ctk.CTkLabel(bar, text="", anchor="w", text_color="#95a5a6")
        self._summary_label.grid(row=0, column=2, sticky="ew", padx=(0, 12))

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

        top_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        bottom_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        self._panes.add(top_host, minsize=340, height=520, stretch="always")
        self._panes.add(bottom_host, minsize=150, height=185, stretch="never")

        self._lists_panes = tk.PanedWindow(
            top_host,
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
        self._build_details_panel(bottom_host)

    def _build_applied_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent)
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Applied Mods", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        self._applied_summary_label = ctk.CTkLabel(header, text="", anchor="e", text_color="#95a5a6")
        self._applied_summary_label.grid(row=0, column=1, sticky="e")

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
        header.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(header, text="Archives", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(
            header, text="Add", width=64, fg_color="#2980b9", hover_color="#2471a3", command=self.import_archives
        ).grid(row=0, column=1, sticky="w", padx=(8, 6))
        self._filter_menu = ctk.CTkOptionMenu(
            header,
            variable=self._filter_var,
            values=["all", "installed", "not installed", "client", "server", "dedicated", "both", "missing archive"],
            width=118,
            command=lambda _value: self._refresh_library_ui(),
        )
        self._filter_menu.grid(row=0, column=2, sticky="e", padx=(0, 6))
        self._search_entry = ctk.CTkEntry(
            header, textvariable=self._search_var, placeholder_text="Search...", width=170
        )
        self._search_entry.grid(row=0, column=3, sticky="e", padx=(0, 6))
        ctk.CTkButton(
            header, text="Refresh", width=72, fg_color="#555555", hover_color="#666666", command=self.refresh_view
        ).grid(row=0, column=4, sticky="e")

        self._archive_hint_label = ctk.CTkLabel(
            panel,
            text="Double-click an archive to choose a target. Right-click rows for more actions. Drop archives anywhere in this pane.",
            justify="left",
            wraplength=500,
            text_color="#95a5a6",
            font=ctk.CTkFont(size=11),
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
            panel, text="Select a mod or archive", font=ctk.CTkFont(size=16, weight="bold"), anchor="w"
        )
        self._detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 2))
        self._detail_meta = ctk.CTkLabel(panel, text="", anchor="w", justify="left", text_color="#95a5a6")
        self._detail_meta.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._detail_hint = ctk.CTkLabel(
            panel,
            text="Archive install actions and applied mod management now live in row menus. Double-click an archive to install quickly.",
            justify="left",
            wraplength=900,
            text_color="#95a5a6",
            font=ctk.CTkFont(size=11),
        )
        self._detail_hint.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        self._installed_box = self._add_text_section(panel, 3, "Applied State", 78)
        self._review_box = self._add_text_section(panel, 4, "Review", 78)
        self._preview_box = self._add_text_section(panel, 5, "Contents", 120)

    def _add_text_section(self, parent, row: int, title: str, height: int) -> ctk.CTkTextbox:
        card = ctk.CTkFrame(parent)
        card.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        box = ctk.CTkTextbox(card, height=height, font=ctk.CTkFont(family="Consolas", size=10))
        box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        box.configure(state="disabled")
        return box

    def refresh_view(self) -> None:
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
    def _effective_targets(mod: ModInstall) -> set[str]:
        targets = set(mod.targets)
        expanded: set[str] = set()
        if "both" in targets:
            expanded.update({"client", "server"})
        expanded.update(target for target in targets if target in {"client", "server", "dedicated_server"})
        return expanded

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
            targets = self._effective_targets(mod)
            label = " + ".join(
                x for x, k in (
                    ("Client", "client"),
                    ("Server", "server"),
                    ("Dedicated", "dedicated_server"),
                ) if k in targets
            ) or "Hosted"
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
        return {
            InstallTarget.CLIENT: "Client",
            InstallTarget.SERVER: "Server",
            InstallTarget.DEDICATED_SERVER: "Dedicated Server",
            InstallTarget.BOTH: "Client + Server",
        }.get(target, target.value.title())

    def _library_path(self) -> Path:
        from ..app_window import DEFAULT_DATA_DIR

        return DEFAULT_DATA_DIR / "archive_library.json"

    def _load_library(self) -> None:
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

    def _on_scope_changed(self, value: str) -> None:
        scope = {
            "All": "all",
            "Client": "client",
            "Server": "server",
            "Dedicated": "dedicated_server",
            "Hosted": "hosted",
        }.get(value, "all")
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

    def _display_name(self, raw: str, *, max_len: int = 34) -> str:
        text = self._compact_name(raw)
        if len(text) <= max_len:
            return text
        clipped = text[: max_len - 1].rstrip(" ._-")
        return clipped + "…"

    def _scope_matches_targets(self, targets: set[str]) -> bool:
        scope = self._scope_var.get()
        if scope == "all":
            return True
        if scope == "hosted":
            return False
        return scope in targets

    def _applied_group_label(self, mod: ModInstall) -> str:
        targets = self._effective_targets(mod)
        if targets == {"client", "server"}:
            return "Client + Server"
        if targets == {"client"}:
            return "Client"
        if targets == {"server"}:
            return "Server"
        if targets == {"dedicated_server"}:
            return "Dedicated Server"
        if targets == {"client", "dedicated_server"}:
            return "Client + Dedicated"
        return "Other"

    def _selected_hosted_profile(self):
        server_tab = getattr(self.app, "_server_tab", None)
        if server_tab is None:
            return None
        try:
            return server_tab._selected_remote_profile()
        except Exception:
            return None

    def _request_hosted_inventory(self) -> None:
        profile = self._selected_hosted_profile()
        if profile is None:
            self._applied_summary_label.configure(text="No hosted profile selected")
            empty = ctk.CTkLabel(
                self._applied_list,
                text="Choose a hosted profile in Server first. Then switch back to Hosted in Mods to view the live remote mod list.",
                justify="left",
                wraplength=330,
                text_color="#95a5a6",
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._applied_widgets.append(empty)
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
            return

        names = sorted(Path(path).name for path in remote_files)
        pak_names = [name for name in names if name.lower().endswith(".pak")]
        other_names = [name for name in names if name not in pak_names]
        self._applied_summary_label.configure(text=f"{len(names)} hosted file(s)")

        if not names:
            empty = ctk.CTkLabel(
                self._applied_list,
                text=f"No files were found in the hosted mods folder for {profile_name}.",
                justify="left",
                wraplength=330,
                text_color="#95a5a6",
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._applied_widgets.append(empty)
            return

        row = 0
        sections = [("PAK Mods", pak_names), ("Other Files", other_names)]
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

            for name in items:
                row_frame = ctk.CTkFrame(self._applied_list, fg_color="#2f2f2f")
                row_frame.grid(row=row, column=0, sticky="ew", pady=1)
                row_frame.grid_columnconfigure(0, weight=1)
                title = ctk.CTkLabel(
                    row_frame,
                    text=self._display_name(name, max_len=30),
                    anchor="w",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#ffffff",
                )
                title.grid(row=0, column=0, sticky="ew", padx=9, pady=(6, 1))
                subtitle = ctk.CTkLabel(
                    row_frame,
                    text=f"{name} | hosted live inventory",
                    anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color="#95a5a6",
                )
                subtitle.grid(row=1, column=0, sticky="ew", padx=9, pady=(0, 6))
                self._applied_widgets.append(row_frame)
                row += 1

    def _show_applied_menu(self, event, mod: ModInstall) -> None:
        if mod.source_archive:
            self._selected_library_path = mod.source_archive
            self._refresh_library_ui()
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Inspect", command=lambda p=Path(mod.source_archive): self._load_archive(p))
        if mod.source_archive and Path(mod.source_archive).is_file():
            menu.add_command(label="Reinstall", command=self._on_reinstall)
            menu.add_command(label="Repair", command=self._on_repair)
        menu.add_command(label="Uninstall", command=self._on_uninstall)
        menu.add_separator()
        menu.add_command(label="Compare with Server", command=self._on_compare_with_server)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _refresh_applied_ui(self) -> None:
        for widget in self._applied_widgets:
            widget.destroy()
        self._applied_widgets.clear()

        if self._scope_var.get() == "hosted":
            self._request_hosted_inventory()
            return

        mods = [
            mod for mod in self.app.manifest.list_mods()
            if self._scope_matches_targets(self._effective_targets(mod))
        ]
        enabled_count = sum(1 for mod in mods if mod.enabled)
        disabled_count = len(mods) - enabled_count
        summary = f"{enabled_count} active"
        if disabled_count:
            summary += f" | {disabled_count} disabled"
        self._applied_summary_label.configure(text=summary if mods else "0 applied")

        if not mods:
            empty = ctk.CTkLabel(
                self._applied_list,
                text="No applied mods yet. Install an archive to the client, server, or dedicated server to track it here.",
                justify="left",
                wraplength=330,
                text_color="#95a5a6",
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._applied_widgets.append(empty)
            return

        grouped: dict[str, list[ModInstall]] = defaultdict(list)
        for mod in mods:
            grouped[self._applied_group_label(mod)].append(mod)

        order = ["Client + Server", "Client + Dedicated", "Client", "Server", "Dedicated Server", "Other"]
        row = 0
        for group_name in order:
            items = grouped.get(group_name, [])
            if not items:
                continue
            heading = ctk.CTkLabel(
                self._applied_list,
                text=group_name,
                font=ctk.CTkFont(size=12, weight="bold"),
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
                row_frame.grid_columnconfigure(0, weight=1)

                title_parts = [self._display_name(mod.display_name, max_len=32)]
                if mod.selected_variant:
                    title_parts.append(f"({mod.selected_variant})")
                if not mod.enabled:
                    title_parts.append("[disabled]")
                title = ctk.CTkLabel(
                    row_frame,
                    text=" ".join(title_parts),
                    anchor="w",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#ffffff",
                )
                title.grid(row=0, column=0, sticky="ew", padx=9, pady=(6, 1))

                subtitle_parts = [archive_name, f"{mod.file_count} files"]
                if mod.source_archive and not Path(mod.source_archive).is_file():
                    subtitle_parts.append("archive missing")
                subtitle = ctk.CTkLabel(
                    row_frame,
                    text=" | ".join(subtitle_parts),
                    anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color="#95a5a6",
                )
                subtitle.grid(row=1, column=0, sticky="ew", padx=9, pady=(0, 6))

                if mod.source_archive:
                    for widget in (row_frame, title, subtitle):
                        widget.bind("<Button-1>", lambda _event, p=Path(mod.source_archive): self._load_archive(p))
                        widget.bind("<Button-3>", lambda event, m=mod: self._show_applied_menu(event, m))

                self._applied_widgets.append(row_frame)
                row += 1

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
        selected_filter = self._filter_var.get()
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
            if selected_filter == "installed" and not mods:
                continue
            if selected_filter == "not installed" and mods:
                continue
            if selected_filter == "client" and "client" not in targets:
                continue
            if selected_filter == "server" and "server" not in targets:
                continue
            if selected_filter == "dedicated" and "dedicated_server" not in targets:
                continue
            if selected_filter == "both" and targets != {"client", "server"}:
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
            "server": "server",
            "dedicated_server": "dedicated server",
            "hosted": "hosted",
        }.get(self._scope_var.get(), "all targets")
        filtered_entries = self._filtered_entries()
        summary = f"{len(filtered_entries)} archives shown | {applied_summary} | {scope_label}"
        if hidden_count:
            summary += f" | {hidden_count} not tracked"
        self._summary_label.configure(text=summary)

        if not filtered_entries:
            empty_text = (
                "Drop archives into this list or use Add to track your first archive."
                if not self._search_var.get().strip() and self._filter_var.get() == "all"
                else "No archives match the current search or filter."
            )
            empty = ctk.CTkLabel(
                self._library_list,
                text=empty_text,
                justify="left",
                wraplength=420,
                text_color="#95a5a6",
                font=ctk.CTkFont(size=11),
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(6, 6), padx=10)
            self._library_widgets.append(empty)
            return

        for index, entry in enumerate(filtered_entries):
            self._add_library_row(entry, index)

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
        row.grid_columnconfigure(1, weight=1)

        color = {
            "Ready": "#3498db",
            "Applied": "#2d8a4e",
            "Disabled": "#f39c12",
            "Applied*": "#f39c12",
            "Missing": "#c0392b",
        }.get(status, "#95a5a6")
        badge = ctk.CTkLabel(row, text=status, text_color=color, width=58, anchor="w", font=ctk.CTkFont(size=10, weight="bold"))
        badge.grid(row=0, column=0, sticky="w", padx=(9, 4), pady=(6, 1))
        name = ctk.CTkLabel(
            row,
            text=self._display_name(entry.get("name", path.stem), max_len=28),
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffffff" if exists else "#777777",
        )
        name.grid(row=0, column=1, sticky="w", padx=4, pady=(6, 1))

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
        detail_label = ctk.CTkLabel(row, text=details, anchor="w", text_color="#95a5a6", wraplength=360, font=ctk.CTkFont(size=10))
        detail_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=9, pady=(0, 1))
        action_label = ctk.CTkLabel(row, text=self._last_action_text(str(path)), anchor="w", text_color="#6f7a81", font=ctk.CTkFont(size=9))
        action_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=9, pady=(0, 6))

        if is_synthetic and exists:
            action_btn = ctk.CTkButton(
                row,
                text="Track",
                width=64,
                height=24,
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._track_in_library(value),
            )
            action_btn.grid(row=0, column=2, rowspan=3, padx=(6, 9), pady=6)
        elif not is_synthetic:
            action_btn = ctk.CTkButton(
                row,
                text="Untrack",
                width=76,
                height=24,
                fg_color="#444444",
                hover_color="#666666",
                command=lambda value=str(path): self._remove_from_library(value),
            )
            action_btn.grid(row=0, column=2, rowspan=3, padx=(6, 9), pady=6)

        for widget in (row, badge, name, detail_label, action_label):
            widget.bind("<Button-1>", lambda _event, p=path: self._on_library_row_click(p))
            widget.bind("<Double-Button-1>", lambda _event, p=path: self._on_library_row_double_click(p))
            widget.bind("<Button-3>", lambda event, p=path: self._show_library_menu(event, p))
        self._library_widgets.append(row)

    def _remove_from_library(self, path_str: str) -> None:
        mods = self._mods_for_archive(path_str)
        if mods and not messagebox.askyesno(
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

    def _track_in_library(self, path_str: str) -> None:
        archive_path = Path(path_str)
        if not archive_path.is_file():
            messagebox.showerror("Archive Missing", f"The archive is no longer available:\n{path_str}")
            return
        self._add_to_library(archive_path)
        self._refresh_library_ui()

    def _show_library_menu(self, event, archive_path: Path) -> None:
        menu = tk.Menu(self, tearoff=0)
        if archive_path.is_file():
            menu.add_command(label="Install to Client", command=lambda: self._install_path_to(archive_path, InstallTarget.CLIENT))
            menu.add_command(label="Install to Server", command=lambda: self._install_path_to(archive_path, InstallTarget.SERVER))
            menu.add_command(label="Install to Dedicated Server", command=lambda: self._install_path_to(archive_path, InstallTarget.DEDICATED_SERVER))
            menu.add_command(label="Install to Both", command=lambda: self._install_path_to(archive_path, InstallTarget.BOTH))
            menu.add_command(label="Install to Hosted Server", command=lambda: self.app.open_remote_deploy(archive_path))
        if self._mods_for_archive(str(archive_path)):
            menu.add_separator()
            menu.add_command(label="Reinstall", command=self._on_reinstall)
            menu.add_command(label="Uninstall", command=self._on_uninstall)
            menu.add_command(label="Repair", command=self._on_repair)
        menu.add_separator()
        menu.add_command(label="Inspect", command=lambda: self._load_archive(archive_path))
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

    def _on_library_row_double_click(self, archive_path: Path) -> str:
        if self._single_click_job is not None:
            self.after_cancel(self._single_click_job)
            self._single_click_job = None
            self._pending_click_path = None
        self._load_archive(archive_path)
        if archive_path.is_file():
            self._open_target_chooser(archive_path)
        return "break"

    def _flush_single_click(self) -> None:
        path = self._pending_click_path
        self._single_click_job = None
        self._pending_click_path = None
        if path is not None:
            self._load_archive(path)

    def _open_target_chooser(self, archive_path: Path) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Choose Install Target")
        dialog.geometry("360x240")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=archive_path.name, font=ctk.CTkFont(size=16, weight="bold"), wraplength=320).pack(
            anchor="w", padx=16, pady=(16, 6)
        )
        ctk.CTkLabel(dialog, text="Choose where to apply this archive.", text_color="#95a5a6").pack(
            anchor="w", padx=16, pady=(0, 12)
        )
        actions = [
            ("Install to Client", lambda: self._install_path_to(archive_path, InstallTarget.CLIENT)),
            ("Install to Server", lambda: self._install_path_to(archive_path, InstallTarget.SERVER)),
            ("Install to Dedicated Server", lambda: self._install_path_to(archive_path, InstallTarget.DEDICATED_SERVER)),
            ("Install to Both", lambda: self._install_path_to(archive_path, InstallTarget.BOTH)),
            ("Install to Hosted Server", lambda: self.app.open_remote_deploy(archive_path)),
        ]
        for label, callback in actions:
            ctk.CTkButton(dialog, text=label, width=220, command=lambda cb=callback: (dialog.destroy(), cb())).pack(
                padx=16, pady=4
            )
        ctk.CTkButton(dialog, text="Cancel", width=120, fg_color="#444444", hover_color="#555555", command=dialog.destroy).pack(
            padx=16, pady=(12, 16)
        )

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
            messagebox.showinfo("No Supported Archives", "The drop did not contain a supported archive.")
            return
        for path in valid:
            self._add_to_library(path)
        self._save_library()
        self._refresh_library_ui()
        if len(valid) == 1:
            self._load_archive(valid[0])

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
        dialog.geometry("460x520")
        dialog.minsize(420, 360)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            dialog,
            text="Choose a variant",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(
            dialog,
            text=Path(info.archive_path).name,
            text_color="#95a5a6",
            wraplength=400,
            justify="left",
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
            ).grid(sticky="w", padx=6, pady=4)

        result = {"value": None}

        def _accept() -> None:
            result["value"] = choice_var.get()
            dialog.destroy()

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        ctk.CTkButton(buttons, text="Use Variant", width=120, command=_accept).pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
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
            target_text = " + ".join(
                label for label, key in (
                    ("Client", "client"),
                    ("Server", "server"),
                    ("Dedicated", "dedicated_server"),
                ) if key in self._effective_targets(mod)
            ) or "Hosted"
            lines.append(f"{self._compact_name(mod.display_name)} [{target_text}] - {'enabled' if mod.enabled else 'disabled'}")
            if mod.selected_variant:
                lines.append(f"  variant: {mod.selected_variant}")
            lines.append(f"  files: {mod.file_count}")
            lines.append(f"  archive: {Path(mod.source_archive).name}")
            lines.append("")
        return "\n".join(lines).strip()

    def _build_install_review(self, info: ArchiveInfo) -> str:
        lines: list[str] = []
        for target in (InstallTarget.CLIENT, InstallTarget.SERVER, InstallTarget.DEDICATED_SERVER, InstallTarget.BOTH):
            plan = plan_deployment(
                info,
                self.app.paths,
                target,
                self._selected_variant(),
                self._mod_name_var.get().strip() or Path(info.archive_path).stem,
            )
            label = self._target_label(target)
            if not plan.valid:
                lines.append(f"{label}: {'; '.join(plan.warnings[:2]) if plan.warnings else 'Not available'}")
                continue
            conflict_report = check_plan_conflicts(plan, self.app.manifest)
            lines.append(
                f"{label}: {len(conflict_report.conflicts)} managed conflict(s)"
                if conflict_report.has_conflicts else f"{label}: ready"
            )
        lines.append("Hosted: use the row menu or double-click target chooser to upload to a hosted profile.")
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

    def _install_current(self, target: InstallTarget) -> None:
        if self._current_info is None:
            messagebox.showwarning("No Archive", "Select an archive first.")
            return
        selected_variant = self._prompt_variant_choice(self._current_info)
        if self._current_info.has_variants and not selected_variant:
            return
        mod_name = self._mod_name_var.get().strip() or self._compact_name(Path(self._current_info.archive_path).stem)
        self._do_install(self._current_info, mod_name, target, selected_variant)

    def _install_path_to(self, archive_path: Path, target: InstallTarget) -> None:
        self._load_archive(archive_path)
        self._install_current(target)

    def _on_install_to_hosted(self) -> None:
        if self._current_info is None:
            messagebox.showwarning("No Archive", "Select an archive first.")
            return
        self.app.open_remote_deploy(self._current_info.archive_path)

    def _on_install_all(self) -> None:
        to_install = [entry for entry in self._library if Path(entry["path"]).is_file() and not self._mods_for_archive(str(entry["path"]))]
        if not to_install:
            messagebox.showinfo("Nothing to Install", "All tracked archives are already applied or missing.")
            return
        if not messagebox.askyesno(
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
                if self._do_install(info, Path(entry["path"]).stem, InstallTarget.CLIENT, quiet=True):
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
        messagebox.showinfo("Install All", "\n".join(lines))
        self.refresh_view()

    def _choose_mod(self, mods: list[ModInstall], *, purpose: str, allow_all: bool = False):
        if not mods:
            return None
        if len(mods) == 1 and not allow_all:
            return mods[0]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Choose Install")
        dialog.geometry("460x320")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Choose which install to {purpose}.", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 6)
        )
        choice_var = tk.StringVar(value=mods[0].mod_id)
        for mod in mods:
            targets = ", ".join(sorted(self._effective_targets(mod))) or "hosted"
            label = f"{self._compact_name(mod.display_name)} [{targets}]"
            if mod.selected_variant:
                label += f" - {mod.selected_variant}"
            ctk.CTkRadioButton(dialog, text=label, variable=choice_var, value=mod.mod_id).pack(anchor="w", padx=18, pady=4)
        result = {"value": None}

        def _selected() -> None:
            result["value"] = next((mod for mod in mods if mod.mod_id == choice_var.get()), None)
            dialog.destroy()

        def _all() -> None:
            result["value"] = "all"
            dialog.destroy()

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(16, 16))
        ctk.CTkButton(buttons, text="Use Selected", width=130, command=_selected).pack(side="left")
        if allow_all:
            ctk.CTkButton(buttons, text="Use All", width=100, fg_color="#e67e22", hover_color="#ca6b18", command=_all).pack(
                side="left", padx=8
            )
        ctk.CTkButton(buttons, text="Cancel", width=100, fg_color="#444444", hover_color="#555555", command=dialog.destroy).pack(
            side="right"
        )
        self.wait_window(dialog)
        return result["value"]

    def _on_uninstall(self) -> None:
        if not self._selected_library_path:
            messagebox.showinfo("No Selection", "Select an archive first.")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            messagebox.showinfo("Not Installed", "This archive is not currently installed.")
            return
        selected = self._choose_mod(mods, purpose="uninstall", allow_all=True)
        if selected is None:
            return
        targets = mods if selected == "all" else [selected]
        if not messagebox.askyesno("Confirm Uninstall", f"Uninstall {len(targets)} install(s) from this archive?"):
            return
        for mod in targets:
            record = self.app.installer.uninstall(mod)
            self.app.manifest.add_record(record)
            self.app.manifest.remove_mod(mod.mod_id)
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self.refresh_view()

    def _on_reinstall(self) -> None:
        if not self._selected_library_path:
            messagebox.showinfo("No Selection", "Select an archive first.")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            messagebox.showinfo("Not Installed", "This archive is not currently installed.")
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
        if not messagebox.askyesno("Confirm Reinstall", f"Reinstall '{selected.display_name}' from:\n{archive_path.name}"):
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

    def _on_repair(self) -> None:
        if not self._selected_library_path:
            messagebox.showinfo("No Selection", "Select an archive first.")
            return
        mods = self._mods_for_archive(self._selected_library_path)
        if not mods:
            messagebox.showinfo("Not Installed", "This archive is not currently installed.")
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
        messagebox.showinfo("Repair", message)
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
                messagebox.showerror("Missing Server Path", "Configure the bundled server path in Settings first.")
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
            if not messagebox.askyesno(
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
                messagebox.showinfo("Installed", f"Installed '{mod.display_name}' to {self._target_label(target)}.")
            log.info("Installed from Mods tab: %s", mod.display_name)
            return True
        except Exception as exc:
            log.error("Install failed: %s", exc)
            if not quiet:
                messagebox.showerror("Install Failed", str(exc))
            return False
