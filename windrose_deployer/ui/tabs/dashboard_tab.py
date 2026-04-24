"""Dashboard tab for operational overview."""
from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from ...core.archive_inspector import inspect_archive
from ...core.conflict_detector import check_plan_conflicts
from ...core.remote_deployer import plan_remote_deployment
from ...models.mod_install import InstallTarget


_COMPARE_TARGETS = {
    "Local Server": "server",
    "Dedicated Server": "dedicated_server",
    "Hosted Server": "hosted",
}


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, *, app):
        super().__init__(master)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._action_buttons: list[ctk.CTkButton] = []
        self._status_values: dict[str, ctk.CTkLabel] = {}
        self._setup_values: dict[str, ctk.CTkLabel] = {}
        self._count_values: dict[str, ctk.CTkLabel] = {}
        self._framework_values: dict[str, ctk.CTkLabel] = {}
        self._compare_target_var = ctk.StringVar(value="Dedicated Server")
        self._build()

    def _build(self) -> None:
        body = ctk.CTkScrollableFrame(self)
        body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._title = ctk.CTkLabel(body, text="Dashboard", font=self.app.ui_font("title"))
        self._title.grid(row=0, column=0, sticky="w", padx=8, pady=(0, 2))

        self._subtitle = ctk.CTkLabel(
            body,
            text="Operations home for Windrose client, local server, dedicated server, and hosted server state.",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._subtitle.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 10))

        self._status_card = self._make_card(body, row=2, column=0, title="Status")
        self._current_card = self._make_card(body, row=2, column=1, title="Current Setup")
        self._frameworks_card = self._make_card(body, row=3, column=0, title="Frameworks")
        self._parity_card = self._make_card(body, row=3, column=1, title="Mod Parity")
        self._actions_card = self._make_card(body, row=4, column=0, title="Quick Actions", columnspan=2)

        self._build_status_card()
        self._build_current_card()
        self._build_frameworks_card()
        self._build_parity_card()
        self._build_actions_card()

    def _make_card(self, body, *, row: int, column: int, title: str, columnspan: int = 1):
        card = ctk.CTkFrame(body)
        padx = 8 if columnspan > 1 else (8 if column == 0 else (4, 8))
        card.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=padx, pady=(0, 8))
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text=title, font=self.app.ui_font("card_title")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(14, 10)
        )
        return card

    def _build_status_card(self) -> None:
        labels = [
            ("client", "Windrose Client"),
            ("server", "Local Server"),
            ("dedicated_server", "Dedicated Server"),
            ("hosted", "Hosted Server"),
        ]
        for index, (key, label) in enumerate(labels, start=1):
            ctk.CTkLabel(
                self._status_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(self._status_card, text="", anchor="e", font=self.app.ui_font("body"))
            value.grid(row=index, column=1, sticky="e", padx=14, pady=4)
            self._status_values[key] = value

    def _build_frameworks_card(self) -> None:
        labels = [
            ("ue4ss", "UE4SS Runtime"),
            ("rcon", "RCON"),
            ("windrose_plus", "WindrosePlus"),
        ]
        for index, (key, label) in enumerate(labels, start=1):
            ctk.CTkLabel(
                self._frameworks_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(
                self._frameworks_card,
                text="",
                anchor="w",
                justify="left",
                font=self.app.ui_font("body"),
                wraplength=self.app.ui_tokens.detail_wrap,
            )
            value.grid(row=index, column=1, sticky="ew", padx=14, pady=4)
            self._framework_values[key] = value

        self._framework_note = ctk.CTkLabel(
            self._frameworks_card,
            text="WindrosePlus files are present; activation depends on its own install/start workflow.",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            wraplength=self.app.ui_tokens.panel_wrap,
        )
        self._framework_note.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 14))

    def _build_current_card(self) -> None:
        labels = [
            ("source", "Active Source"),
            ("world", "Active World"),
            ("profile", "Hosted Profile"),
            ("apply", "Last Apply"),
            ("restart", "Last Restart"),
            ("backup", "Last Backup"),
        ]
        for index, (key, label) in enumerate(labels, start=1):
            ctk.CTkLabel(
                self._current_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(
                self._current_card,
                text="",
                justify="left",
                anchor="e",
                font=self.app.ui_font("body"),
                wraplength=self.app.ui_tokens.panel_wrap - 40,
            )
            value.grid(row=index, column=1, sticky="e", padx=14, pady=4)
            self._setup_values[key] = value

    def _build_parity_card(self) -> None:
        ctk.CTkLabel(
            self._parity_card,
            text="Compare Target",
            font=self.app.ui_font("body"),
            text_color="#aeb6bf",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 6))
        self._compare_target_menu = ctk.CTkOptionMenu(
            self._parity_card,
            variable=self._compare_target_var,
            values=list(_COMPARE_TARGETS.keys()),
            width=170,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
        )
        self._compare_target_menu.grid(row=1, column=1, sticky="e", padx=14, pady=(0, 6))

        self._parity_state = ctk.CTkLabel(
            self._parity_card,
            text="",
            anchor="w",
            font=self.app.ui_font("row_title"),
        )
        self._parity_state.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 4))

        self._parity_summary = ctk.CTkLabel(
            self._parity_card,
            text="",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            wraplength=self.app.ui_tokens.panel_wrap,
        )
        self._parity_summary.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))

        self._drift_label = ctk.CTkLabel(
            self._parity_card,
            text="",
            justify="left",
            anchor="w",
            text_color="#e67e22",
            font=self.app.ui_font("small"),
            wraplength=self.app.ui_tokens.panel_wrap,
        )
        self._drift_label.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))

        button_bar = ctk.CTkFrame(self._parity_card, fg_color="transparent")
        button_bar.grid(row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 8))
        button_bar.grid_columnconfigure(0, weight=1)
        button_bar.grid_columnconfigure(1, weight=1)

        self._compare_btn = ctk.CTkButton(
            button_bar,
            text="Run Compare",
            width=126,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._run_compare,
        )
        self._compare_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 4))
        self._action_buttons.append(self._compare_btn)
        self._open_compare_btn = ctk.CTkButton(
            button_bar,
            text="Open Full Compare",
            width=146,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_full_compare,
        )
        self._open_compare_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 4))
        self._action_buttons.append(self._open_compare_btn)
        self._review_sync_btn = ctk.CTkButton(
            button_bar,
            text="Review Sync Actions",
            width=170,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            state="disabled",
            command=self._review_sync_actions,
        )
        self._review_sync_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self._action_buttons.append(self._review_sync_btn)

        labels = [
            ("client", "Client"),
            ("server", "Local Server"),
            ("dedicated_server", "Dedicated Server"),
            ("hosted", "Hosted Server"),
        ]
        for index, (key, label) in enumerate(labels, start=6):
            ctk.CTkLabel(
                self._parity_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(self._parity_card, text="0", anchor="e", font=self.app.ui_font("body"))
            value.grid(row=index, column=1, sticky="e", padx=14, pady=4)
            self._count_values[key] = value

    def _build_actions_card(self) -> None:
        actions = ctk.CTkFrame(self._actions_card, fg_color="transparent")
        actions.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=14, pady=(0, 14))
        for column in range(4):
            actions.grid_columnconfigure(column, weight=1)

        self._add_action_button(
            actions, row=0, column=0, text="Launch Windrose", command=self.app._on_start_game,
            fg="#2d8a4e", hover="#236b3d",
        )
        self._add_action_button(
            actions, row=0, column=1, text="Launch Dedicated Server", command=self.app._on_start_server,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=0, column=2, text="Open Server Folder", command=self.app._server_tab._open_active_server_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=0, column=3, text="Back Up Now", command=self.app._server_tab._on_backup_now,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=1, column=0, text="Open Client Mods", command=self._open_client_mods_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=1, column=1, text="Open Local Server Mods", command=self._open_local_server_mods_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=1, column=2, text="Open Dedicated Server Mods", command=self._open_dedicated_server_mods_folder,
            fg="#555555", hover="#666666",
        )

    def _add_action_button(self, parent, *, row: int, column: int, text: str, command, fg: str, hover: str) -> None:
        button = ctk.CTkButton(
            parent,
            text=text,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color=fg,
            hover_color=hover,
            command=command,
        )
        button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
        self._action_buttons.append(button)

    def _run_compare(self) -> None:
        self._set_server_target_from_dashboard(refresh_inventory=False)
        self.app._server_tab.compare_now()

    def _open_full_compare(self) -> None:
        self._set_server_target_from_dashboard(refresh_inventory=False)
        self.app._tabview.set("Server")
        self.app._on_tab_changed("Server")

    def _dashboard_target_key(self) -> str:
        return _COMPARE_TARGETS.get(self._compare_target_var.get(), "dedicated_server")

    def _set_server_target_from_dashboard(self, *, refresh_inventory: bool = False) -> str:
        target = self._dashboard_target_key()
        self.app._server_tab.set_source_for_compare(target, refresh_inventory=refresh_inventory)
        return target

    def _review_sync_actions(self) -> None:
        target = self._set_server_target_from_dashboard(refresh_inventory=False)
        server_tab = self.app._server_tab
        if server_tab.last_compare_target() != target or server_tab.last_compare_report() is None:
            messagebox.showinfo("Run Compare First", "Run Compare for the selected target before reviewing sync actions.")
            return
        if server_tab.last_compare_report().review_needed == 0:
            messagebox.showinfo("No Sync Actions", "The last compare did not find any differences that need review.")
            return

        if target == "hosted":
            profile = server_tab._selected_remote_profile()
            if profile is None:
                messagebox.showwarning("Hosted Profile Required", "Choose a hosted profile first.")
                return
            self._review_sync_btn.configure(state="disabled", text="Checking Hosted...")

            def _work() -> None:
                try:
                    remote_files = self.app.remote_deployer.list_remote_files(profile)
                    self.app.dispatch_to_ui(
                        lambda: self._open_sync_review_dialog(target, remote_files=remote_files)
                    )
                except Exception as exc:
                    self.app.dispatch_to_ui(
                        lambda error=str(exc): messagebox.showerror("Hosted Sync Review Failed", error)
                    )
                finally:
                    def _restore_review_button() -> None:
                        if self._review_sync_btn.winfo_exists():
                            self._review_sync_btn.configure(text="Review Sync Actions")
                            self.refresh_view()
                    self.app.dispatch_to_ui(_restore_review_button)

            threading.Thread(target=_work, daemon=True).start()
            return

        self._open_sync_review_dialog(target)

    def _open_sync_review_dialog(self, target: str, *, remote_files: list[str] | None = None) -> None:
        actions, notes = self._build_sync_review_actions(target, remote_files=remote_files or [])
        dialog = ctk.CTkToplevel(self)
        dialog.title("Review Sync Actions")
        self.app.center_dialog(dialog, 760, 560)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        target_label = self._target_label(target)
        ctk.CTkLabel(
            dialog,
            text=f"Review Sync Actions: Client -> {target_label}",
            font=self.app.ui_font("detail_title"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            dialog,
            text=(
                "Only safe additive actions are checked by default. "
                "Server-only removals and ambiguous items are listed for review, not applied automatically."
            ),
            text_color="#95a5a6",
            justify="left",
            wraplength=700,
            font=self.app.ui_font("body"),
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        list_frame = ctk.CTkScrollableFrame(dialog)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        list_frame.grid_columnconfigure(1, weight=1)

        action_vars: list[tuple[dict, tk.BooleanVar]] = []
        row = 0
        if actions:
            for action in actions:
                var = tk.BooleanVar(value=bool(action["enabled"]))
                checkbox = ctk.CTkCheckBox(
                    list_frame,
                    text="",
                    variable=var,
                    state="normal" if action["enabled"] else "disabled",
                    width=24,
                )
                checkbox.grid(row=row, column=0, sticky="nw", padx=(8, 4), pady=(8, 2))
                title = action["title"]
                detail = action["detail"] if action["enabled"] else f"{action['detail']} | {action['reason']}"
                ctk.CTkLabel(
                    list_frame,
                    text=title,
                    font=self.app.ui_font("row_title"),
                    anchor="w",
                    justify="left",
                ).grid(row=row, column=1, sticky="ew", padx=4, pady=(8, 0))
                ctk.CTkLabel(
                    list_frame,
                    text=detail,
                    text_color="#95a5a6" if action["enabled"] else "#e67e22",
                    font=self.app.ui_font("small"),
                    anchor="w",
                    justify="left",
                    wraplength=640,
                ).grid(row=row + 1, column=1, sticky="ew", padx=4, pady=(0, 8))
                action_vars.append((action, var))
                row += 2
        else:
            ctk.CTkLabel(
                list_frame,
                text="No safe install/upload actions were found for this compare.",
                text_color="#95a5a6",
                font=self.app.ui_font("body"),
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=8)
            row += 1

        if notes:
            ctk.CTkLabel(
                list_frame,
                text="Review Separately",
                font=self.app.ui_font("row_title"),
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(12, 4))
            row += 1
            for note in notes:
                ctk.CTkLabel(
                    list_frame,
                    text=note,
                    text_color="#e67e22",
                    justify="left",
                    anchor="w",
                    wraplength=700,
                    font=self.app.ui_font("small"),
                ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=2)
                row += 1

        status = ctk.CTkLabel(dialog, text="", text_color="#95a5a6", justify="left", wraplength=700)
        status.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))

        def _apply_selected() -> None:
            selected = [action for action, var in action_vars if action["enabled"] and var.get()]
            if not selected:
                status.configure(text="Select at least one safe action first.", text_color="#e67e22")
                return
            apply_btn.configure(state="disabled", text="Applying...")
            if target == "hosted":
                self._apply_hosted_sync_actions(selected, dialog, status, apply_btn)
            else:
                self._apply_local_sync_actions(selected, target, dialog, status, apply_btn)

        apply_btn = ctk.CTkButton(
            buttons,
            text="Apply Selected",
            width=130,
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=_apply_selected,
            state="normal" if any(action["enabled"] for action in actions) else "disabled",
        )
        apply_btn.pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Open Full Compare",
            width=140,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: (dialog.destroy(), self._open_full_compare()),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons,
            text="Close",
            width=100,
            fg_color="#444444",
            hover_color="#555555",
            command=dialog.destroy,
        ).pack(side="right")

    def _build_sync_review_actions(self, target: str, *, remote_files: list[str]) -> tuple[list[dict], list[str]]:
        mods = self.app.manifest.list_mods()
        notes: list[str] = []
        actions: list[dict] = []
        if target == "hosted":
            missing = self.app.server_sync.client_mods_missing_from_hosted(mods, remote_files)
            server_only = self.app.server_sync.hosted_files_missing_from_client(mods, remote_files)
            for file_name in server_only[:25]:
                notes.append(f"{file_name}: hosted-only file. Review before deleting; no automatic removal is selected.")
            if len(server_only) > 25:
                notes.append(f"{len(server_only) - 25} more hosted-only file(s) omitted from this preview.")
        else:
            missing = self.app.server_sync.client_mods_missing_from_local(mods, target=target)
            server_only_mods = self.app.server_sync.server_mods_missing_from_client(mods, target=target)
            for mod in server_only_mods[:25]:
                notes.append(f"{mod.display_name}: installed on {self._target_label(target)} only. Review before uninstalling.")
            if len(server_only_mods) > 25:
                notes.append(f"{len(server_only_mods) - 25} more server-only mod(s) omitted from this preview.")

        for mod in missing:
            action = self._build_sync_action_for_mod(mod, target)
            actions.append(action)

        return actions, notes

    def _build_sync_action_for_mod(self, mod, target: str) -> dict:
        target_label = self._target_label(target)
        archive = Path(mod.source_archive) if mod.source_archive else None
        base = {
            "mod_id": mod.mod_id,
            "name": mod.display_name,
            "target": target,
            "title": f"{mod.display_name} -> {target_label}",
            "detail": f"Source archive: {archive.name if archive else 'not tracked'}",
            "archive": archive,
            "enabled": False,
            "reason": "",
        }
        if archive is None or not archive.is_file():
            base["reason"] = "Missing source archive; install manually from Archives."
            return base
        try:
            info = inspect_archive(archive)
        except Exception as exc:
            base["reason"] = f"Could not inspect archive: {exc}"
            return base
        if info.has_variants or mod.selected_variant:
            base["reason"] = "Variant archive; use full compare/install review so the exact variant is explicit."
            return base
        if mod.component_map:
            base["reason"] = "Selected bundle components; use full compare/install review to avoid uploading extra pak files."
            return base
        if target == "hosted":
            profile = self.app._server_tab._selected_remote_profile()
            if profile is None:
                base["reason"] = "No hosted profile selected."
                return base
            plan = plan_remote_deployment(info, profile, selected_variant=None, mod_name=mod.display_name)
            if not plan.valid:
                base["reason"] = "; ".join(plan.warnings) or "Hosted upload plan is not valid."
                return base
            base.update({"enabled": True, "kind": "hosted_upload", "info": info})
            base["detail"] = f"Upload {plan.file_count} file(s) from {archive.name} to hosted ~mods."
            return base

        target_enum = InstallTarget.SERVER if target == "server" else InstallTarget.DEDICATED_SERVER
        plan, error = self.app._mods_tab._prepare_install_target(info, mod.display_name, target_enum, None)
        if plan is None:
            base["reason"] = error or "Install plan is not valid."
            return base
        conflict_report = check_plan_conflicts(plan, self.app.manifest)
        if conflict_report.has_conflicts:
            base["reason"] = "Managed file conflict detected; open full compare/install review first."
            return base
        base.update(
            {
                "enabled": True,
                "kind": "local_install",
                "preset": "local" if target == "server" else "dedicated",
                "info": info,
            }
        )
        base["detail"] = f"Install {archive.name} to {target_label} using existing backup/history flow."
        return base

    def _apply_local_sync_actions(self, actions: list[dict], target: str, dialog, status, apply_btn) -> None:
        success = 0
        failed = 0
        for action in actions:
            try:
                ok = self.app._mods_tab._run_install_preset(
                    action["info"],
                    action["name"],
                    action["preset"],
                    None,
                    quiet=True,
                    confirm_conflicts=False,
                )
                success += 1 if ok else 0
                failed += 0 if ok else 1
            except Exception:
                failed += 1
        status.configure(
            text=f"Applied {success} sync action(s). {failed} failed." if failed else f"Applied {success} sync action(s).",
            text_color="#2d8a4e" if success and not failed else "#e67e22",
        )
        apply_btn.configure(state="normal", text="Apply Selected")
        self._set_server_target_from_dashboard(refresh_inventory=False)
        self.app._server_tab.compare_now()
        self.refresh_view()

    def _apply_hosted_sync_actions(self, actions: list[dict], dialog, status, apply_btn) -> None:
        profile = self.app._server_tab._selected_remote_profile()
        if profile is None:
            status.configure(text="No hosted profile selected.", text_color="#c0392b")
            apply_btn.configure(state="normal", text="Apply Selected")
            return
        status.configure(text="Uploading selected mods to hosted server...", text_color="#95a5a6")

        def _work() -> None:
            success = 0
            failed = 0
            failed_messages: list[str] = []
            for action in actions:
                try:
                    plan = plan_remote_deployment(action["info"], profile, selected_variant=None, mod_name=action["name"])
                    result = self.app.remote_deployer.deploy(plan, profile)
                    if result.failed:
                        failed += 1
                        failed_messages.extend(result.failed[:2])
                    else:
                        success += 1
                        self.app._server_tab._record_hosted_upload(
                            archive_path=action.get("archive"),
                            display_name=action["name"],
                            profile=profile,
                            plan=plan,
                            result=result,
                            notes=f"Dashboard sync uploaded {action['name']} to hosted server {profile.name} ({result.summary})",
                        )
                except Exception as exc:
                    failed += 1
                    failed_messages.append(f"{action['name']}: {exc}")

            def _show() -> None:
                if not status.winfo_exists():
                    return
                text = f"Uploaded {success} hosted sync action(s)."
                if failed:
                    text += f" {failed} failed."
                    if failed_messages:
                        text += " " + "; ".join(failed_messages[:3])
                status.configure(text=text, text_color="#2d8a4e" if success and not failed else "#e67e22")
                if apply_btn.winfo_exists():
                    apply_btn.configure(state="normal", text="Apply Selected")
                self.app._server_tab._refresh_server_inventory()
                self._set_server_target_from_dashboard(refresh_inventory=False)
                self.app._server_tab.compare_now()
                self.refresh_view()

            self.app.dispatch_to_ui(_show)

        threading.Thread(target=_work, daemon=True).start()

    @staticmethod
    def _target_label(target: str) -> str:
        return {
            "server": "Local Server",
            "dedicated_server": "Dedicated Server",
            "hosted": "Hosted Server",
        }.get(target, target.replace("_", " ").title())

    @staticmethod
    def _open_folder(path) -> bool:
        if path and path.exists():
            try:
                os.startfile(str(path))
            except OSError:
                subprocess.Popen(["explorer", str(path)])
            return True
        return False

    def _open_client_mods_folder(self) -> None:
        if not self._open_folder(self.app.paths.client_mods):
            self.app._server_tab._set_result("Client mods folder is not configured.", level="warning")

    def _open_local_server_mods_folder(self) -> None:
        if not self._open_folder(self.app.paths.server_mods):
            self.app._server_tab._set_result("Local server mods folder is not configured.", level="warning")

    def _open_dedicated_server_mods_folder(self) -> None:
        if not self._open_folder(self.app.paths.dedicated_server_mods):
            self.app._server_tab._set_result("Dedicated server mods folder is not configured.", level="warning")

    def apply_ui_preferences(self) -> None:
        self._title.configure(font=self.app.ui_font("title"))
        self._subtitle.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.detail_wrap)
        for label in self._status_values.values():
            label.configure(font=self.app.ui_font("body"))
        for label in self._setup_values.values():
            label.configure(font=self.app.ui_font("body"), wraplength=self.app.ui_tokens.panel_wrap - 40)
        for label in self._count_values.values():
            label.configure(font=self.app.ui_font("body"))
        for label in self._framework_values.values():
            label.configure(font=self.app.ui_font("body"), wraplength=self.app.ui_tokens.panel_wrap)
        self._framework_note.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.panel_wrap)
        self._compare_target_menu.configure(font=self.app.ui_font("body"), height=self.app.ui_tokens.compact_button_height)
        self._parity_state.configure(font=self.app.ui_font("row_title"))
        self._parity_summary.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.panel_wrap)
        self._drift_label.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.panel_wrap)
        for button in self._action_buttons:
            button.configure(font=self.app.ui_font("body"), height=self.app.ui_tokens.compact_button_height)

    def refresh_view(self) -> None:
        server_tab = self.app._server_tab
        counts = server_tab._dashboard_target_counts()
        source_label = "Hosted Server" if server_tab._source_var.get() == "hosted" else server_tab._active_local_label()
        active_world = server_tab._world_display_name(server_tab._world_config)
        hosted_profile = server_tab._selected_remote_profile()
        hosted_name = hosted_profile.name if hosted_profile is not None else "Not selected"

        client_state = self._status_text(self.app.is_game_running(), configured=True)
        local_state = self._server_status_text("server")
        dedicated_state = self._server_status_text("dedicated_server")
        hosted_state = server_tab._hosted_dashboard_state
        framework_states = self.app.framework_state.all_local_states(self.app.paths)

        self._set_state_label(self._status_values["client"], client_state)
        self._set_state_label(self._status_values["server"], local_state)
        self._set_state_label(self._status_values["dedicated_server"], dedicated_state)
        self._set_state_label(self._status_values["hosted"], hosted_state)
        self._refresh_frameworks(framework_states)

        self._setup_values["source"].configure(text=source_label)
        self._setup_values["world"].configure(text=active_world)
        self._setup_values["profile"].configure(text=hosted_name if server_tab._source_var.get() == "hosted" else "N/A")
        self._setup_values["apply"].configure(text=server_tab._last_apply_text())
        self._setup_values["restart"].configure(text=server_tab._last_restart_text())
        self._setup_values["backup"].configure(text=server_tab._last_backup_text())

        compare_state, compare_summary = server_tab.dashboard_parity_state()
        drift_warnings = getattr(self.app, "manifest_drift_warnings", lambda: [])()
        state_text, state_color = {
            "clean": ("Compare looks clean", "#2d8a4e"),
            "review": ("Review recommended", "#e67e22"),
            "not_run": ("No compare run yet", "#95a5a6"),
        }.get(compare_state, ("Review recommended", "#e67e22"))
        if drift_warnings:
            state_text, state_color = "Review recommended", "#e67e22"
        self._parity_state.configure(text=state_text, text_color=state_color)
        self._parity_summary.configure(text=compare_summary)
        if drift_warnings:
            count = len(drift_warnings)
            self._drift_label.configure(text=f"Drift detected: {count} managed mod issue(s). Open Mods or Activity to review.")
        else:
            self._drift_label.configure(text="")
        can_review_sync = (
            server_tab.last_compare_target() == self._dashboard_target_key()
            and server_tab.last_compare_report() is not None
            and server_tab.last_compare_report().review_needed > 0
        )
        self._review_sync_btn.configure(
            state="normal" if can_review_sync else "disabled",
            fg_color="#e67e22" if can_review_sync else "#555555",
            hover_color="#d35400" if can_review_sync else "#666666",
        )
        for key, value in counts.items():
            self._count_values[key].configure(text=str(value))

    def _server_status_text(self, target: str) -> str:
        configured = bool(self.app.paths.server_root if target == "server" else self.app.paths.dedicated_server_root)
        if not configured:
            return "Not configured"
        running = self.app.is_server_process_running()
        if not running:
            return "Configured"
        if self.app.paths.server_root and not self.app.paths.dedicated_server_root and target == "server":
            return "Running"
        if self.app.paths.dedicated_server_root and not self.app.paths.server_root and target == "dedicated_server":
            return "Running"
        active_target = self.app._server_tab._source_var.get()
        if active_target == target:
            return "Running"
        return "Configured"

    def _refresh_frameworks(self, states: dict) -> None:
        self._set_framework_label(
            self._framework_values["ue4ss"],
            self._framework_targets_text(states, "ue4ss_runtime", empty="Missing"),
        )
        self._set_framework_label(
            self._framework_values["rcon"],
            self._framework_targets_text(states, "rcon_mod", empty="Not installed"),
        )
        self._set_framework_label(
            self._framework_values["windrose_plus"],
            self._windrose_plus_text(states),
        )

    @staticmethod
    def _framework_target_names(states: dict, attribute: str) -> list[str]:
        labels = {
            "client": "Client",
            "server": "Local",
            "dedicated_server": "Dedicated",
        }
        return [labels[key] for key, state in states.items() if getattr(state, attribute, False)]

    @classmethod
    def _framework_targets_text(cls, states: dict, attribute: str, *, empty: str) -> str:
        targets = cls._framework_target_names(states, attribute)
        return ", ".join(targets) if targets else empty

    @classmethod
    def _windrose_plus_text(cls, states: dict) -> str:
        active = cls._framework_target_names(states, "windrose_plus")
        files = [
            target
            for target, state in zip(
                ["Client", "Local", "Dedicated"],
                [states.get("client"), states.get("server"), states.get("dedicated_server")],
            )
            if state and state.windrose_plus_package and not state.windrose_plus
        ]
        parts = []
        if active:
            parts.append(f"Active on {', '.join(active)}")
        if files:
            parts.append(f"Files on {', '.join(files)}")
        return " | ".join(parts) if parts else "Not installed"

    @staticmethod
    def _set_framework_label(label: ctk.CTkLabel, value: str) -> None:
        normalized = value.lower()
        if "missing" in normalized or "files on" in normalized:
            color = "#e67e22"
        elif "not installed" in normalized:
            color = "#95a5a6"
        else:
            color = "#2d8a4e"
        label.configure(text=value, text_color=color)

    @staticmethod
    def _status_text(running: bool, *, configured: bool) -> str:
        if not configured:
            return "Not configured"
        return "Running" if running else "Not running"

    @staticmethod
    def _set_state_label(label: ctk.CTkLabel, value: str) -> None:
        normalized = value.lower()
        if "offline" in normalized:
            color = "#c0392b"
        elif "not configured" in normalized or "not running" in normalized:
            color = "#95a5a6"
        elif "running" in normalized or "connected" in normalized:
            color = "#2d8a4e"
        elif "missing" in normalized:
            color = "#e67e22"
        elif normalized == "configured":
            color = "#95a5a6"
        else:
            color = "#e67e22"
        label.configure(text=value, text_color=color)
