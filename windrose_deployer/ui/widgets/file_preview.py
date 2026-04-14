"""Archive file tree preview widget."""
from __future__ import annotations

import tkinter as tk
from pathlib import PurePosixPath

import customtkinter as ctk

from ...models.archive_info import ArchiveInfo


class FilePreview(ctk.CTkFrame):
    """Displays archive contents as a flat file list with type indicators."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._header = ctk.CTkLabel(self, text="Archive Contents", anchor="w",
                                    font=ctk.CTkFont(weight="bold"))
        self._header.pack(fill="x", padx=8, pady=(4, 0))

        self._info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._info_frame.pack(fill="x", padx=8, pady=2)
        self._type_label = ctk.CTkLabel(self._info_frame, text="Type: —", anchor="w")
        self._type_label.pack(side="left")
        self._count_label = ctk.CTkLabel(self._info_frame, text="Files: —", anchor="e")
        self._count_label.pack(side="right")

        self._textbox = ctk.CTkTextbox(self, height=200, state="disabled",
                                       font=ctk.CTkFont(family="Consolas", size=11))
        self._textbox.pack(fill="both", expand=True, padx=4, pady=4)

    def show(self, info: ArchiveInfo) -> None:
        self._type_label.configure(text=f"Type: {info.archive_type.value}")
        self._count_label.configure(text=f"Files: {info.total_files}")

        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")

        if info.pak_entries:
            self._textbox.insert("end", "=== PAK FILES ===\n")
            for e in info.pak_entries:
                self._textbox.insert("end", f"  [PAK] {e.path}\n")

        if info.companion_entries:
            self._textbox.insert("end", "\n=== COMPANION FILES ===\n")
            for e in info.companion_entries:
                suffix = PurePosixPath(e.path).suffix.upper().lstrip(".")
                self._textbox.insert("end", f"  [{suffix}] {e.path}\n")

        if info.loose_entries:
            self._textbox.insert("end", "\n=== LOOSE FILES ===\n")
            for e in info.loose_entries:
                self._textbox.insert("end", f"  {e.path}\n")

        if info.variant_groups:
            self._textbox.insert("end", "\n=== VARIANT GROUPS ===\n")
            for vg in info.variant_groups:
                self._textbox.insert("end", f"  Group: {vg.base_name}\n")
                for v in vg.variants:
                    name = PurePosixPath(v.path).name
                    self._textbox.insert("end", f"    - {name}\n")

        if info.warnings:
            self._textbox.insert("end", "\n=== WARNINGS ===\n")
            for w in info.warnings:
                self._textbox.insert("end", f"  ! {w}\n")

        self._textbox.configure(state="disabled")

    def clear(self) -> None:
        self._type_label.configure(text="Type: —")
        self._count_label.configure(text="Files: —")
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
