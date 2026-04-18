"""Remote tab - deploy archive-library mods to rented servers over SFTP."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.archive_inspector import inspect_archive
from ...core.remote_deployer import plan_remote_deployment
from ...models.remote_profile import RemoteProfile

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class RemoteTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._current_info = None
        self._profile_labels: dict[str, str] = {}
        self._archive_labels: dict[str, str] = {}
        self._archive_labels_by_path: dict[str, str] = {}
        self._archive_var = ctk.StringVar(value="(none)")
        self._variant_var = ctk.StringVar(value="(none)")
        self._deploy_dialog: ctk.CTkToplevel | None = None
        self._deploy_archive_menu: ctk.CTkOptionMenu | None = None
        self._deploy_variant_frame: ctk.CTkFrame | None = None
        self._deploy_variant_menu: ctk.CTkOptionMenu | None = None
        self._deploy_archive_label: ctk.CTkLabel | None = None
        self._deploy_info_box: ctk.CTkTextbox | None = None
        self._deploy_dialog_status: ctk.CTkLabel | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._panes = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            showhandle=True,
            handlesize=8,
            bd=0,
            relief=tk.FLAT,
            bg="#2b2b2b",
            sashrelief=tk.RAISED,
        )
        self._panes.grid(row=0, column=0, sticky="nsew")

        self._left_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        self._right_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        self._panes.add(self._left_host, minsize=320, width=390)
        self._panes.add(self._right_host, minsize=420)

        self._build_profile_panel(self._left_host)
        self._build_deploy_panel(self._right_host)
        self.refresh_profiles()
        self.refresh_archives()

    def _build_profile_panel(self, parent) -> None:
        panel = ctk.CTkScrollableFrame(parent, width=360)
        panel.pack(fill="both", expand=True, padx=(8, 4), pady=8)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel,
            text="Remote Server Setup",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            panel,
            text="Most servers only need host, username, auth, and the remote root that contains R5.",
            text_color="#95a5a6",
            justify="left",
            wraplength=320,
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        selector = ctk.CTkFrame(panel, fg_color="transparent")
        selector.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        selector.grid_columnconfigure(0, weight=1)

        self._profile_var = ctk.StringVar(value="(new)")
        self._profile_menu = ctk.CTkOptionMenu(
            selector,
            variable=self._profile_var,
            values=["(new)"],
            command=lambda _value: self._on_profile_selected(),
            width=220,
        )
        self._profile_menu.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            selector,
            text="New",
            width=70,
            command=self._new_profile,
        ).grid(row=0, column=1, sticky="e")

        self._vars = {
            "name": ctk.StringVar(),
            "host": ctk.StringVar(),
            "port": ctk.StringVar(value="22"),
            "username": ctk.StringVar(),
            "password": ctk.StringVar(),
            "private_key_path": ctk.StringVar(),
            "remote_root_dir": ctk.StringVar(),
            "remote_mods_dir": ctk.StringVar(),
            "remote_server_description_path": ctk.StringVar(),
            "remote_save_root": ctk.StringVar(),
            "restart_command": ctk.StringVar(),
        }
        self._auth_mode_var = ctk.StringVar(value="password")
        self._advanced_visible = False
        self._suspend_preview_updates = False

        basic = ctk.CTkFrame(panel)
        basic.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))
        basic.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            basic,
            text="Basic Setup",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6))

        ctk.CTkLabel(basic, text="Profile Name:").grid(
            row=1, column=0, sticky="w", padx=(10, 4), pady=4
        )
        ctk.CTkEntry(basic, textvariable=self._vars["name"]).grid(
            row=1, column=1, sticky="ew", padx=(4, 10), pady=4
        )

        host_row = ctk.CTkFrame(basic, fg_color="transparent")
        host_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=4)
        host_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(host_row, text="Host:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        ctk.CTkEntry(host_row, textvariable=self._vars["host"]).grid(
            row=0, column=1, sticky="ew", padx=(4, 8)
        )
        ctk.CTkLabel(host_row, text="Port:").grid(row=0, column=2, sticky="w", padx=(0, 4))
        ctk.CTkEntry(host_row, textvariable=self._vars["port"], width=72).grid(
            row=0, column=3, sticky="w", padx=(4, 0)
        )

        ctk.CTkLabel(basic, text="Username:").grid(
            row=3, column=0, sticky="w", padx=(10, 4), pady=4
        )
        ctk.CTkEntry(basic, textvariable=self._vars["username"]).grid(
            row=3, column=1, sticky="ew", padx=(4, 10), pady=4
        )

        ctk.CTkLabel(basic, text="Auth Mode:").grid(
            row=4, column=0, sticky="w", padx=(10, 4), pady=4
        )
        self._auth_menu = ctk.CTkOptionMenu(
            basic,
            variable=self._auth_mode_var,
            values=["password", "key"],
            command=lambda _value: self._toggle_auth_fields(),
            width=120,
        )
        self._auth_menu.grid(row=4, column=1, sticky="w", padx=(4, 10), pady=4)

        self._auth_frame = ctk.CTkFrame(basic, fg_color="transparent")
        self._auth_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 0))
        self._auth_frame.grid_columnconfigure(1, weight=1)

        self._password_row = ctk.CTkFrame(self._auth_frame, fg_color="transparent")
        self._password_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self._password_row, text="Password:").grid(
            row=0, column=0, sticky="w", padx=(0, 4), pady=4
        )
        self._password_entry = ctk.CTkEntry(self._password_row, textvariable=self._vars["password"], show="*")
        self._password_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)

        self._key_row = ctk.CTkFrame(self._auth_frame, fg_color="transparent")
        self._key_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self._key_row, text="Private Key:").grid(
            row=0, column=0, sticky="w", padx=(0, 4), pady=4
        )
        self._private_key_entry = ctk.CTkEntry(self._key_row, textvariable=self._vars["private_key_path"])
        self._private_key_entry.grid(row=0, column=1, sticky="ew", padx=(4, 6), pady=4)
        ctk.CTkButton(
            self._key_row,
            text="Browse",
            width=82,
            command=self._browse_private_key,
        ).grid(row=0, column=2, sticky="e", padx=(0, 6))

        self._auth_help_label = ctk.CTkLabel(
            basic,
            text="",
            text_color="#95a5a6",
            justify="left",
            wraplength=300,
        )
        self._auth_help_label.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 4))

        ctk.CTkLabel(basic, text="Remote Root:").grid(
            row=7, column=0, sticky="w", padx=(10, 4), pady=4
        )
        ctk.CTkEntry(
            basic,
            textvariable=self._vars["remote_root_dir"],
            placeholder_text="Folder on the remote host that contains R5",
        ).grid(row=7, column=1, sticky="ew", padx=(4, 10), pady=4)
        ctk.CTkLabel(
            basic,
            text="Example: /home/container or C:/Games/WindroseServer",
            text_color="#95a5a6",
            justify="left",
            wraplength=300,
        ).grid(row=8, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 6))

        basic_actions = ctk.CTkFrame(basic, fg_color="transparent")
        basic_actions.grid(row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        ctk.CTkButton(
            basic_actions,
            text="Fill From Root",
            width=120,
            command=self._apply_root_defaults,
        ).pack(side="left")
        ctk.CTkButton(
            basic_actions,
            text="Test Connection",
            width=120,
            command=self._test_connection,
        ).pack(side="right")

        preview = ctk.CTkFrame(panel)
        preview.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 10))
        preview.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            preview,
            text="Resolved Paths",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            preview,
            text="These are the actual paths the app will use. Leave overrides blank for the normal layout.",
            text_color="#95a5a6",
            justify="left",
            wraplength=320,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

        self._preview_labels: dict[str, ctk.CTkLabel] = {}
        preview_rows = [
            ("mods", "Mods Dir"),
            ("server", "Server Config"),
            ("save", "Save Root"),
        ]
        for row_idx, (key, label) in enumerate(preview_rows, start=2):
            ctk.CTkLabel(preview, text=label + ":").grid(
                row=row_idx, column=0, sticky="nw", padx=(10, 6), pady=4
            )
            value_label = ctk.CTkLabel(
                preview,
                text="(not set)",
                anchor="w",
                justify="left",
                text_color="#d0d0d0",
                font=ctk.CTkFont(family="Consolas", size=11),
                wraplength=245,
            )
            value_label.grid(row=row_idx, column=1, sticky="ew", padx=(0, 10), pady=4)
            self._preview_labels[key] = value_label

        advanced_header = ctk.CTkFrame(panel, fg_color="transparent")
        advanced_header.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 6))
        advanced_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            advanced_header,
            text="Advanced",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self._advanced_btn = ctk.CTkButton(
            advanced_header,
            text="Show",
            width=80,
            fg_color="#555555",
            hover_color="#666666",
            command=self._toggle_advanced,
        )
        self._advanced_btn.grid(row=0, column=1, sticky="e")

        self._advanced_frame = ctk.CTkFrame(panel)
        self._advanced_frame.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._advanced_frame.grid_columnconfigure(1, weight=1)

        advanced_rows = [
            ("remote_mods_dir", "Mods Dir Override"),
            ("remote_server_description_path", "Server Config Override"),
            ("remote_save_root", "Save Root Override"),
            ("restart_command", "Restart Command"),
        ]
        for row_idx, (key, label) in enumerate(advanced_rows):
            ctk.CTkLabel(self._advanced_frame, text=label + ":").grid(
                row=row_idx, column=0, sticky="w", padx=(10, 4), pady=4
            )
            ctk.CTkEntry(self._advanced_frame, textvariable=self._vars[key]).grid(
                row=row_idx, column=1, sticky="ew", padx=(4, 10), pady=4
            )
        ctk.CTkLabel(
            self._advanced_frame,
            text="Use overrides only if your host does not follow the normal layout derived from the root.",
            text_color="#95a5a6",
            justify="left",
            wraplength=320,
        ).grid(row=len(advanced_rows), column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 10))
        self._advanced_frame.grid_remove()

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 8))
        ctk.CTkButton(
            actions,
            text="Save Profile",
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=self._save_profile,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Delete",
            width=80,
            fg_color="#c0392b",
            hover_color="#962d22",
            command=self._delete_profile,
        ).pack(side="left")

        self._profile_status = ctk.CTkLabel(
            panel,
            text="",
            text_color="#95a5a6",
            justify="left",
            wraplength=320,
        )
        self._profile_status.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 12))

        for var in self._vars.values():
            var.trace_add("write", self._on_profile_fields_changed)
        self._auth_mode_var.trace_add("write", self._on_profile_fields_changed)
        self._toggle_auth_fields()
        self._update_profile_preview()

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self._advanced_frame.grid()
            self._advanced_btn.configure(text="Hide")
        else:
            self._advanced_frame.grid_remove()
            self._advanced_btn.configure(text="Show")

    def _on_profile_fields_changed(self, *_args) -> None:
        if self._suspend_preview_updates:
            return
        self._toggle_auth_fields()
        self._update_profile_preview()

    def _preview_profile(self) -> RemoteProfile:
        profile_id = getattr(self, "_active_profile_id", None) or RemoteProfile.new().profile_id
        port_raw = self._vars["port"].get().strip()
        try:
            port = int(port_raw or 22)
        except ValueError:
            port = 22
        profile = RemoteProfile(
            profile_id=profile_id,
            name=self._vars["name"].get().strip() or "Remote Profile",
            host=self._vars["host"].get().strip(),
            port=port,
            username=self._vars["username"].get().strip(),
            auth_mode=self._auth_mode_var.get(),
            password=self._vars["password"].get(),
            private_key_path=self._vars["private_key_path"].get().strip(),
            remote_root_dir=self._vars["remote_root_dir"].get().strip(),
            remote_mods_dir=self._vars["remote_mods_dir"].get().strip(),
            remote_server_description_path=self._vars["remote_server_description_path"].get().strip(),
            remote_save_root=self._vars["remote_save_root"].get().strip(),
            restart_command=self._vars["restart_command"].get().strip(),
        )
        profile.apply_root_defaults(overwrite=False)
        return profile

    def _update_profile_preview(self) -> None:
        profile = self._preview_profile()
        self._preview_labels["mods"].configure(text=profile.resolved_mods_dir() or "(not set)")
        self._preview_labels["server"].configure(
            text=profile.resolved_server_description_path() or "(not set)"
        )
        self._preview_labels["save"].configure(text=profile.resolved_save_root() or "(not set)")

    def _build_deploy_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent)
        panel.pack(fill="both", expand=True, padx=(4, 8), pady=8)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            panel,
            text="Remote Actions",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            panel,
            text="Use Mods -> Install to Remote for the normal workflow. This tab now keeps setup and server actions separate from one-off direct deploys.",
            text_color="#95a5a6",
            justify="left",
            wraplength=520,
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        utility_row = ctk.CTkFrame(panel, fg_color="transparent")
        utility_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        ctk.CTkButton(
            utility_row,
            text="Direct Deploy...",
            width=120,
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=self._open_deploy_dialog,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            utility_row,
            text="Open Mods Tab",
            width=110,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: self.app._tabview.set("Mods"),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            utility_row,
            text="List Remote Files",
            width=120,
            command=self._list_remote_files,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            utility_row,
            text="Restart Server",
            width=110,
            fg_color="#e67e22",
            hover_color="#ca6b18",
            command=self._restart_remote_server,
        ).pack(side="left", padx=6)

        direct_hint = ctk.CTkFrame(panel)
        direct_hint.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))
        direct_hint.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            direct_hint,
            text="Direct Deploy",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self._deploy_hint_label = ctk.CTkLabel(
            direct_hint,
            text="Opens a compact picker with archive names only. For normal use, deploy from the Mods tab.",
            text_color="#95a5a6",
            justify="left",
            wraplength=500,
        )
        self._deploy_hint_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        self._info_box = ctk.CTkTextbox(
            panel,
            state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self._info_box.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self._set_info_text(
            "Remote activity appears here.\n\n"
            "Use Direct Deploy only for one-off uploads.\n"
            "Use Mods -> Install to Remote for the regular workflow."
        )

        self._deploy_status = ctk.CTkLabel(panel, text="", text_color="#95a5a6")
        self._deploy_status.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _open_deploy_dialog(self) -> None:
        if self._deploy_dialog and self._deploy_dialog.winfo_exists():
            self._sync_deploy_dialog()
            self._deploy_dialog.deiconify()
            self._deploy_dialog.lift()
            self._deploy_dialog.focus()
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Direct Deploy")
        dialog.geometry("720x520")
        dialog.minsize(620, 420)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(4, weight=1)
        dialog.protocol("WM_DELETE_WINDOW", self._close_deploy_dialog)
        self._deploy_dialog = dialog

        ctk.CTkLabel(
            dialog,
            text="Direct Deploy",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 4))
        ctk.CTkLabel(
            dialog,
            text="Choose a library archive and upload it straight to the remote mods folder. The picker uses archive names, not full file paths.",
            text_color="#95a5a6",
            justify="left",
            wraplength=660,
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        form = ctk.CTkFrame(dialog)
        form.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Archive:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self._deploy_archive_menu = ctk.CTkOptionMenu(
            form,
            variable=self._archive_var,
            values=["(none)"],
            command=lambda _value: self._on_archive_selected(),
            width=320,
        )
        self._deploy_archive_menu.grid(row=0, column=1, sticky="ew", padx=(4, 12), pady=(12, 4))

        self._deploy_archive_label = ctk.CTkLabel(
            form,
            text="Pick an archive here, or send one from the Mods tab.",
            text_color="#95a5a6",
            justify="left",
            wraplength=560,
        )
        self._deploy_archive_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 6))

        self._deploy_variant_frame = ctk.CTkFrame(form, fg_color="transparent")
        self._deploy_variant_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=4)
        ctk.CTkLabel(self._deploy_variant_frame, text="Variant:").pack(side="left")
        self._deploy_variant_menu = ctk.CTkOptionMenu(
            self._deploy_variant_frame,
            variable=self._variant_var,
            values=["(none)"],
            width=240,
        )
        self._deploy_variant_menu.pack(side="left", padx=8)

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 8))
        ctk.CTkButton(
            btn_row,
            text="Deploy",
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=self._deploy_selected_archive,
        ).pack(side="left")
        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=100,
            fg_color="#555555",
            hover_color="#666666",
            command=self._close_deploy_dialog,
        ).pack(side="right")

        self._deploy_info_box = ctk.CTkTextbox(
            dialog,
            state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self._deploy_info_box.grid(row=4, column=0, sticky="nsew", padx=14, pady=(0, 8))

        self._deploy_dialog_status = ctk.CTkLabel(dialog, text="", text_color="#95a5a6")
        self._deploy_dialog_status.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 14))

        self._sync_deploy_dialog()

    def _close_deploy_dialog(self) -> None:
        dialog = self._deploy_dialog
        self._deploy_dialog = None
        self._deploy_archive_menu = None
        self._deploy_variant_frame = None
        self._deploy_variant_menu = None
        self._deploy_archive_label = None
        self._deploy_info_box = None
        self._deploy_dialog_status = None
        if dialog and dialog.winfo_exists():
            dialog.destroy()

    def _sync_deploy_dialog(self) -> None:
        if not (self._deploy_dialog and self._deploy_dialog.winfo_exists()):
            return

        values = list(self._archive_labels.keys()) or ["(none)"]
        if self._deploy_archive_menu is not None:
            self._deploy_archive_menu.configure(values=values)

        current_label = self._archive_var.get()
        if current_label not in values:
            preferred = self.app._mods_tab.selected_archive_path()
            preferred_label = self._archive_labels_by_path.get(str(preferred)) if preferred else None
            self._archive_var.set(preferred_label or values[0])

        self._on_archive_selected()

    def _archive_label_for_path(self, archive_path: str) -> str:
        path = Path(archive_path)
        base_label = path.name
        if base_label not in self._archive_labels:
            return base_label

        parent_label = path.parent.name or path.parent.drive.replace(":", "") or "archive"
        candidate = f"{path.name} - {parent_label}"
        counter = 2
        while candidate in self._archive_labels:
            candidate = f"{path.name} - {parent_label} ({counter})"
            counter += 1
        return candidate

    def _archive_path_from_selection(self) -> Path | None:
        archive_path = self._archive_labels.get(self._archive_var.get())
        if not archive_path:
            return None
        return Path(archive_path)

    def refresh_profiles(self) -> None:
        profiles = self.app.remote_profiles.list_profiles()
        self._profile_labels = {}
        values = ["(new)"]
        for profile in profiles:
            label = profile.name
            if profile.host:
                label = f"{profile.name} [{profile.host}]"
            self._profile_labels[label] = profile.profile_id
            values.append(label)
        self._profile_menu.configure(values=values)
        if self._profile_var.get() not in values:
            self._profile_var.set(values[0])
            self._on_profile_selected()

    def refresh_archives(self) -> None:
        entries = self.app._mods_tab.library_entries()
        archive_paths = [str(Path(entry["path"])) for entry in entries if Path(entry["path"]).is_file()]

        self._archive_labels = {}
        self._archive_labels_by_path = {}
        for archive_path in archive_paths:
            label = self._archive_label_for_path(archive_path)
            self._archive_labels[label] = archive_path
            self._archive_labels_by_path[archive_path] = label

        values = list(self._archive_labels.keys()) or ["(none)"]
        preferred = self.app._mods_tab.selected_archive_path()
        preferred_label = self._archive_labels_by_path.get(str(preferred)) if preferred else None
        if preferred_label:
            self._archive_var.set(preferred_label)
        elif self._archive_var.get() not in values:
            self._archive_var.set(values[0])

        self._sync_deploy_dialog()
        self._on_archive_selected()

    def select_archive_path(self, archive_path: str | Path) -> None:
        archive_str = str(Path(archive_path))
        archive_label = self._archive_labels_by_path.get(archive_str)
        if archive_label:
            self._open_deploy_dialog()
            self._archive_var.set(archive_label)
            self._on_archive_selected()

    def _toggle_auth_fields(self) -> None:
        auth_mode = self._auth_mode_var.get()
        if auth_mode == "password":
            if self._key_row.winfo_manager():
                self._key_row.grid_remove()
            if not self._password_row.winfo_manager():
                self._password_row.grid(row=0, column=0, sticky="ew")
            self._password_entry.configure(state="normal")
            self._private_key_entry.configure(state="disabled")
            self._auth_help_label.configure(
                text="Use the real server account password. Windows PIN is not an SSH password.",
            )
        else:
            if self._password_row.winfo_manager():
                self._password_row.grid_remove()
            if not self._key_row.winfo_manager():
                self._key_row.grid(row=0, column=0, sticky="ew")
            self._password_entry.configure(state="disabled")
            self._private_key_entry.configure(state="normal")
            self._auth_help_label.configure(
                text="Choose a private key file. The app stores only the path, not the key contents. Most keys live in your .ssh folder.",
            )

    def _browse_private_key(self) -> None:
        path = filedialog.askopenfilename(
            title="Select SSH Private Key",
            filetypes=[
                ("Private Keys", "*.pem *.key *.ppk *.pub *"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self._vars["private_key_path"].set(path)

    def _on_profile_selected(self) -> None:
        label = self._profile_var.get()
        profile_id = self._profile_labels.get(label)
        profile = self.app.remote_profiles.get_profile(profile_id) if profile_id else None
        if profile is None:
            self._populate_profile(RemoteProfile.new())
            self._profile_var.set("(new)")
            return
        self._populate_profile(profile)

    def _populate_profile(self, profile: RemoteProfile) -> None:
        self._suspend_preview_updates = True
        try:
            self._active_profile_id = profile.profile_id
            self._vars["name"].set(profile.name)
            self._vars["host"].set(profile.host)
            self._vars["port"].set(str(profile.port))
            self._vars["username"].set(profile.username)
            self._vars["password"].set(profile.password)
            self._vars["private_key_path"].set(profile.private_key_path)
            self._vars["remote_root_dir"].set(profile.remote_root_dir)
            self._vars["remote_mods_dir"].set(profile.remote_mods_dir)
            self._vars["remote_server_description_path"].set(profile.remote_server_description_path)
            self._vars["remote_save_root"].set(profile.remote_save_root)
            self._vars["restart_command"].set(profile.restart_command)
            self._auth_mode_var.set(profile.auth_mode or "password")
        finally:
            self._suspend_preview_updates = False
        self._toggle_auth_fields()
        self._update_profile_preview()
        self._profile_status.configure(
            text=self._profile_summary(profile),
            text_color="#95a5a6",
        )

    def _read_profile(self) -> RemoteProfile:
        port_raw = self._vars["port"].get().strip()
        if port_raw:
            int(port_raw)
        profile = self._preview_profile()
        return profile

    def _profile_summary(self, profile: RemoteProfile) -> str:
        mods_dir = profile.resolved_mods_dir() or "(not set)"
        server_desc = profile.resolved_server_description_path() or "(not set)"
        save_root = profile.resolved_save_root() or "(not set)"
        return (
            f"Mods: {mods_dir} | ServerDescription: {server_desc} | Saves: {save_root}"
        )

    def _apply_root_defaults(self) -> None:
        try:
            profile = self._read_profile()
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a whole number.")
            return

        if not profile.normalized_root_dir():
            messagebox.showwarning(
                "Remote Root Required",
                "Enter Remote Game/Server Root first. It should point to the folder that contains R5.",
            )
            return

        profile.apply_root_defaults(overwrite=True)
        self._populate_profile(profile)
        self._profile_status.configure(
            text=f"Filled default remote paths from root. {self._profile_summary(profile)}",
            text_color="#2d8a4e",
        )

    def _ensure_profile_ready(self, profile: RemoteProfile, *, require_target: bool = False) -> bool:
        if not profile.host or not profile.username:
            messagebox.showerror("Missing Fields", "Host and username are required.")
            return False
        if profile.auth_mode == "password" and not profile.password:
            messagebox.showerror("Missing Fields", "Password is required for password authentication.")
            return False
        if profile.auth_mode == "key":
            raw_key = profile.private_key_path.strip()
            if not raw_key:
                messagebox.showerror("Missing Fields", "Private key path is required for key authentication.")
                return False
            if "\n" in raw_key or "\r" in raw_key:
                messagebox.showerror(
                    "Invalid Private Key",
                    "Private Key must be a file path, not pasted key contents.",
                )
                return False
            expanded = os.path.expandvars(raw_key)
            key_path = Path(expanded).expanduser()
            if not key_path.is_file():
                messagebox.showerror(
                    "Missing Private Key",
                    f"Private key file not found:\n{key_path}",
                )
                return False
            profile.private_key_path = str(key_path)
        if require_target and not profile.resolved_mods_dir():
            messagebox.showerror(
                "Missing Remote Path",
                "Set Remote Game/Server Root or Remote Mods Dir first.",
            )
            return False
        return True

    def _new_profile(self) -> None:
        self._profile_var.set("(new)")
        self._populate_profile(RemoteProfile.new())
        self._profile_status.configure(
            text="Creating a new profile. Start with host/login plus Remote Game/Server Root.",
            text_color="#95a5a6",
        )

    def _save_profile(self) -> None:
        try:
            profile = self._read_profile()
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a whole number.")
            return

        if not self._ensure_profile_ready(profile):
            return

        self.app.remote_profiles.upsert(profile)
        self.refresh_profiles()
        for label, profile_id in self._profile_labels.items():
            if profile_id == profile.profile_id:
                self._profile_var.set(label)
                break
        self._profile_status.configure(
            text=f"Saved profile '{profile.name}'. {self._profile_summary(profile)}",
            text_color="#2d8a4e",
        )
        self.app.refresh_remote_profile_views()
        log.info("Saved remote profile: %s", profile.name)

    def _delete_profile(self) -> None:
        label = self._profile_var.get()
        profile_id = self._profile_labels.get(label)
        if not profile_id:
            return
        profile = self.app.remote_profiles.get_profile(profile_id)
        if profile is None:
            return
        if not self.app.confirm_action(
            "destructive",
            "Delete Profile",
            f"Delete remote profile '{profile.name}'?",
        ):
            return

        self.app.remote_profiles.remove(profile.profile_id)
        self.refresh_profiles()
        self.app.refresh_remote_profile_views()
        self._new_profile()

    def _on_archive_selected(self) -> None:
        archive_path = self._archive_path_from_selection()
        if archive_path is None or not archive_path.is_file():
            self._current_info = None
            if self._deploy_archive_label is not None:
                self._deploy_archive_label.configure(
                    text="Pick an archive here, or send one from the Mods tab."
                )
            if self._deploy_variant_frame is not None:
                self._deploy_variant_frame.grid_remove()
            self._set_deploy_info_text(
                "Choose an archive from the library to inspect it here.\n"
                "Only archive names are shown in the picker to keep the dialog readable."
            )
            return

        try:
            info = inspect_archive(archive_path)
        except Exception as exc:
            self._current_info = None
            if self._deploy_archive_label is not None:
                self._deploy_archive_label.configure(
                    text=f"Failed to inspect {archive_path.name}"
                )
            self._set_deploy_info_text(f"Failed to inspect {archive_path.name}:\n{exc}")
            return

        self._current_info = info
        if self._deploy_archive_label is not None:
            self._deploy_archive_label.configure(
                text=f"Selected archive: {archive_path.name}"
            )
        if info.has_variants:
            variants = []
            for group in info.variant_groups:
                variants.extend(group.variant_names)
            if self._deploy_variant_menu is not None:
                self._deploy_variant_menu.configure(values=variants)
            self._variant_var.set(variants[0] if variants else "(none)")
            if self._deploy_variant_frame is not None:
                self._deploy_variant_frame.grid()
        else:
            if self._deploy_variant_menu is not None:
                self._deploy_variant_menu.configure(values=["(none)"])
            self._variant_var.set("(none)")
            if self._deploy_variant_frame is not None:
                self._deploy_variant_frame.grid_remove()

        self._set_deploy_info_text(self._describe_archive(info))

    def _describe_archive(self, info) -> str:
        lines = [
            f"Archive: {Path(info.archive_path).name}",
            f"Type:    {info.archive_type.value}",
            f"Files:   {info.total_files}",
            "",
        ]
        if info.pak_entries:
            lines.append("PAK files:")
            lines.extend(f"  {Path(entry.path).name}" for entry in info.pak_entries)
        if info.loose_entries:
            lines.append("")
            lines.append("Loose files:")
            lines.extend(f"  {entry.path}" for entry in info.loose_entries[:20])
        if info.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"  ! {warning}" for warning in info.warnings)
        return "\n".join(lines)

    def _set_info_text(self, text: str) -> None:
        self._info_box.configure(state="normal")
        self._info_box.delete("1.0", "end")
        self._info_box.insert("1.0", text)
        self._info_box.configure(state="disabled")

    def _set_deploy_info_text(self, text: str) -> None:
        if self._deploy_info_box is None:
            return
        self._deploy_info_box.configure(state="normal")
        self._deploy_info_box.delete("1.0", "end")
        self._deploy_info_box.insert("1.0", text)
        self._deploy_info_box.configure(state="disabled")

    def _set_deploy_dialog_status(self, text: str, color: str = "#95a5a6") -> None:
        if self._deploy_dialog_status is not None:
            self._deploy_dialog_status.configure(text=text, text_color=color)

    def _selected_variant(self) -> Optional[str]:
        value = self._variant_var.get()
        return None if value == "(none)" else value

    def _test_connection(self) -> None:
        try:
            profile = self._read_profile()
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a whole number.")
            return
        if not self._ensure_profile_ready(profile):
            return
        self._profile_status.configure(text="Testing connection...", text_color="#95a5a6")

        def _work() -> None:
            try:
                ok, message = self.app.remote_deployer.test_connection(profile)
            except Exception as exc:
                ok, message = False, str(exc)
            self.after(0, lambda: self._profile_status.configure(
                text=message,
                text_color="#2d8a4e" if ok else "#c0392b",
            ))

        threading.Thread(target=_work, daemon=True).start()

    def _deploy_selected_archive(self) -> None:
        if self._current_info is None:
            messagebox.showwarning("No Archive", "Choose an archive to deploy first.")
            return

        try:
            profile = self._read_profile()
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a whole number.")
            return
        if not self._ensure_profile_ready(profile, require_target=True):
            return

        selected_variant = self._selected_variant()
        plan = plan_remote_deployment(
            self._current_info,
            profile,
            selected_variant=selected_variant,
            mod_name=Path(self._current_info.archive_path).stem,
        )
        if not plan.valid:
            messagebox.showerror("Remote Plan Error", "\n".join(plan.warnings))
            return

        self._deploy_status.configure(text="Deploying to remote server...", text_color="#95a5a6")
        self._set_deploy_dialog_status("Deploying to remote server...", "#95a5a6")

        def _work() -> None:
            try:
                result = self.app.remote_deployer.deploy(plan, profile)
                message = result.summary
                if profile.restart_command.strip():
                    message += " - restart command available."
                else:
                    message += " - restart the server manually when ready."
                info_text = self._describe_archive(self._current_info)
                info_text += "\n\nRemote deployment summary:\n"
                for path in result.uploaded:
                    info_text += f"  uploaded  {path}\n"
                for entry in result.failed:
                    info_text += f"  failed    {entry}\n"
                for entry in result.skipped:
                    info_text += f"  skipped   {entry}\n"
                self.after(0, lambda: (
                    self._deploy_status.configure(
                        text=message,
                        text_color="#2d8a4e" if not result.failed else "#e67e22",
                    ),
                    self._set_info_text(info_text),
                    self._set_deploy_dialog_status(
                        message,
                        "#2d8a4e" if not result.failed else "#e67e22",
                    ),
                    self._set_deploy_info_text(info_text),
                ))
            except Exception as exc:
                self.after(0, lambda: (
                    self._deploy_status.configure(
                        text=f"Remote deploy failed: {exc}",
                        text_color="#c0392b",
                    ),
                    self._set_deploy_dialog_status(
                        f"Remote deploy failed: {exc}",
                        "#c0392b",
                    ),
                ))

        threading.Thread(target=_work, daemon=True).start()

    def _list_remote_files(self) -> None:
        try:
            profile = self._read_profile()
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a whole number.")
            return
        if not self._ensure_profile_ready(profile, require_target=True):
            return

        self._deploy_status.configure(text="Listing remote files...", text_color="#95a5a6")

        def _work() -> None:
            try:
                files = self.app.remote_deployer.list_remote_files(profile)
                text = f"Remote files under {profile.resolved_mods_dir()}:\n\n"
                if files:
                    text += "\n".join(files)
                else:
                    text += "(no files found)"
                self.after(0, lambda: (
                    self._set_info_text(text),
                    self._deploy_status.configure(
                        text=f"Found {len(files)} remote file(s).",
                        text_color="#2d8a4e",
                    ),
                ))
            except Exception as exc:
                self.after(0, lambda: self._deploy_status.configure(
                    text=f"Remote listing failed: {exc}",
                    text_color="#c0392b",
                ))

        threading.Thread(target=_work, daemon=True).start()

    def _restart_remote_server(self) -> None:
        try:
            profile = self._read_profile()
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a whole number.")
            return
        if not self._ensure_profile_ready(profile):
            return

        self._deploy_status.configure(text="Running restart command...", text_color="#95a5a6")

        def _work() -> None:
            try:
                ok, message = self.app.remote_deployer.restart_remote(profile)
            except Exception as exc:
                ok, message = False, str(exc)
            self.after(0, lambda: self._deploy_status.configure(
                text=message or ("Restart command finished." if ok else "Restart failed."),
                text_color="#2d8a4e" if ok else "#c0392b",
            ))

        threading.Thread(target=_work, daemon=True).start()
