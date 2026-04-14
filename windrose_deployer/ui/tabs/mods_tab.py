"""Mods tab — add, inspect, and install mod archives with drag-and-drop."""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.archive_handler import SUPPORTED_EXTENSIONS
from ...core.archive_inspector import inspect_archive
from ...core.conflict_detector import check_plan_conflicts
from ...core.deployment_planner import plan_deployment
from ...models.archive_info import ArchiveInfo, ArchiveType
from ...models.mod_install import InstallTarget
from ...ui.widgets.file_preview import FilePreview

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
    def __init__(self, master, app: AppWindow, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._current_info: Optional[ArchiveInfo] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_drop_zone()
        self._build_options_section()
        self._build_preview_section()
        self._register_dnd()

    # ---------------------------------------------------------- layout

    def _build_drop_zone(self) -> None:
        self._drop_frame = ctk.CTkFrame(self, height=100, border_width=2,
                                        border_color="#555555")
        self._drop_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self._drop_frame.grid_columnconfigure(0, weight=1)
        self._drop_frame.grid_propagate(False)

        self._drop_inner = ctk.CTkFrame(self._drop_frame, fg_color="transparent")
        self._drop_inner.place(relx=0.5, rely=0.5, anchor="center")

        self._drop_label = ctk.CTkLabel(
            self._drop_inner,
            text="Drop mod archive here  (.zip  .7z  .rar)\nor click Browse to select",
            font=ctk.CTkFont(size=14),
            text_color="#aaaaaa",
            justify="center",
        )
        self._drop_label.pack(pady=(0, 6))

        btn_row = ctk.CTkFrame(self._drop_inner, fg_color="transparent")
        btn_row.pack()

        self._browse_btn = ctk.CTkButton(btn_row, text="Browse...", width=100,
                                         command=self._on_browse)
        self._browse_btn.pack(side="left", padx=4)

        self._status_label = ctk.CTkLabel(btn_row, text="", anchor="w", width=400)
        self._status_label.pack(side="left", padx=8)

    def _build_options_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        frame.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(frame, text="Target:").grid(row=0, column=0, padx=(8, 4), pady=8)
        self._target_var = ctk.StringVar(value="client")
        self._target_menu = ctk.CTkOptionMenu(
            frame, variable=self._target_var,
            values=["client", "server", "both"], width=110,
        )
        self._target_menu.grid(row=0, column=1, padx=4, pady=8)

        self._variant_label = ctk.CTkLabel(frame, text="Variant:")
        self._variant_label.grid(row=0, column=2, padx=(12, 4), pady=8)
        self._variant_var = ctk.StringVar(value="(none)")
        self._variant_menu = ctk.CTkOptionMenu(
            frame, variable=self._variant_var, values=["(none)"], width=180,
        )
        self._variant_menu.grid(row=0, column=3, padx=4, pady=8)

        ctk.CTkLabel(frame, text="Name:").grid(row=0, column=4, padx=(12, 4), pady=8)
        self._mod_name_var = ctk.StringVar()
        self._mod_name_entry = ctk.CTkEntry(frame, textvariable=self._mod_name_var, width=180)
        self._mod_name_entry.grid(row=0, column=5, padx=4, pady=8, sticky="ew")

        self._install_btn = ctk.CTkButton(
            frame, text="Install", width=100,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_install,
        )
        self._install_btn.grid(row=0, column=6, padx=(8, 8), pady=8)

    def _build_preview_section(self) -> None:
        self._preview = FilePreview(self)
        self._preview.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))

    # ---------------------------------------------------------- drag and drop

    def _register_dnd(self) -> None:
        """Register drag-and-drop handlers via tkinterdnd2 if available."""
        if not getattr(self.app, "_dnd_enabled", False):
            return
        try:
            self._drop_frame.drop_target_register("DND_Files")
            self._drop_frame.dnd_bind("<<Drop>>", self._on_drop)
            self._drop_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self._drop_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)

            for child in (self._drop_label, self._drop_inner,
                          self._browse_btn, self._status_label):
                try:
                    child.drop_target_register("DND_Files")
                    child.dnd_bind("<<Drop>>", self._on_drop)
                except Exception:
                    pass

            log.info("Drag-and-drop registered on Mods tab")
        except Exception as exc:
            log.warning("Could not register drag-and-drop: %s", exc)

    def _on_drag_enter(self, event) -> None:
        self._drop_frame.configure(border_color="#2d8a4e")
        self._drop_label.configure(text_color="#2d8a4e")

    def _on_drag_leave(self, event) -> None:
        self._drop_frame.configure(border_color="#555555")
        self._drop_label.configure(text_color="#aaaaaa")

    def _on_drop(self, event) -> None:
        self._drop_frame.configure(border_color="#555555")
        self._drop_label.configure(text_color="#aaaaaa")

        raw = event.data
        paths = self._parse_drop_data(raw)
        if not paths:
            return

        archive_path = paths[0]
        if archive_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            self._status_label.configure(
                text=f"Unsupported: {archive_path.suffix}",
                text_color="#c0392b",
            )
            return

        self._load_archive(archive_path)

    def _parse_drop_data(self, data: str) -> list[Path]:
        """Parse tkinterdnd2 drop data which may be brace-wrapped or space-separated."""
        paths: list[Path] = []
        data = data.strip()
        if not data:
            return paths

        if "{" in data:
            import re
            for match in re.finditer(r"\{([^}]+)\}", data):
                paths.append(Path(match.group(1)))
            remaining = re.sub(r"\{[^}]+\}", "", data).strip()
            if remaining:
                for part in remaining.split():
                    if part:
                        paths.append(Path(part))
        else:
            for part in data.split("\n"):
                part = part.strip()
                if part:
                    paths.append(Path(part))
            if not paths:
                paths.append(Path(data))

        return paths

    # ---------------------------------------------------------- handlers

    def _on_browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Mod Archive",
            filetypes=_FILETYPES,
        )
        if path:
            self._load_archive(Path(path))

    def _load_archive(self, archive_path: Path) -> None:
        """Inspect an archive and populate all UI fields."""
        self._status_label.configure(text="Inspecting...", text_color="#aaaaaa")
        self.update_idletasks()

        info = inspect_archive(archive_path)
        self._current_info = info
        self._preview.show(info)

        name = archive_path.stem
        self._mod_name_var.set(name)

        self._drop_label.configure(
            text=f"{archive_path.name}",
            text_color="#ffffff",
        )

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
            self._status_label.configure(
                text=f"{info.archive_type.value} — {info.total_files} files, {len(info.warnings)} warning(s)",
                text_color="#e67e22",
            )
        else:
            self._status_label.configure(
                text=f"{info.archive_type.value} — {info.total_files} files",
                text_color="#2d8a4e",
            )

        log.info("Loaded archive: %s (%s)", archive_path.name, info.archive_type.value)

    def _on_install(self) -> None:
        if self._current_info is None:
            messagebox.showwarning("No Archive", "Please select a mod archive first.")
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

        mod_name = self._mod_name_var.get().strip() or Path(info.archive_path).stem

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

        self._status_label.configure(text="Installing...", text_color="#aaaaaa")
        self.update_idletasks()

        try:
            mod, record = self.app.installer.install(plan)
            self.app.manifest.add_mod(mod)
            self.app.manifest.add_record(record)
            self._status_label.configure(
                text=f"Installed '{mod.display_name}' — {mod.file_count} files",
                text_color="#2d8a4e",
            )
            log.info("Mod installed: %s", mod.display_name)
            self.app.refresh_installed_tab()
        except Exception as exc:
            log.error("Install failed: %s", exc)
            messagebox.showerror("Install Failed", str(exc))
            self._status_label.configure(text="Install failed", text_color="#c0392b")
