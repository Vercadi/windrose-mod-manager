"""Mods tab — archive library with install status, variant picker, and quick install.

Layout:
  +------------------------------------------------+
  | [Browse] [Install All]  Target:[v]  Status msg |  toolbar
  +------------------+-----------------------------+
  | Archive Library  | Archive Details             |
  |                  |   name, type, file count    |
  | ModA       [ok]  |   Variant picker (if any)   |
  | ModB             |   [Install] [Remove]        |
  | ModC       [ok]  |   File preview              |
  +------------------+-----------------------------+

Single click = inspect, Double click = quick install, Right click = context menu.
Green checkmark on library entries whose archive is already installed.
"""
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
        self._selected_library_path: Optional[str] = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_library_panel()
        self._build_details_panel()
        self._load_library()
        self._register_dnd()

    # ================================================================ toolbar

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent", height=40)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 2))

        self._drop_frame = ctk.CTkFrame(bar, border_width=2, border_color="#555555",
                                        height=36, width=200)
        self._drop_frame.pack(side="left")
        self._drop_frame.pack_propagate(False)
        self._drop_label = ctk.CTkLabel(
            self._drop_frame, text="  Drop archives here",
            font=ctk.CTkFont(size=12), text_color="#777777", anchor="w",
        )
        self._drop_label.pack(fill="both", expand=True, padx=6)

        self._browse_btn = ctk.CTkButton(bar, text="Browse...", width=80,
                                         command=self._on_browse)
        self._browse_btn.pack(side="left", padx=4)

        self._install_all_btn = ctk.CTkButton(
            bar, text="Install All", width=90,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_install_all,
        )
        self._install_all_btn.pack(side="left", padx=4)

        ctk.CTkLabel(bar, text="Target:").pack(side="left", padx=(12, 4))
        self._target_var = ctk.StringVar(value="client")
        self._target_menu = ctk.CTkOptionMenu(
            bar, variable=self._target_var,
            values=["client", "server", "both"], width=100,
        )
        self._target_menu.pack(side="left", padx=4)

        self._status_label = ctk.CTkLabel(bar, text="", anchor="w",
                                          font=ctk.CTkFont(size=12))
        self._status_label.pack(side="left", padx=12, fill="x", expand=True)

    # ================================================================ library panel

    def _build_library_panel(self) -> None:
        panel = ctk.CTkFrame(self, width=250)
        panel.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(2, 8))
        panel.grid_propagate(False)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkLabel(header, text="Archive Library",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=4)
        ctk.CTkButton(header, text="Clear", width=46, height=22,
                      fg_color="#555555", hover_color="#666666",
                      font=ctk.CTkFont(size=11),
                      command=self._on_clear_library).pack(side="right", padx=2)

        self._library_list = ctk.CTkScrollableFrame(panel)
        self._library_list.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2, 4))
        self._library_list.grid_columnconfigure(0, weight=1)

    # ================================================================ details panel

    def _build_details_panel(self) -> None:
        """Right side — archive info, variant picker, install button, file preview."""
        panel = ctk.CTkFrame(self)
        panel.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(2, 8))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)

        self._detail_header = ctk.CTkLabel(
            panel, text="Select an archive from the library",
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
        )
        self._detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))

        self._detail_subheader = ctk.CTkLabel(
            panel, text="", font=ctk.CTkFont(size=12),
            text_color="#999999", anchor="w",
        )
        self._detail_subheader.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        # Variant + actions row
        action_frame = ctk.CTkFrame(panel, fg_color="transparent")
        action_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))

        self._variant_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        self._variant_frame.pack(side="left", fill="x", expand=True)

        self._variant_label = ctk.CTkLabel(self._variant_frame, text="Variant:",
                                           font=ctk.CTkFont(size=12))
        self._variant_label.pack(side="left", padx=(4, 4))
        self._variant_var = ctk.StringVar(value="(none)")
        self._variant_menu = ctk.CTkOptionMenu(
            self._variant_frame, variable=self._variant_var,
            values=["(none)"], width=220,
        )
        self._variant_menu.pack(side="left", padx=4)
        self._variant_frame.pack_forget()

        ctk.CTkLabel(action_frame, text="Name:", font=ctk.CTkFont(size=12)).pack(
            side="left", padx=(4, 4))
        self._mod_name_var = ctk.StringVar()
        self._mod_name_entry = ctk.CTkEntry(action_frame, textvariable=self._mod_name_var,
                                            width=160)
        self._mod_name_entry.pack(side="left", padx=4)

        self._uninstall_btn = ctk.CTkButton(
            action_frame, text="Uninstall", width=90,
            fg_color="#c0392b", hover_color="#962d22",
            command=self._on_uninstall,
        )
        self._uninstall_btn.pack(side="right", padx=(4, 4))
        self._uninstall_btn.pack_forget()

        self._install_remote_btn = ctk.CTkButton(
            action_frame, text="Install to Remote", width=130,
            fg_color="#2980b9", hover_color="#2471a3",
            command=self._on_install_remote,
        )
        self._install_remote_btn.pack(side="right", padx=(4, 4))

        self._install_btn = ctk.CTkButton(
            action_frame, text="Install", width=90,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_install,
        )
        self._install_btn.pack(side="right", padx=(4, 4))

        # File preview
        self._preview_header = ctk.CTkLabel(
            panel, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#888888",
        )
        self._preview_header.grid(row=3, column=0, sticky="nw", padx=12, pady=(4, 0))

        self._preview_box = ctk.CTkTextbox(
            panel, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self._preview_box.grid(row=3, column=0, sticky="nsew", padx=8, pady=(20, 8))

    # ================================================================ install status helpers

    def _get_installed_archives(self) -> set[str]:
        """Return set of archive paths that are currently installed."""
        return {m.source_archive for m in self.app.manifest.list_mods()
                if m.source_archive}

    def _is_installed(self, archive_path_str: str) -> bool:
        return archive_path_str in self._get_installed_archives()

    def _find_installed_mod(self, archive_path_str: str):
        """Find the ModInstall for a given archive path, or None."""
        for m in self.app.manifest.list_mods():
            if m.source_archive == archive_path_str:
                return m
        return None

    # ================================================================ archive library

    def _library_path(self) -> Path:
        from ..app_window import DEFAULT_DATA_DIR
        return DEFAULT_DATA_DIR / "archive_library.json"

    def _load_library(self) -> None:
        data = read_json(self._library_path())
        self._library = data.get("archives", [])
        self._refresh_library_ui()

    def _save_library(self) -> None:
        write_json(self._library_path(), {"archives": self._library})

    def _add_to_library(self, archive_path: Path) -> None:
        path_str = str(archive_path)
        for entry in self._library:
            if entry.get("path") == path_str:
                return
        self._library.append({
            "path": path_str,
            "name": archive_path.stem,
            "ext": archive_path.suffix.lower(),
        })
        self._save_library()
        self._refresh_library_ui()

    def _refresh_library_ui(self) -> None:
        for w in self._library_widgets:
            w.destroy()
        self._library_widgets.clear()

        installed = self._get_installed_archives()
        for i, entry in enumerate(self._library):
            self._add_library_row(entry, i, entry["path"] in installed)

    def _add_library_row(self, entry: dict, idx: int, installed: bool) -> None:
        path = Path(entry["path"])
        exists = path.is_file()
        is_selected = entry["path"] == self._selected_library_path

        bg = "#2a3a2a" if is_selected else "transparent"
        row = ctk.CTkFrame(self._library_list, cursor="hand2" if exists else "arrow",
                           fg_color=bg)
        row.grid(row=idx, column=0, sticky="ew", pady=1)
        row.grid_columnconfigure(1, weight=1)

        # Installed badge
        badge_text = "  \u2714" if installed else "   "
        badge_color = "#2d8a4e" if installed else "transparent"
        badge = ctk.CTkLabel(row, text=badge_text, width=24,
                             text_color="#2d8a4e" if installed else "#444444",
                             font=ctk.CTkFont(size=13))
        badge.grid(row=0, column=0, padx=(4, 0), pady=3)

        name_color = "#ffffff" if exists else "#666666"
        label = ctk.CTkLabel(
            row, text=entry.get("name", path.stem),
            anchor="w", font=ctk.CTkFont(size=12),
            text_color=name_color,
        )
        label.grid(row=0, column=1, sticky="w", padx=(2, 0), pady=3)

        ext_label = ctk.CTkLabel(
            row, text=entry.get("ext", ""),
            font=ctk.CTkFont(size=10), text_color="#666666",
        )
        ext_label.grid(row=0, column=2, padx=(2, 2), pady=3)

        remove_btn = ctk.CTkButton(
            row, text="\u00d7", width=22, height=22,
            fg_color="transparent", hover_color="#c0392b",
            font=ctk.CTkFont(size=13),
            command=lambda p=entry["path"]: self._remove_from_library(p),
        )
        remove_btn.grid(row=0, column=3, padx=(0, 4), pady=3)

        if exists:
            for widget in (row, badge, label, ext_label):
                widget.bind("<Button-1>", lambda e, p=path: self._load_archive(p))
                widget.bind("<Double-Button-1>", lambda e, p=path: self._quick_install(p))
                widget.bind("<Button-3>", lambda e, p=path: self._show_library_menu(e, p))

        self._library_widgets.append(row)

    def _remove_from_library(self, path_str: str) -> None:
        self._library = [e for e in self._library if e.get("path") != path_str]
        if self._selected_library_path == path_str:
            self._selected_library_path = None
            self._clear_details()
        self._save_library()
        self._refresh_library_ui()

    def _on_clear_library(self) -> None:
        if not self._library:
            return
        confirm = messagebox.askyesno(
            "Clear Library",
            f"Remove all {len(self._library)} archive(s) from the library?\n\n"
            "This only removes the references, not the archive files themselves.",
        )
        if confirm:
            self._library.clear()
            self._selected_library_path = None
            self._clear_details()
            self._save_library()
            self._refresh_library_ui()

    # ================================================================ context menu + quick install

    def _show_library_menu(self, event, archive_path: Path) -> None:
        menu = tk.Menu(self, tearoff=0)
        installed = self._is_installed(str(archive_path))
        if installed:
            menu.add_command(label="\u2714  Installed", state="disabled")
            menu.add_separator()
            menu.add_command(label="Uninstall",
                             command=lambda: self._on_uninstall_archive(str(archive_path)))
        menu.add_command(label="Install", command=lambda: self._quick_install(archive_path))
        menu.add_command(label="Install to Remote Server",
                         command=lambda: self._on_install_remote_archive(str(archive_path)))
        menu.add_command(label="Inspect", command=lambda: self._load_archive(archive_path))
        menu.add_separator()
        menu.add_command(label="Remove from Library",
                         command=lambda: self._remove_from_library(str(archive_path)))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _quick_install(self, archive_path: Path) -> None:
        """Inspect and install in one step. Falls back to details if variants detected."""
        if not archive_path.is_file():
            messagebox.showerror("Not Found", f"Archive not found:\n{archive_path}")
            return

        self._status_label.configure(text=f"Installing {archive_path.name}...",
                                     text_color="#aaaaaa")
        self.update_idletasks()

        try:
            info = inspect_archive(archive_path)
        except Exception as exc:
            messagebox.showerror("Inspect Failed", str(exc))
            return

        if info.has_variants:
            self._load_archive(archive_path)
            messagebox.showinfo(
                "Variant Selection Required",
                f"'{archive_path.name}' has {sum(len(vg.variants) for vg in info.variant_groups)} "
                f"variants.\nPlease select one and click Install.",
            )
            return

        self._do_install(info, archive_path.stem)

    def _on_install_all(self) -> None:
        """Batch-install all library archives that aren't already installed.
        Skips multi-variant archives (user must pick manually)."""
        installed = self._get_installed_archives()
        to_install = [
            e for e in self._library
            if e["path"] not in installed and Path(e["path"]).is_file()
        ]
        if not to_install:
            messagebox.showinfo("Nothing to Install",
                                "All archives in the library are already installed "
                                "(or have missing files).")
            return

        confirm = messagebox.askyesno(
            "Install All",
            f"Install {len(to_install)} archive(s) using target '{self._target_var.get()}'?",
        )
        if not confirm:
            return

        success = 0
        failed = 0
        skipped_variants = 0
        for entry in to_install:
            path = Path(entry["path"])
            try:
                info = inspect_archive(path)
                if info.has_variants:
                    skipped_variants += 1
                    continue
                if self._do_install(info, path.stem, quiet=True):
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                log.error("Install All: failed for %s: %s", path.name, exc)
                failed += 1

        msg = f"Installed {success} mod(s)."
        if failed:
            msg += f"\n{failed} failed."
        if skipped_variants:
            msg += f"\nSkipped {skipped_variants} archive(s) with variants — install those manually."
        self._status_label.configure(text=msg, text_color="#2d8a4e")
        self._refresh_library_ui()

    # ================================================================ drag and drop

    def _register_dnd(self) -> None:
        if not getattr(self.app, "_dnd_enabled", False):
            return
        try:
            self._drop_frame.drop_target_register("DND_Files")
            self._drop_frame.dnd_bind("<<Drop>>", self._on_drop)
            self._drop_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self._drop_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)

            for child in (self._drop_label, self._browse_btn):
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
        self._drop_label.configure(text_color="#777777")

    def _on_drop(self, event) -> None:
        self._drop_frame.configure(border_color="#555555")
        self._drop_label.configure(text_color="#777777")

        paths = self._parse_drop_data(event.data)
        valid = [p for p in paths if p.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not valid:
            self._status_label.configure(text="No supported archives in drop",
                                         text_color="#c0392b")
            return

        for p in valid:
            self._add_to_library(p)

        if len(valid) == 1:
            self._load_archive(valid[0])
        else:
            self._status_label.configure(
                text=f"Added {len(valid)} archives — click to inspect, double-click to install",
                text_color="#2d8a4e",
            )

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
            if not paths:
                paths.append(Path(data))
        return paths

    # ================================================================ browse / inspect / install

    def _on_browse(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select Mod Archive(s)", filetypes=_FILETYPES,
        )
        if not paths:
            return
        valid = [Path(p) for p in paths if Path(p).suffix.lower() in SUPPORTED_EXTENSIONS]
        for p in valid:
            self._add_to_library(p)
        if len(valid) == 1:
            self._load_archive(valid[0])
        elif valid:
            self._status_label.configure(
                text=f"Added {len(valid)} archives — click to inspect",
                text_color="#2d8a4e",
            )

    def _load_archive(self, archive_path: Path) -> None:
        """Inspect and show details for an archive."""
        self._add_to_library(archive_path)
        self._selected_library_path = str(archive_path)
        self._refresh_library_ui()

        self._status_label.configure(text="Inspecting...", text_color="#aaaaaa")
        self.update_idletasks()

        info = inspect_archive(archive_path)
        self._current_info = info

        self._detail_header.configure(text=archive_path.name)
        self._mod_name_var.set(archive_path.stem)

        installed = self._is_installed(str(archive_path))
        type_text = info.archive_type.value.replace("_", " ")
        sub = f"{type_text}  \u2022  {info.total_files} files"
        if installed:
            sub += "  \u2022  \u2714 Installed"
        self._detail_subheader.configure(text=sub)

        # Variant picker
        if info.has_variants:
            variant_names = []
            for vg in info.variant_groups:
                variant_names.extend(vg.variant_names)
            self._variant_menu.configure(values=variant_names)
            if variant_names:
                self._variant_var.set(variant_names[0])
            self._variant_frame.pack(side="left", padx=(0, 8))
        else:
            self._variant_menu.configure(values=["(none)"])
            self._variant_var.set("(none)")
            self._variant_frame.pack_forget()

        # Show/hide uninstall button
        if installed:
            self._uninstall_btn.pack(side="right", padx=(4, 4))
        else:
            self._uninstall_btn.pack_forget()

        # File preview
        self._show_preview(info)

        if info.warnings:
            self._status_label.configure(
                text=f"{len(info.warnings)} warning(s) — see file preview",
                text_color="#e67e22",
            )
        else:
            self._status_label.configure(
                text=f"Ready to install" if not installed else "Already installed",
                text_color="#2d8a4e" if not installed else "#95a5a6",
            )

        log.info("Inspected: %s (%s)", archive_path.name, info.archive_type.value)

    def _clear_details(self) -> None:
        self._current_info = None
        self._detail_header.configure(text="Select an archive from the library")
        self._detail_subheader.configure(text="")
        self._variant_frame.pack_forget()
        self._uninstall_btn.pack_forget()
        self._mod_name_var.set("")
        self._preview_header.configure(text="")
        self._preview_box.configure(state="normal")
        self._preview_box.delete("1.0", "end")
        self._preview_box.configure(state="disabled")

    def _show_preview(self, info: ArchiveInfo) -> None:
        self._preview_box.configure(state="normal")
        self._preview_box.delete("1.0", "end")

        if info.pak_entries:
            self._preview_box.insert("end", "=== PAK FILES ===\n")
            for e in info.pak_entries:
                self._preview_box.insert("end", f"  [PAK] {PurePosixPath(e.path).name}\n")

        if info.companion_entries:
            self._preview_box.insert("end", "\n=== COMPANION FILES ===\n")
            for e in info.companion_entries:
                suffix = PurePosixPath(e.path).suffix.upper().lstrip(".")
                self._preview_box.insert("end", f"  [{suffix}] {PurePosixPath(e.path).name}\n")

        if info.loose_entries:
            self._preview_box.insert("end", "\n=== LOOSE FILES ===\n")
            for e in info.loose_entries:
                self._preview_box.insert("end", f"  {e.path}\n")

        if info.variant_groups:
            self._preview_box.insert("end", "\n=== VARIANT GROUPS ===\n")
            for vg in info.variant_groups:
                self._preview_box.insert("end", f"  Group: {vg.base_name}\n")
                for v in vg.variants:
                    self._preview_box.insert("end",
                                             f"    - {PurePosixPath(v.path).name}\n")

        if info.warnings:
            self._preview_box.insert("end", "\n=== WARNINGS ===\n")
            for w in info.warnings:
                self._preview_box.insert("end", f"  ! {w}\n")

        self._preview_box.configure(state="disabled")

    def _on_install(self) -> None:
        if self._current_info is None:
            messagebox.showwarning("No Archive", "Select an archive from the library first.")
            return

        info = self._current_info
        selected_variant = self._variant_var.get()
        if selected_variant == "(none)":
            selected_variant = None

        if info.has_variants and selected_variant is None:
            messagebox.showwarning(
                "Variant Required",
                "This archive has multiple variants. Please select one.",
            )
            return

        mod_name = self._mod_name_var.get().strip() or Path(info.archive_path).stem
        self._do_install(info, mod_name, selected_variant=selected_variant)

    def _on_uninstall(self) -> None:
        """Uninstall the mod associated with the currently inspected archive."""
        if self._current_info is None:
            return
        self._on_uninstall_archive(self._current_info.archive_path)

    def _on_uninstall_archive(self, archive_path_str: str) -> None:
        """Uninstall the mod installed from a given archive path."""
        mod = self._find_installed_mod(archive_path_str)
        if not mod:
            messagebox.showinfo("Not Installed",
                                "No installed mod found for this archive.")
            return

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
        self._status_label.configure(
            text=f"Uninstalled '{mod.display_name}'",
            text_color="#e67e22",
        )
        log.info("Uninstalled from Mods tab: %s", mod.display_name)
        self.app.refresh_installed_tab()
        self.app.refresh_backups_tab()
        self._refresh_library_ui()

        # Update the details panel to reflect uninstalled state
        if self._selected_library_path == archive_path_str:
            self._load_archive(Path(archive_path_str))

    def _on_install_remote(self) -> None:
        """Upload the currently selected archive to the remote server."""
        if self._current_info is None:
            messagebox.showwarning("No Archive", "Select an archive from the library first.")
            return
        self._on_install_remote_archive(self._current_info.archive_path)

    def _on_install_remote_archive(self, archive_path_str: str) -> None:
        """Upload a given archive file to the remote server via SFTP."""
        remote_tab = self.app.remote_tab
        if not remote_tab.is_connected():
            messagebox.showinfo(
                "Not Connected",
                "No remote server connection is active.\n\n"
                "Please connect to a remote server via the "
                "\"Remote Server\" tab first.",
            )
            return

        archive_path = Path(archive_path_str)
        if not archive_path.is_file():
            messagebox.showerror("Not Found", f"Archive not found:\n{archive_path}")
            return

        self._status_label.configure(
            text=f"Uploading {archive_path.name} to remote...",
            text_color="#aaaaaa",
        )
        self.update_idletasks()

        def _on_upload_done(success: bool, message: str) -> None:
            if success:
                self._status_label.configure(
                    text=f"Remote: {message}", text_color="#2d8a4e",
                )
                messagebox.showinfo("Upload Complete",
                                    f"'{archive_path.name}' uploaded to remote server.")
            else:
                self._status_label.configure(
                    text=f"Remote upload failed", text_color="#c0392b",
                )
                messagebox.showerror("Upload Failed", message)

        remote_tab.upload_file(str(archive_path), callback=_on_upload_done)

    def _do_install(self, info: ArchiveInfo, mod_name: str,
                    selected_variant: Optional[str] = None,
                    quiet: bool = False) -> bool:
        """Core install logic shared by single install, quick install, and install all."""
        paths = self.app.paths
        try:
            target = InstallTarget(self._target_var.get())
        except ValueError:
            target = InstallTarget.CLIENT

        if target in (InstallTarget.CLIENT, InstallTarget.BOTH) and not paths.client_root:
            if not quiet:
                messagebox.showerror("Error", "Client path not configured. Check Settings.")
            return False
        if target in (InstallTarget.SERVER, InstallTarget.BOTH) and not paths.server_root:
            if not quiet:
                messagebox.showerror("Error", "Server path not configured. Check Settings.")
            return False

        plan = plan_deployment(info, paths, target, selected_variant, mod_name)
        if not plan.valid:
            if not quiet:
                messagebox.showerror("Plan Error", "\n".join(plan.warnings))
            return False

        conflict_report = check_plan_conflicts(plan, self.app.manifest)
        if conflict_report.has_conflicts and not quiet:
            conflict_text = "\n".join(c.description for c in conflict_report.conflicts)
            if not messagebox.askyesno(
                "File Conflicts",
                f"Conflicts found:\n\n{conflict_text}\n\nExisting files will be backed up. Continue?",
            ):
                return False

        self._status_label.configure(text=f"Installing {mod_name}...", text_color="#aaaaaa")
        self.update_idletasks()

        try:
            mod, record = self.app.installer.install(plan)
            self.app.manifest.add_mod(mod)
            self.app.manifest.add_record(record)
            if not quiet:
                self._status_label.configure(
                    text=f"Installed '{mod.display_name}' \u2014 {mod.file_count} files",
                    text_color="#2d8a4e",
                )
            log.info("Installed: %s (%d files)", mod.display_name, mod.file_count)
            self.app.refresh_installed_tab()
            self.app.refresh_backups_tab()
            self._refresh_library_ui()
            return True
        except Exception as exc:
            log.error("Install failed: %s", exc)
            if not quiet:
                messagebox.showerror("Install Failed", str(exc))
                self._status_label.configure(text="Install failed", text_color="#c0392b")
            return False
