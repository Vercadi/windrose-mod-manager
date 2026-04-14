"""Mods tab — add, inspect, and install mod archives."""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.archive_inspector import inspect_archive
from ...core.conflict_detector import check_plan_conflicts
from ...core.deployment_planner import plan_deployment
from ...models.archive_info import ArchiveInfo, ArchiveType
from ...models.mod_install import InstallTarget
from ...ui.widgets.file_preview import FilePreview

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class ModsTab(ctk.CTkFrame):
    def __init__(self, master, app: AppWindow, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._current_info: Optional[ArchiveInfo] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_archive_section()
        self._build_options_section()
        self._build_actions_section()
        self._build_preview_section()

    # ---------------------------------------------------------- layout

    def _build_archive_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Mod Archive:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=8, pady=8, sticky="w")

        self._archive_path_var = ctk.StringVar()
        self._archive_entry = ctk.CTkEntry(frame, textvariable=self._archive_path_var, state="readonly")
        self._archive_entry.grid(row=0, column=1, padx=4, pady=8, sticky="ew")

        self._browse_btn = ctk.CTkButton(frame, text="Browse...", width=100, command=self._on_browse)
        self._browse_btn.grid(row=0, column=2, padx=(4, 8), pady=8)

        self._inspect_btn = ctk.CTkButton(frame, text="Inspect", width=80, command=self._on_inspect)
        self._inspect_btn.grid(row=0, column=3, padx=(0, 8), pady=8)

    def _build_options_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky="ew", padx=8, pady=4)

        ctk.CTkLabel(frame, text="Install Target:").pack(side="left", padx=(8, 4), pady=8)
        self._target_var = ctk.StringVar(value="client")
        self._target_menu = ctk.CTkOptionMenu(
            frame, variable=self._target_var,
            values=["client", "server", "both"], width=120,
        )
        self._target_menu.pack(side="left", padx=4, pady=8)

        self._variant_label = ctk.CTkLabel(frame, text="Variant:")
        self._variant_label.pack(side="left", padx=(16, 4), pady=8)
        self._variant_var = ctk.StringVar(value="(none)")
        self._variant_menu = ctk.CTkOptionMenu(
            frame, variable=self._variant_var, values=["(none)"], width=200,
        )
        self._variant_menu.pack(side="left", padx=4, pady=8)

        self._mod_name_label = ctk.CTkLabel(frame, text="Name:")
        self._mod_name_label.pack(side="left", padx=(16, 4), pady=8)
        self._mod_name_var = ctk.StringVar()
        self._mod_name_entry = ctk.CTkEntry(frame, textvariable=self._mod_name_var, width=200)
        self._mod_name_entry.pack(side="left", padx=4, pady=8)

    def _build_actions_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=8, pady=4)

        self._install_btn = ctk.CTkButton(
            frame, text="Install Mod", width=140,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_install,
        )
        self._install_btn.pack(side="left", padx=8)

        self._status_label = ctk.CTkLabel(frame, text="", anchor="w")
        self._status_label.pack(side="left", padx=8, fill="x", expand=True)

    def _build_preview_section(self) -> None:
        self._preview = FilePreview(self)
        self._preview.grid(row=3, column=0, sticky="nsew", padx=8, pady=(4, 8))

    # ---------------------------------------------------------- handlers

    def _on_browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Mod Archive",
            filetypes=[("Zip archives", "*.zip"), ("All files", "*.*")],
        )
        if path:
            self._archive_path_var.set(path)
            self._on_inspect()

    def _on_inspect(self) -> None:
        path_str = self._archive_path_var.get().strip()
        if not path_str:
            messagebox.showwarning("No Archive", "Please select a mod archive first.")
            return

        archive_path = Path(path_str)
        self._status_label.configure(text="Inspecting...")
        self.update_idletasks()

        info = inspect_archive(archive_path)
        self._current_info = info
        self._preview.show(info)

        name = PurePosixPath(archive_path.stem).name
        self._mod_name_var.set(name)

        if info.has_variants:
            variant_names = []
            for vg in info.variant_groups:
                variant_names.extend(vg.variant_names)
            self._variant_menu.configure(values=variant_names)
            if variant_names:
                self._variant_var.set(variant_names[0])
        else:
            self._variant_menu.configure(values=["(none)"])
            self._variant_var.set("(none)")

        if info.warnings:
            self._status_label.configure(text=f"Inspected — {len(info.warnings)} warning(s)")
        else:
            self._status_label.configure(text=f"Inspected — {info.archive_type.value}, {info.total_files} files")

    def _on_install(self) -> None:
        if self._current_info is None:
            messagebox.showwarning("No Archive", "Please inspect an archive first.")
            return

        info = self._current_info
        paths = self.app.paths

        try:
            target = InstallTarget(self._target_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid install target.")
            return

        if target in (InstallTarget.CLIENT, InstallTarget.BOTH) and not paths.client_root:
            messagebox.showerror("Error", "Client path not configured. Check Settings tab.")
            return
        if target in (InstallTarget.SERVER, InstallTarget.BOTH) and not paths.server_root:
            messagebox.showerror("Error", "Server path not configured. Check Settings tab.")
            return

        selected_variant = self._variant_var.get()
        if selected_variant == "(none)":
            selected_variant = None

        if info.has_variants and selected_variant is None:
            messagebox.showwarning(
                "Variant Required",
                "This archive contains multiple variants. Please select one before installing.",
            )
            return

        mod_name = self._mod_name_var.get().strip() or PurePosixPath(info.archive_path).stem

        plan = plan_deployment(info, paths, target, selected_variant, mod_name)

        if not plan.valid:
            messagebox.showerror("Plan Error", "\n".join(plan.warnings))
            return

        conflict_report = check_plan_conflicts(plan, self.app.manifest)
        if conflict_report.has_conflicts:
            conflict_text = "\n".join(c.description for c in conflict_report.conflicts)
            proceed = messagebox.askyesno(
                "File Conflicts Detected",
                f"The following conflicts were found:\n\n{conflict_text}\n\n"
                "Existing files will be backed up. Continue?",
            )
            if not proceed:
                return

        if conflict_report.has_warnings:
            for w in conflict_report.warnings:
                log.warning("Deployment warning: %s", w)

        self._status_label.configure(text="Installing...")
        self.update_idletasks()

        try:
            mod, record = self.app.installer.install(plan)
            self.app.manifest.add_mod(mod)
            self.app.manifest.add_record(record)
            self._status_label.configure(text=f"Installed '{mod.display_name}' — {mod.file_count} files")
            log.info("Mod installed: %s", mod.display_name)
            self.app.refresh_installed_tab()
        except Exception as exc:
            log.error("Install failed: %s", exc)
            messagebox.showerror("Install Failed", str(exc))
            self._status_label.configure(text="Install failed")
