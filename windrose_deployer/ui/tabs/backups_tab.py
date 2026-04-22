"""Activity screen with recovery actions and advanced raw backup browser."""
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

_TIMELINE_RENDER_LIMIT = 250


class BackupsTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", *, auto_refresh: bool = True, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._selected_item = None
        self._selected_backup: Optional[BackupRecord] = None
        self._selected_backup_ids: set[str] = set()
        self._all_backups: list[BackupRecord] = []
        self._timeline_rows: list[ctk.CTkFrame] = []
        self._backup_rows: list[ctk.CTkFrame] = []
        self._action_buttons: list[ctk.CTkButton] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._filter_var = ctk.StringVar(value="all")
        self._advanced_visible = False

        self._build_header()
        self._build_main()
        if auto_refresh:
            self.refresh()

    def _build_header(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(frame, text="Activity & Backups", font=self.app.ui_font("title")).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        self._filter_menu = ctk.CTkOptionMenu(
            frame,
            variable=self._filter_var,
            values=["all", "mods", "server", "hosted"],
            width=130,
            font=self.app.ui_font("body"),
            command=lambda _value: self.refresh(),
        )
        self._filter_menu.grid(row=0, column=1, sticky="w")
        self._summary_label = ctk.CTkLabel(frame, text="", anchor="w", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._summary_label.grid(row=0, column=2, sticky="ew", padx=(12, 12))
        backup_btn = ctk.CTkButton(
            frame,
            text="Back Up Now",
            width=112,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self.app._server_tab._on_backup_now,
        )
        backup_btn.grid(row=0, column=3, sticky="e", padx=(0, 8))
        self._action_buttons.append(backup_btn)
        cleanup_btn = ctk.CTkButton(
            frame,
            text="Clean Up Old",
            width=120,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_cleanup_old,
        )
        cleanup_btn.grid(row=0, column=4, sticky="e", padx=(0, 8))
        self._action_buttons.append(cleanup_btn)
        self._advanced_btn = ctk.CTkButton(
            frame,
            text="Show Raw Backup Copies",
            width=180,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._toggle_advanced,
        )
        self._advanced_btn.grid(row=0, column=5, sticky="e")
        self._action_buttons.append(self._advanced_btn)
        self._result_label = ctk.CTkLabel(
            frame,
            text="",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._result_label.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(4, 0))

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

        self._detail_title = ctk.CTkLabel(right, text="Select an activity item", font=self.app.ui_font("detail_title"))
        self._detail_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self._detail_meta = ctk.CTkLabel(right, text="", justify="left", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._detail_meta.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        actions = ctk.CTkFrame(right)
        actions.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._restore_btn = ctk.CTkButton(actions, text="Restore Previous Version", width=180, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), fg_color="#2d8a4e", hover_color="#236b3d", command=self._on_restore)
        self._restore_btn.pack(side="left", padx=(0, 6))
        self._undo_btn = ctk.CTkButton(actions, text="Undo Last Change", width=140, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), fg_color="#2980b9", hover_color="#2471a3", command=self._on_undo)
        self._undo_btn.pack(side="left", padx=6)
        self._open_files_btn = ctk.CTkButton(actions, text="Open Affected Files", width=150, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), command=self._on_open_files)
        self._open_files_btn.pack(side="left", padx=6)
        self._action_buttons.extend([self._restore_btn, self._undo_btn, self._open_files_btn])

        self._detail_box = ctk.CTkTextbox(right, height=240, font=self.app.ui_font("mono"))
        self._detail_box.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._detail_box.configure(state="disabled")

        self._advanced_frame = ctk.CTkFrame(right)
        self._advanced_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._advanced_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._advanced_frame, text="Raw Backup Copies", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        self._backup_list = ctk.CTkScrollableFrame(self._advanced_frame, height=180)
        self._backup_list.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._backup_list.grid_columnconfigure(0, weight=1)
        raw_actions = ctk.CTkFrame(self._advanced_frame, fg_color="transparent")
        raw_actions.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._restore_raw_btn = ctk.CTkButton(raw_actions, text="Restore Previous Version", width=170, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), command=self._on_restore_raw)
        self._restore_raw_btn.pack(side="left", padx=(0, 6))
        self._delete_raw_btn = ctk.CTkButton(raw_actions, text="Delete Selected", width=138, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), fg_color="#c0392b", hover_color="#962d22", command=self._on_delete_raw)
        self._delete_raw_btn.pack(side="left", padx=6)
        self._delete_all_raw_btn = ctk.CTkButton(raw_actions, text="Delete All", width=112, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), fg_color="#962d22", hover_color="#7d241b", command=self._on_delete_all_raw)
        self._delete_all_raw_btn.pack(side="left", padx=6)
        self._open_folder_btn = ctk.CTkButton(raw_actions, text="Open Backup Folder", width=140, height=self.app.ui_tokens.compact_button_height, font=self.app.ui_font("body"), command=self._on_open_folder)
        self._open_folder_btn.pack(side="left", padx=6)
        self._action_buttons.extend([self._restore_raw_btn, self._delete_raw_btn, self._delete_all_raw_btn, self._open_folder_btn])
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
        self._detail_title.configure(text="Select an activity item")
        self._detail_meta.configure(text="")
        self._set_box(self._detail_box, "")

        items = self.app.recovery.build_timeline()
        items = [item for item in items if self._matches_filter(item)]
        visible_items = items[:_TIMELINE_RENDER_LIMIT]
        for index, item in enumerate(visible_items):
            self._add_timeline_row(item, index)

        self._all_backups = sorted(self.app.backup.list_backups(), key=lambda item: item.timestamp, reverse=True)
        self._selected_backup_ids.intersection_update({record.backup_id for record in self._all_backups})
        if self._advanced_visible:
            self._render_backup_rows()

        shown_text = f"{len(visible_items)} shown / " if len(items) > len(visible_items) else ""
        self._summary_label.configure(text=f"{shown_text}{len(items)} activity items | {len(self._all_backups)} raw backups")

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
        ctk.CTkLabel(row, text=item.title, anchor="w", font=self.app.ui_font("row_title")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 2)
        )
        ctk.CTkLabel(row, text=item.subtitle, anchor="w", text_color="#95a5a6", font=self.app.ui_font("small")).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 2)
        )
        ctk.CTkLabel(row, text=item.summary, anchor="w", text_color="#c1c7cd", wraplength=self.app.ui_tokens.panel_wrap, font=self.app.ui_font("body")).grid(
            row=2, column=0, sticky="ew", padx=10, pady=(0, 2)
        )
        ctk.CTkLabel(row, text=item.timestamp[:19].replace("T", " "), anchor="w", text_color="#6f7a81", font=self.app.ui_font("tiny")).grid(
            row=3, column=0, sticky="ew", padx=10, pady=(0, 8)
        )
        for widget in row.winfo_children() + [row]:
            widget.bind("<Button-1>", lambda _event, value=item: self._select_item(value))
        self._timeline_rows.append(row)

    def _render_backup_rows(self) -> None:
        for widget in self._backup_rows:
            widget.destroy()
        self._backup_rows.clear()
        for index, record in enumerate(self._all_backups):
            self._add_backup_row(record, index)

    def _add_backup_row(self, record: BackupRecord, index: int) -> None:
        row = ctk.CTkFrame(self._backup_list, cursor="hand2")
        row.grid(row=index, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(1, weight=1)
        selected_var = tk.BooleanVar(value=record.backup_id in self._selected_backup_ids)
        checkbox = ctk.CTkCheckBox(
            row,
            text="",
            variable=selected_var,
            width=20,
            command=lambda value=record, var=selected_var: self._toggle_backup_checked(value, var.get()),
        )
        checkbox.grid(row=0, column=0, rowspan=3, sticky="n", padx=(10, 2), pady=(10, 8))
        ctk.CTkLabel(row, text=record.category.replace("_", " ").title(), anchor="w", font=self.app.ui_font("small")).grid(
            row=0, column=1, sticky="ew", padx=10, pady=(8, 2)
        )
        ctk.CTkLabel(row, text=record.description or Path(record.backup_path).name, anchor="w", text_color="#c1c7cd", wraplength=self.app.ui_tokens.panel_wrap, font=self.app.ui_font("body")).grid(
            row=1, column=1, sticky="ew", padx=10, pady=(0, 2)
        )
        ctk.CTkLabel(row, text=record.timestamp[:19].replace("T", " "), anchor="w", text_color="#6f7a81", font=self.app.ui_font("tiny")).grid(
            row=2, column=1, sticky="ew", padx=10, pady=(0, 8)
        )
        for widget in row.winfo_children() + [row]:
            if widget is checkbox:
                continue
            widget.bind("<Button-1>", lambda _event, value=record: self._select_backup(value))
        self._backup_rows.append(row)

    def _select_item(self, item) -> None:
        self._selected_item = item
        self._detail_title.configure(text=item.title)
        self._detail_meta.configure(text=f"{item.subtitle}\n{item.timestamp[:19].replace('T', ' ')}")
        self._set_box(self._detail_box, "\n".join(item.details))

    def _select_backup(self, record: BackupRecord) -> None:
        self._selected_backup = record
        self._selected_backup_ids.add(record.backup_id)

    def _toggle_backup_checked(self, record: BackupRecord, selected: bool) -> None:
        if selected:
            self._selected_backup_ids.add(record.backup_id)
            self._selected_backup = record
        else:
            self._selected_backup_ids.discard(record.backup_id)
            if self._selected_backup and self._selected_backup.backup_id == record.backup_id:
                self._selected_backup = None

    def _set_result(self, text: str, *, level: str = "info") -> None:
        colors = {
            "success": "#2d8a4e",
            "warning": "#e67e22",
            "error": "#c0392b",
            "info": "#95a5a6",
        }
        self._result_label.configure(text=text, text_color=colors.get(level, "#95a5a6"))

    def apply_ui_preferences(self) -> None:
        tokens = self.app.ui_tokens
        self._filter_menu.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
        self._summary_label.configure(font=self.app.ui_font("small"))
        self._result_label.configure(font=self.app.ui_font("small"), wraplength=tokens.detail_wrap)
        self._detail_title.configure(font=self.app.ui_font("detail_title"))
        self._detail_meta.configure(font=self.app.ui_font("small"))
        self._detail_box.configure(font=self.app.ui_font("mono"))
        for button in self._action_buttons:
            try:
                button.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
            except Exception:
                pass
        if self._timeline_rows or self._backup_rows:
            self.refresh()

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self._advanced_frame.grid()
            self._advanced_btn.configure(text="Hide Raw Backup Copies")
            self._render_backup_rows()
        else:
            self._advanced_frame.grid_remove()
            self._advanced_btn.configure(text="Show Raw Backup Copies")
            for widget in self._backup_rows:
                widget.destroy()
            self._backup_rows.clear()

    def _on_restore(self) -> None:
        item = self._selected_item
        if item is None:
            self._set_result("Select an activity item first.", level="info")
            return
        if item.backup_record is not None:
            self._restore_backup_record(item.backup_record)
            return
        if item.deployment_record and item.deployment_record.action == "install":
            mod = self.app.manifest.get_mod(item.deployment_record.mod_id)
            if mod is None:
                self._set_result("That install is no longer active.", level="info")
                return
            record = self.app.installer.uninstall(mod)
            self.app.manifest.add_record(record)
            self.app.manifest.remove_mod(mod.mod_id)
            self.app.refresh_mods_tab()
            self.refresh()
            self._set_result(f"Restored by uninstalling {item.title.lower()}.", level="success")
            return
        self._set_result("Use a raw backup copy for this type of restore.", level="info")

    def _on_undo(self) -> None:
        item = self._selected_item
        if item is None or item.deployment_record is None:
            self._set_result("Select an install-related activity item first.", level="info")
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
            self._set_result("That activity item cannot be undone automatically.", level="info")
            return
        self.app.refresh_mods_tab()
        self.refresh()
        self._set_result("Undid the selected activity action.", level="success")

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
        selected = self._selected_backups()
        if len(selected) != 1:
            self._set_result("Select exactly one raw backup copy to restore.", level="info")
            return
        self._restore_backup_record(selected[0])

    def _restore_backup_record(self, record: BackupRecord) -> None:
        if not self.app.confirm_action(
            "destructive",
            "Restore Previous Version",
            f"Restore backup?\n\n{record.description}\n{record.source_path}",
        ):
            return
        if record.category.startswith("remote_"):
            restored = self.app.remote_config_svc.restore_backup_record(record)
        else:
            restored = self.app.backup.restore_backup(record)
        if restored:
            self.refresh()
            self.app.refresh_mods_tab()
            self._set_result("Restored the selected backup copy.", level="success")
        else:
            messagebox.showerror("Restore Failed", "Could not restore that backup.")

    def _on_delete_raw(self) -> None:
        selected = self._selected_backups()
        if not selected:
            self._set_result("Select one or more raw backup copies first.", level="info")
            return
        if not self.app.confirm_action(
            "destructive",
            "Delete Selected Backup Copies",
            f"Delete {len(selected)} selected backup copie(s)?",
        ):
            return
        removed = 0
        for record in selected:
            if self.app.backup.delete_backup(record, delete_file=True):
                removed += 1
        self.refresh()
        if removed:
            self._set_result(f"Removed {removed} selected backup copie(s).", level="success")
        else:
            messagebox.showerror("Delete Failed", "Could not delete that backup copy.")

    def _on_delete_all_raw(self) -> None:
        if not self._all_backups:
            self._set_result("There are no raw backup copies to delete.", level="info")
            return
        if not self.app.confirm_action(
            "destructive",
            "Delete All Backup Copies",
            f"Delete all {len(self._all_backups)} raw backup copie(s)?",
        ):
            return
        removed = 0
        for record in list(self._all_backups):
            if self.app.backup.delete_backup(record, delete_file=True):
                removed += 1
        self.refresh()
        if removed:
            self._set_result(f"Removed {removed} raw backup copie(s).", level="success")
        else:
            messagebox.showerror("Delete Failed", "Could not delete the raw backup copies.")

    def _on_open_folder(self) -> None:
        folder = self.app.backup.backup_root
        if folder.is_dir():
            os.startfile(str(folder))

    def _on_cleanup_old(self) -> None:
        limit = self.app.backup.max_backups_per_source or DEFAULT_MAX_BACKUPS_PER_SOURCE
        if not self.app.confirm_action(
            "destructive",
            "Clean Up Old Backups",
            f"Keep only the newest {limit} backups per source and remove older copies?",
        ):
            return
        removed = self.app.backup.prune_retention(max_backups_per_source=limit)
        self.refresh()
        if removed:
            self._set_result(f"Removed {removed} old backup(s).", level="success")
        else:
            self._set_result("No old backups needed cleanup.", level="info")

    def _selected_backups(self) -> list[BackupRecord]:
        selected_ids = set(self._selected_backup_ids)
        if self._selected_backup is not None:
            selected_ids.add(self._selected_backup.backup_id)
        return [record for record in self._all_backups if record.backup_id in selected_ids]

    @staticmethod
    def _set_box(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")
