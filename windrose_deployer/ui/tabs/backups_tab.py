"""Recovery screen with action timeline and advanced raw backup browser."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.backup_manager import BackupRecord, DEFAULT_MAX_BACKUPS_PER_SOURCE

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class BackupsTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._selected_item = None
        self._selected_backup: Optional[BackupRecord] = None
        self._timeline_rows: list[ctk.CTkFrame] = []
        self._backup_rows: list[ctk.CTkFrame] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._filter_var = ctk.StringVar(value="all")
        self._advanced_visible = False

        self._build_header()
        self._build_main()
        self.refresh()

    def _build_header(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(frame, text="Recovery", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        self._filter_menu = ctk.CTkOptionMenu(
            frame,
            variable=self._filter_var,
            values=["all", "mods", "server", "hosted"],
            width=130,
            command=lambda _value: self.refresh(),
        )
        self._filter_menu.grid(row=0, column=1, sticky="w")
        self._summary_label = ctk.CTkLabel(frame, text="", anchor="w", text_color="#95a5a6")
        self._summary_label.grid(row=0, column=2, sticky="ew", padx=(12, 12))
        ctk.CTkButton(
            frame,
            text="Clean Up Old",
            width=120,
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_cleanup_old,
        ).grid(row=0, column=3, sticky="e", padx=(0, 8))
        self._advanced_btn = ctk.CTkButton(
            frame,
            text="Show Raw Backup Copies",
            width=180,
            fg_color="#555555",
            hover_color="#666666",
            command=self._toggle_advanced,
        )
        self._advanced_btn.grid(row=0, column=4, sticky="e")

    def _build_main(self) -> None:
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
        self._panes.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        left_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        right_host = ctk.CTkFrame(self._panes, fg_color="transparent")
        self._panes.add(left_host, minsize=320, width=380)
        self._panes.add(right_host, minsize=520)

        self._timeline = ctk.CTkScrollableFrame(left_host)
        self._timeline.pack(fill="both", expand=True)
        self._timeline.grid_columnconfigure(0, weight=1)

        right = ctk.CTkScrollableFrame(right_host)
        right.pack(fill="both", expand=True)
        right.grid_columnconfigure(0, weight=1)

        self._detail_title = ctk.CTkLabel(right, text="Select a recovery item", font=ctk.CTkFont(size=18, weight="bold"))
        self._detail_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self._detail_meta = ctk.CTkLabel(right, text="", justify="left", text_color="#95a5a6")
        self._detail_meta.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        actions = ctk.CTkFrame(right)
        actions.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        ctk.CTkButton(actions, text="Restore Previous Version", width=180, fg_color="#2d8a4e", hover_color="#236b3d", command=self._on_restore).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Undo Last Change", width=140, fg_color="#2980b9", hover_color="#2471a3", command=self._on_undo).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Open Affected Files", width=150, command=self._on_open_files).pack(side="left", padx=6)

        self._detail_box = ctk.CTkTextbox(right, height=240, font=ctk.CTkFont(family="Consolas", size=11))
        self._detail_box.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._detail_box.configure(state="disabled")

        self._advanced_frame = ctk.CTkFrame(right)
        self._advanced_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._advanced_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._advanced_frame, text="Raw Backup Copies", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        self._backup_list = ctk.CTkScrollableFrame(self._advanced_frame, height=180)
        self._backup_list.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._backup_list.grid_columnconfigure(0, weight=1)
        raw_actions = ctk.CTkFrame(self._advanced_frame, fg_color="transparent")
        raw_actions.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(raw_actions, text="Restore Previous Version", width=170, command=self._on_restore_raw).pack(side="left", padx=(0, 6))
        ctk.CTkButton(raw_actions, text="Remove Backup Copy", width=150, fg_color="#c0392b", hover_color="#962d22", command=self._on_delete_raw).pack(side="left", padx=6)
        ctk.CTkButton(raw_actions, text="Open Backup Folder", width=140, command=self._on_open_folder).pack(side="left", padx=6)
        self._advanced_frame.grid_remove()

    def refresh(self) -> None:
        for widget in self._timeline_rows:
            widget.destroy()
        for widget in self._backup_rows:
            widget.destroy()
        self._timeline_rows.clear()
        self._backup_rows.clear()
        self._selected_item = None
        self._selected_backup = None
        self._detail_title.configure(text="Select a recovery item")
        self._detail_meta.configure(text="")
        self._set_box(self._detail_box, "")

        items = self.app.recovery.build_timeline()
        items = [item for item in items if self._matches_filter(item)]
        for index, item in enumerate(items):
            self._add_timeline_row(item, index)

        backups = sorted(self.app.backup.list_backups(), key=lambda item: item.timestamp, reverse=True)
        for index, record in enumerate(backups):
            self._add_backup_row(record, index)

        self._summary_label.configure(text=f"{len(items)} recovery items | {len(backups)} raw backups")

    def _matches_filter(self, item) -> bool:
        selected = self._filter_var.get()
        if selected == "all":
            return True
        if selected == "mods":
            return item.action in {"install", "uninstall", "disable", "enable", "repair"}
        if selected == "server":
            return item.target in {"server", "client,server"} or item.action in {"save_server_config", "save_world_config"}
        if selected == "hosted":
            return item.target == "hosted" or item.action.startswith("save_remote_") or item.action.startswith("hosted_")
        return True

    def _add_timeline_row(self, item, index: int) -> None:
        row = ctk.CTkFrame(self._timeline, cursor="hand2")
        row.grid(row=index, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row, text=item.title, anchor="w", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 2)
        )
        ctk.CTkLabel(row, text=item.subtitle, anchor="w", text_color="#95a5a6").grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 2)
        )
        ctk.CTkLabel(row, text=item.summary, anchor="w", text_color="#c1c7cd", wraplength=300).grid(
            row=2, column=0, sticky="ew", padx=10, pady=(0, 2)
        )
        ctk.CTkLabel(row, text=item.timestamp[:19].replace("T", " "), anchor="w", text_color="#6f7a81").grid(
            row=3, column=0, sticky="ew", padx=10, pady=(0, 8)
        )
        for widget in row.winfo_children() + [row]:
            widget.bind("<Button-1>", lambda _event, value=item: self._select_item(value))
        self._timeline_rows.append(row)

    def _add_backup_row(self, record: BackupRecord, index: int) -> None:
        row = ctk.CTkFrame(self._backup_list, cursor="hand2")
        row.grid(row=index, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row, text=record.category.replace("_", " ").title(), anchor="w", font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 2)
        )
        ctk.CTkLabel(row, text=record.description or Path(record.backup_path).name, anchor="w", text_color="#c1c7cd", wraplength=320).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 2)
        )
        ctk.CTkLabel(row, text=record.timestamp[:19].replace("T", " "), anchor="w", text_color="#6f7a81").grid(
            row=2, column=0, sticky="ew", padx=10, pady=(0, 8)
        )
        for widget in row.winfo_children() + [row]:
            widget.bind("<Button-1>", lambda _event, value=record: self._select_backup(value))
        self._backup_rows.append(row)

    def _select_item(self, item) -> None:
        self._selected_item = item
        self._detail_title.configure(text=item.title)
        self._detail_meta.configure(text=f"{item.subtitle}\n{item.timestamp[:19].replace('T', ' ')}")
        self._set_box(self._detail_box, "\n".join(item.details))

    def _select_backup(self, record: BackupRecord) -> None:
        self._selected_backup = record

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self._advanced_frame.grid()
            self._advanced_btn.configure(text="Hide Raw Backup Copies")
        else:
            self._advanced_frame.grid_remove()
            self._advanced_btn.configure(text="Show Raw Backup Copies")

    def _on_restore(self) -> None:
        item = self._selected_item
        if item is None:
            messagebox.showinfo("No Selection", "Select a recovery item first.")
            return
        if item.backup_record is not None:
            self._restore_backup_record(item.backup_record)
            return
        if item.deployment_record and item.deployment_record.action == "install":
            mod = self.app.manifest.get_mod(item.deployment_record.mod_id)
            if mod is None:
                messagebox.showinfo("Undo Not Available", "That install is no longer active.")
                return
            record = self.app.installer.uninstall(mod)
            self.app.manifest.add_record(record)
            self.app.manifest.remove_mod(mod.mod_id)
            self.app.refresh_mods_tab()
            self.refresh()
            return
        messagebox.showinfo("Restore Not Available", "Use a raw backup copy for this type of recovery.")

    def _on_undo(self) -> None:
        item = self._selected_item
        if item is None or item.deployment_record is None:
            messagebox.showinfo("Undo Not Available", "Select an install-related recovery item first.")
            return
        record = item.deployment_record
        mod = self.app.manifest.get_mod(record.mod_id)
        if record.action == "install" and mod is not None:
            uninstall_record = self.app.installer.uninstall(mod)
            self.app.manifest.add_record(uninstall_record)
            self.app.manifest.remove_mod(mod.mod_id)
        elif record.action == "disable" and mod is not None:
            self.app.installer.enable(mod)
            self.app.manifest.update_mod(mod)
        elif record.action == "enable" and mod is not None:
            self.app.installer.disable(mod)
            self.app.manifest.update_mod(mod)
        else:
            messagebox.showinfo("Undo Not Available", "That recovery item cannot be undone automatically.")
            return
        self.app.refresh_mods_tab()
        self.refresh()

    def _on_open_files(self) -> None:
        item = self._selected_item
        if item is None:
            return
        if item.backup_record is not None:
            path = Path(item.backup_record.backup_path).parent
        elif item.deployment_record and item.deployment_record.files:
            path = Path(item.deployment_record.files[0].dest_path).parent
        else:
            return
        if path.exists():
            os.startfile(str(path))

    def _on_restore_raw(self) -> None:
        if not self._selected_backup:
            messagebox.showinfo("No Selection", "Select a raw backup copy first.")
            return
        self._restore_backup_record(self._selected_backup)

    def _restore_backup_record(self, record: BackupRecord) -> None:
        confirm = messagebox.askyesno("Restore Previous Version", f"Restore backup?\n\n{record.description}\n{record.source_path}")
        if not confirm:
            return
        if record.category.startswith("remote_"):
            restored = self.app.remote_config_svc.restore_backup_record(record)
        else:
            restored = self.app.backup.restore_backup(record)
        if restored:
            self.refresh()
            self.app.refresh_mods_tab()
        else:
            messagebox.showerror("Restore Failed", "Could not restore that backup.")

    def _on_delete_raw(self) -> None:
        if not self._selected_backup:
            messagebox.showinfo("No Selection", "Select a raw backup copy first.")
            return
        if not messagebox.askyesno("Remove Backup Copy", f"Delete this backup copy?\n\n{self._selected_backup.backup_path}"):
            return
        if self.app.backup.delete_backup(self._selected_backup, delete_file=True):
            self.refresh()
        else:
            messagebox.showerror("Delete Failed", "Could not delete that backup copy.")

    def _on_open_folder(self) -> None:
        folder = self.app.backup.backup_root
        if folder.is_dir():
            os.startfile(str(folder))

    def _on_cleanup_old(self) -> None:
        limit = self.app.backup.max_backups_per_source or DEFAULT_MAX_BACKUPS_PER_SOURCE
        if not messagebox.askyesno(
            "Clean Up Old Backups",
            f"Keep only the newest {limit} backups per source and remove older copies?",
        ):
            return
        removed = self.app.backup.prune_retention(max_backups_per_source=limit)
        self.refresh()
        if removed:
            self._summary_label.configure(text=f"Removed {removed} old backup(s).")

    @staticmethod
    def _set_box(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")
