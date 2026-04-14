"""Backups tab — view and restore backups."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.backup_manager import BackupRecord

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class BackupsTab(ctk.CTkFrame):
    def __init__(self, master, app: AppWindow, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._selected_record: Optional[BackupRecord] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_list()
        self._build_actions()

    def _build_toolbar(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(frame, text="Backup History",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)

        self._filter_var = ctk.StringVar(value="all")
        self._filter_menu = ctk.CTkOptionMenu(
            frame, variable=self._filter_var,
            values=["all", "installs", "server_config"],
            command=lambda _: self.refresh(),
            width=140,
        )
        self._filter_menu.pack(side="right", padx=8)
        ctk.CTkLabel(frame, text="Filter:").pack(side="right", padx=4)

        self._refresh_btn = ctk.CTkButton(frame, text="Refresh", width=80, command=self.refresh)
        self._refresh_btn.pack(side="right", padx=8)

    def _build_list(self) -> None:
        self._list_frame = ctk.CTkScrollableFrame(self)
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._list_frame.grid_columnconfigure(0, weight=1)
        self._row_widgets: list[ctk.CTkFrame] = []

    def _build_actions(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

        self._restore_btn = ctk.CTkButton(
            frame, text="Restore Selected", width=140,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_restore,
        )
        self._restore_btn.pack(side="left", padx=8)

        self._open_btn = ctk.CTkButton(
            frame, text="Open Backup Folder", width=160,
            command=self._on_open_folder,
        )
        self._open_btn.pack(side="left", padx=8)

        self._status_label = ctk.CTkLabel(frame, text="")
        self._status_label.pack(side="left", padx=8, fill="x", expand=True)

    # ---------------------------------------------------------- refresh

    def refresh(self) -> None:
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()
        self._selected_record = None

        category = self._filter_var.get()
        if category == "all":
            records = self.app.backup.list_backups()
        else:
            records = self.app.backup.list_backups(category)

        records_sorted = sorted(records, key=lambda r: r.timestamp, reverse=True)

        for i, record in enumerate(records_sorted):
            self._add_row(record, i)

        self._status_label.configure(text=f"{len(records_sorted)} backup(s)")

    def _add_row(self, record: BackupRecord, idx: int) -> None:
        row = ctk.CTkFrame(self._list_frame, cursor="hand2")
        row.grid(row=idx, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(1, weight=1)

        cat_colors = {"installs": "#3498db", "server_config": "#e67e22"}
        cat_color = cat_colors.get(record.category, "#95a5a6")

        cat_label = ctk.CTkLabel(row, text=record.category.upper(),
                                 text_color=cat_color,
                                 font=ctk.CTkFont(size=10, weight="bold"),
                                 width=100)
        cat_label.grid(row=0, column=0, padx=(8, 4), pady=6)

        desc = ctk.CTkLabel(row, text=record.description, anchor="w")
        desc.grid(row=0, column=1, sticky="w", padx=4, pady=6)

        ts = ctk.CTkLabel(row, text=record.timestamp[:19], anchor="e",
                          text_color="#95a5a6", font=ctk.CTkFont(size=11))
        ts.grid(row=0, column=2, sticky="e", padx=8, pady=6)

        exists = Path(record.backup_path).is_file()
        status_text = "●" if exists else "✕"
        status_color = "#2d8a4e" if exists else "#c0392b"
        status = ctk.CTkLabel(row, text=status_text, text_color=status_color, width=20)
        status.grid(row=0, column=3, padx=(4, 8), pady=6)

        for widget in (row, cat_label, desc, ts, status):
            widget.bind("<Button-1>", lambda e, r=record: self._select(r))

        self._row_widgets.append(row)

    def _select(self, record: BackupRecord) -> None:
        self._selected_record = record
        src = Path(record.source_path).name
        bk = Path(record.backup_path).name
        self._status_label.configure(text=f"Selected: {src} -> {bk}")

    # ---------------------------------------------------------- actions

    def _on_restore(self) -> None:
        if not self._selected_record:
            messagebox.showinfo("No Selection", "Select a backup to restore.")
            return

        record = self._selected_record
        confirm = messagebox.askyesno(
            "Confirm Restore",
            f"Restore backup?\n\n"
            f"Source: {record.source_path}\n"
            f"Backup: {record.backup_path}\n\n"
            "This will overwrite the current file.",
        )
        if not confirm:
            return

        if self.app.backup.restore_backup(record):
            messagebox.showinfo("Restored", "Backup restored successfully.")
            self.refresh()
        else:
            messagebox.showerror("Error", "Failed to restore backup — file may be missing.")

    def _on_open_folder(self) -> None:
        folder = self.app.backup.backup_root
        if folder.is_dir():
            os.startfile(str(folder))
        else:
            messagebox.showinfo("Not Found", "Backup folder does not exist yet.")
