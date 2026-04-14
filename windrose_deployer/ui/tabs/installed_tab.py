"""Installed tab — view and manage installed mods."""
from __future__ import annotations

import logging
import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...models.mod_install import ModInstall

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class InstalledTab(ctk.CTkFrame):
    def __init__(self, master, app: AppWindow, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._selected_mod: Optional[ModInstall] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_mod_list()
        self._build_details_panel()

    def _build_toolbar(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(frame, text="Installed Mods", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left", padx=8)

        self._refresh_btn = ctk.CTkButton(frame, text="Refresh", width=80, command=self.refresh)
        self._refresh_btn.pack(side="right", padx=8)

        self._uninstall_all_btn = ctk.CTkButton(
            frame, text="Uninstall All", width=100,
            fg_color="#c0392b", hover_color="#962d22",
            command=self._on_uninstall_all,
        )
        self._uninstall_all_btn.pack(side="right", padx=4)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        self._search_entry = ctk.CTkEntry(frame, textvariable=self._search_var,
                                          placeholder_text="Search mods...", width=200)
        self._search_entry.pack(side="right", padx=8)

    def _build_mod_list(self) -> None:
        self._list_frame = ctk.CTkScrollableFrame(self)
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(4, 8))
        self._list_frame.grid_columnconfigure(0, weight=1)
        self._mod_widgets: list[ctk.CTkFrame] = []

    def _build_details_panel(self) -> None:
        self._details = ctk.CTkFrame(self, width=300)
        self._details.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(4, 8))
        self._details.grid_propagate(False)

        self._detail_name = ctk.CTkLabel(self._details, text="Select a mod",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         wraplength=280)
        self._detail_name.pack(padx=8, pady=(12, 4), anchor="w")

        self._detail_info = ctk.CTkTextbox(self._details, height=200, state="disabled",
                                           font=ctk.CTkFont(family="Consolas", size=11))
        self._detail_info.pack(fill="both", expand=True, padx=8, pady=4)

        btn_frame = ctk.CTkFrame(self._details, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(4, 8))

        self._toggle_btn = ctk.CTkButton(btn_frame, text="Disable", width=80,
                                         command=self._on_toggle)
        self._toggle_btn.pack(side="left", padx=(0, 4))

        self._uninstall_btn = ctk.CTkButton(btn_frame, text="Uninstall", width=80,
                                            fg_color="#c0392b", hover_color="#962d22",
                                            command=self._on_uninstall)
        self._uninstall_btn.pack(side="left", padx=4)

        self._reinstall_btn = ctk.CTkButton(btn_frame, text="Reinstall", width=80,
                                            fg_color="#2980b9", hover_color="#2471a3",
                                            command=self._on_reinstall)
        self._reinstall_btn.pack(side="left", padx=4)

        self._open_folder_btn = ctk.CTkButton(btn_frame, text="Open Folder", width=80,
                                              command=self._on_open_folder)
        self._open_folder_btn.pack(side="left", padx=4)

    # ---------------------------------------------------------- refresh

    def refresh(self) -> None:
        for w in self._mod_widgets:
            w.destroy()
        self._mod_widgets.clear()
        self._selected_mod = None
        self._show_details(None)

        search = self._search_var.get().strip().lower()
        mods = self.app.manifest.list_mods()
        if search:
            mods = [m for m in mods if search in m.display_name.lower() or search in m.mod_id.lower()]

        for i, mod in enumerate(mods):
            self._add_mod_row(mod, i)

    def _on_search(self, *_args) -> None:
        self.refresh()

    def _add_mod_row(self, mod: ModInstall, idx: int) -> None:
        row = ctk.CTkFrame(self._list_frame, cursor="hand2")
        row.grid(row=idx, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(1, weight=1)

        status_color = "#2d8a4e" if mod.enabled else "#7f8c8d"
        status = ctk.CTkLabel(row, text="●", text_color=status_color, width=20)
        status.grid(row=0, column=0, padx=(8, 4), pady=6)

        name = ctk.CTkLabel(row, text=mod.display_name, anchor="w",
                            font=ctk.CTkFont(weight="bold"))
        name.grid(row=0, column=1, sticky="w", padx=4, pady=6)

        info_text = f"{mod.file_count} files | {', '.join(mod.targets)}"
        if not mod.enabled:
            info_text += " | DISABLED"
        info = ctk.CTkLabel(row, text=info_text, anchor="e",
                            text_color="#95a5a6")
        info.grid(row=0, column=2, sticky="e", padx=8, pady=6)

        for widget in (row, status, name, info):
            widget.bind("<Button-1>", lambda e, m=mod: self._select_mod(m))

        self._mod_widgets.append(row)

    def _select_mod(self, mod: ModInstall) -> None:
        self._selected_mod = mod
        self._show_details(mod)

    def _show_details(self, mod: Optional[ModInstall]) -> None:
        if mod is None:
            self._detail_name.configure(text="Select a mod")
            self._detail_info.configure(state="normal")
            self._detail_info.delete("1.0", "end")
            self._detail_info.configure(state="disabled")
            return

        self._detail_name.configure(text=mod.display_name)
        self._toggle_btn.configure(text="Enable" if not mod.enabled else "Disable")

        self._detail_info.configure(state="normal")
        self._detail_info.delete("1.0", "end")

        lines = [
            f"ID:        {mod.mod_id}",
            f"Type:      {mod.install_type}",
            f"Targets:   {', '.join(mod.targets)}",
            f"Files:     {mod.file_count}",
            f"Enabled:   {mod.enabled}",
            f"Installed: {mod.install_time}",
            f"Archive:   {mod.source_archive}",
        ]
        if mod.selected_variant:
            lines.append(f"Variant:   {mod.selected_variant}")
        if mod.archive_hash:
            lines.append(f"Hash:      {mod.archive_hash[:16]}...")

        lines.append("")
        lines.append("--- Installed Files ---")
        for fp in mod.installed_files:
            exists = Path(fp).exists()
            marker = "" if exists else " [MISSING]"
            lines.append(f"  {fp}{marker}")

        self._detail_info.insert("1.0", "\n".join(lines))
        self._detail_info.configure(state="disabled")

    # ---------------------------------------------------------- actions

    def _on_toggle(self) -> None:
        if not self._selected_mod:
            return
        mod = self._selected_mod
        if mod.enabled:
            self.app.installer.disable(mod)
        else:
            self.app.installer.enable(mod)
        self.app.manifest.update_mod(mod)
        self.refresh()
        log.info("Toggled mod %s: enabled=%s", mod.mod_id, mod.enabled)

    def _on_uninstall(self) -> None:
        if not self._selected_mod:
            return
        mod = self._selected_mod
        confirm = messagebox.askyesno(
            "Confirm Uninstall",
            f"Uninstall '{mod.display_name}'?\n\n"
            f"This will remove {mod.file_count} managed files.",
        )
        if not confirm:
            return

        record = self.app.installer.uninstall(mod)
        self.app.manifest.add_record(record)
        self.app.manifest.remove_mod(mod.mod_id)
        self.refresh()
        log.info("Uninstalled mod: %s", mod.mod_id)

    def _on_reinstall(self) -> None:
        if not self._selected_mod:
            return
        mod = self._selected_mod
        archive_path = Path(mod.source_archive) if mod.source_archive else None
        if not archive_path or not archive_path.is_file():
            messagebox.showerror(
                "Archive Not Found",
                f"The original archive is no longer available:\n{mod.source_archive}\n\n"
                "You can re-install manually from the Mods tab.",
            )
            return

        confirm = messagebox.askyesno(
            "Confirm Reinstall",
            f"Reinstall '{mod.display_name}'?\n\n"
            f"This will uninstall the current version ({mod.file_count} files) "
            f"and install again from:\n{archive_path.name}",
        )
        if not confirm:
            return

        # Uninstall first
        record = self.app.installer.uninstall(mod)
        self.app.manifest.add_record(record)
        self.app.manifest.remove_mod(mod.mod_id)

        # Re-install using the same archive, target, and variant
        try:
            from ...core.archive_inspector import inspect_archive
            from ...core.deployment_planner import plan_deployment
            from ...models.mod_install import InstallTarget

            info = inspect_archive(archive_path)
            target = InstallTarget(mod.targets[0]) if mod.targets else InstallTarget.CLIENT
            plan = plan_deployment(info, self.app.paths, target,
                                   mod.selected_variant, mod.display_name)

            if not plan.valid:
                messagebox.showerror("Reinstall Failed", "\n".join(plan.warnings))
                self.refresh()
                return

            new_mod, new_record = self.app.installer.install(plan)
            self.app.manifest.add_mod(new_mod)
            self.app.manifest.add_record(new_record)
            log.info("Reinstalled mod: %s", new_mod.display_name)
        except Exception as exc:
            log.error("Reinstall failed: %s", exc)
            messagebox.showerror("Reinstall Failed", str(exc))

        self.refresh()
        self.app.refresh_backups_tab()

    def _on_uninstall_all(self) -> None:
        mods = self.app.manifest.list_mods()
        if not mods:
            messagebox.showinfo("Nothing to Uninstall", "No mods are currently installed.")
            return

        confirm = messagebox.askyesno(
            "Uninstall All Mods",
            f"This will uninstall all {len(mods)} installed mod(s) and "
            "return your game to a vanilla state.\n\nAre you sure?",
        )
        if not confirm:
            return

        count = 0
        for mod in list(mods):
            try:
                record = self.app.installer.uninstall(mod)
                self.app.manifest.add_record(record)
                self.app.manifest.remove_mod(mod.mod_id)
                count += 1
            except Exception as exc:
                log.error("Failed to uninstall %s: %s", mod.mod_id, exc)

        self.refresh()
        self.app.refresh_backups_tab()
        messagebox.showinfo("Done", f"Uninstalled {count} of {len(mods)} mod(s).")
        log.info("Uninstall all: removed %d mods", count)

    def _on_open_folder(self) -> None:
        if not self._selected_mod or not self._selected_mod.installed_files:
            return
        first_file = Path(self._selected_mod.installed_files[0])
        folder = first_file.parent
        if folder.is_dir():
            os.startfile(str(folder))
