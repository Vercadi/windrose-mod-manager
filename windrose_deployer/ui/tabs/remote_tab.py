"""Remote Server tab — SSH/SFTP connection and mod management on a remote server."""
from __future__ import annotations

import logging
import ntpath
import os
import posixpath
import shutil
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Optional

from ...core.archive_handler import open_archive, is_supported_archive

import customtkinter as ctk

try:
    import paramiko
    _PARAMIKO_AVAILABLE = True
except ImportError:
    _PARAMIKO_AVAILABLE = False

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class RemoteTab(ctk.CTkFrame):
    """SSH-based remote server management tab."""

    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self._client: Optional["paramiko.SSHClient"] = None
        self._sftp: Optional["paramiko.SFTPClient"] = None
        self._connected = False
        self._remote_os: str = "linux"  # "linux" or "windows", detected on connect
        self._remote_mods_dir = "/home/windrose/mods"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_connection_panel()
        self._build_main_area()

        if not _PARAMIKO_AVAILABLE:
            self._log_output(
                "[ERROR] paramiko is not installed. "
                "Run: pip install paramiko\n"
            )

    # ================================================================== UI

    def _build_connection_panel(self) -> None:
        """Build the connection form at the top of the tab."""
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        frame.grid_columnconfigure(5, weight=1)

        # ---- Row 0: Host / Port / Username ----
        ctk.CTkLabel(frame, text="Host:").grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=4)
        self._host_var = ctk.StringVar()
        ctk.CTkEntry(frame, textvariable=self._host_var, width=180,
                      placeholder_text="192.168.1.100").grid(
            row=0, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(frame, text="Port:").grid(
            row=0, column=2, sticky="w", padx=(12, 4), pady=4)
        self._port_var = ctk.StringVar(value="22")
        ctk.CTkEntry(frame, textvariable=self._port_var, width=60).grid(
            row=0, column=3, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(frame, text="Username:").grid(
            row=0, column=4, sticky="w", padx=(12, 4), pady=4)
        self._user_var = ctk.StringVar()
        ctk.CTkEntry(frame, textvariable=self._user_var, width=140,
                      placeholder_text="root").grid(
            row=0, column=5, sticky="w", padx=4, pady=4)

        # ---- Row 1: Auth method ----
        self._auth_var = ctk.StringVar(value="password")

        ctk.CTkLabel(frame, text="Auth:").grid(
            row=1, column=0, sticky="w", padx=(8, 4), pady=4)

        auth_frame = ctk.CTkFrame(frame, fg_color="transparent")
        auth_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=4)

        ctk.CTkRadioButton(auth_frame, text="Password",
                           variable=self._auth_var, value="password",
                           command=self._on_auth_toggle).pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(auth_frame, text="Private Key",
                           variable=self._auth_var, value="key",
                           command=self._on_auth_toggle).pack(side="left")

        # Password field
        self._pw_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._pw_frame.grid(row=1, column=3, columnspan=3, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(self._pw_frame, text="Password:").pack(side="left", padx=(0, 4))
        self._password_var = ctk.StringVar()
        self._pw_entry = ctk.CTkEntry(self._pw_frame, textvariable=self._password_var,
                                       width=180, show="*")
        self._pw_entry.pack(side="left")

        # Key file fields (hidden initially)
        self._key_frame = ctk.CTkFrame(frame, fg_color="transparent")
        ctk.CTkLabel(self._key_frame, text="Key:").pack(side="left", padx=(0, 4))
        self._key_path_var = ctk.StringVar()
        ctk.CTkEntry(self._key_frame, textvariable=self._key_path_var,
                      width=180, state="readonly").pack(side="left", padx=(0, 4))
        ctk.CTkButton(self._key_frame, text="Browse", width=70,
                       command=self._on_browse_key).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self._key_frame, text="Passphrase:").pack(side="left", padx=(0, 4))
        self._passphrase_var = ctk.StringVar()
        ctk.CTkEntry(self._key_frame, textvariable=self._passphrase_var,
                      width=120, show="*").pack(side="left")

        # ---- Row 2: Mods dir + Connect button + Status ----
        ctk.CTkLabel(frame, text="Mods Dir:").grid(
            row=2, column=0, sticky="w", padx=(8, 4), pady=4)
        self._mods_dir_var = ctk.StringVar(value=self._remote_mods_dir)
        ctk.CTkEntry(frame, textvariable=self._mods_dir_var, width=260,
                      placeholder_text="/home/windrose/mods").grid(
            row=2, column=1, columnspan=3, sticky="w", padx=4, pady=4)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=4, columnspan=2, sticky="w", padx=4, pady=4)

        self._connect_btn = ctk.CTkButton(
            btn_frame, text="Connect", width=100,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_connect,
        )
        self._connect_btn.pack(side="left", padx=(0, 8))

        self._status_label = ctk.CTkLabel(
            btn_frame, text="Disconnected",
            text_color="#c0392b", font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._status_label.pack(side="left")

    def _build_main_area(self) -> None:
        """Build the actions + console area below the connection form."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self._build_action_buttons(main)
        self._build_console(main)

    def _build_action_buttons(self, parent) -> None:
        """Predefined action buttons for common server mod management tasks."""
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(frame, text="Quick Actions",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            side="left", padx=8, pady=6)

        btn_defs = [
            ("List Mods", self._action_list_mods, "#2980b9", "#2471a3"),
            ("Server Status", self._action_server_status, "#2980b9", "#2471a3"),
            ("Restart Server", self._action_restart_server, "#e67e22", "#c96b17"),
            ("Upload Mod", self._action_upload_mod, "#2d8a4e", "#236b3d"),
            ("Download Mod List", self._action_download_mod_list, "#555555", "#666666"),
        ]

        for text, cmd, fg, hover in btn_defs:
            ctk.CTkButton(frame, text=text, width=120,
                          fg_color=fg, hover_color=hover,
                          command=cmd).pack(side="left", padx=4, pady=6)

    def _build_console(self, parent) -> None:
        """Build the scrollable output area and command input."""
        console_frame = ctk.CTkFrame(parent)
        console_frame.grid(row=1, column=0, sticky="nsew")
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(0, weight=1)

        # Output area
        self._output = ctk.CTkTextbox(
            console_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled",
            wrap="word",
        )
        self._output.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 0))

        # Command input row
        input_frame = ctk.CTkFrame(console_frame, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        input_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(input_frame, text="$", font=ctk.CTkFont(
            family="Consolas", size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(4, 0))

        self._cmd_var = ctk.StringVar()
        self._cmd_entry = ctk.CTkEntry(
            input_frame, textvariable=self._cmd_var,
            font=ctk.CTkFont(family="Consolas", size=12),
            placeholder_text="Type a command and press Enter...",
        )
        self._cmd_entry.grid(row=0, column=0, sticky="ew", padx=(20, 4))
        self._cmd_entry.bind("<Return>", self._on_cmd_enter)

        self._run_btn = ctk.CTkButton(
            input_frame, text="Run", width=60,
            command=self._on_run_cmd,
        )
        self._run_btn.grid(row=0, column=1, padx=(0, 4))

        self._clear_btn = ctk.CTkButton(
            input_frame, text="Clear", width=60,
            fg_color="#555555", hover_color="#666666",
            command=self._clear_output,
        )
        self._clear_btn.grid(row=0, column=2, padx=(0, 4))

    # ================================================================== Auth toggle

    def _on_auth_toggle(self) -> None:
        if self._auth_var.get() == "password":
            self._key_frame.grid_forget()
            self._pw_frame.grid(row=1, column=3, columnspan=3,
                                sticky="w", padx=4, pady=4)
        else:
            self._pw_frame.grid_forget()
            self._key_frame.grid(row=1, column=3, columnspan=3,
                                 sticky="w", padx=4, pady=4)

    def _on_browse_key(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Private Key File",
            filetypes=[("Key Files", "*.pem *.key *.ppk"), ("All Files", "*.*")],
        )
        if path:
            self._key_path_var.set(path)

    # ================================================================== Connection

    def _on_connect(self) -> None:
        if self._connected:
            self._disconnect()
            return
        self._connect()

    def _connect(self) -> None:
        if not _PARAMIKO_AVAILABLE:
            messagebox.showerror(
                "Missing Dependency",
                "paramiko is not installed.\nRun: pip install paramiko",
            )
            return

        host = self._host_var.get().strip()
        port_str = self._port_var.get().strip()
        username = self._user_var.get().strip()

        if not host:
            messagebox.showwarning("Input Required", "Please enter a host address.")
            return
        if not username:
            messagebox.showwarning("Input Required", "Please enter a username.")
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showwarning("Invalid Port", "Port must be a number.")
            return

        self._remote_mods_dir = self._mods_dir_var.get().strip() or "/home/windrose/mods"

        self._connect_btn.configure(state="disabled", text="Connecting...")
        self._status_label.configure(text="Connecting...", text_color="#e67e22")

        def _do_connect():
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                if self._auth_var.get() == "password":
                    password = self._password_var.get()
                    client.connect(host, port=port, username=username,
                                   password=password, timeout=10)
                else:
                    key_path = self._key_path_var.get().strip()
                    if not key_path or not os.path.isfile(key_path):
                        raise FileNotFoundError(
                            f"Private key file not found: {key_path}")
                    passphrase = self._passphrase_var.get() or None
                    pkey = paramiko.RSAKey.from_private_key_file(
                        key_path, password=passphrase)
                    client.connect(host, port=port, username=username,
                                   pkey=pkey, timeout=10)

                sftp = client.open_sftp()
                self._client = client
                self._sftp = sftp
                self._connected = True

                # Detect remote OS: uname succeeds on Linux, fails on Windows
                try:
                    _, uname_out, _ = client.exec_command("uname", timeout=10)
                    uname_exit = uname_out.channel.recv_exit_status()
                    if uname_exit == 0:
                        self._remote_os = "linux"
                    else:
                        self._remote_os = "windows"
                except Exception:
                    self._remote_os = "windows"

                detected_os = self._remote_os
                self.after(0, lambda: self._on_connect_success(host, detected_os))
                log.info("SSH connected to %s@%s:%d (remote OS: %s)",
                         username, host, port, self._remote_os)

            except Exception as exc:
                self.after(0, lambda e=exc: self._on_connect_error(e))
                log.error("SSH connection failed: %s", exc)

        threading.Thread(target=_do_connect, daemon=True).start()

    def _on_connect_success(self, host: str, remote_os: str = "linux") -> None:
        self._connect_btn.configure(state="normal", text="Disconnect",
                                     fg_color="#c0392b", hover_color="#962d22")
        self._status_label.configure(text=f"Connected to {host}",
                                      text_color="#2d8a4e")
        self._log_output(f"[+] Connected to {host} (detected OS: {remote_os})\n")

    def _on_connect_error(self, exc: Exception) -> None:
        self._connect_btn.configure(state="normal", text="Connect",
                                     fg_color="#2d8a4e", hover_color="#236b3d")
        self._status_label.configure(text="Connection failed", text_color="#c0392b")
        self._log_output(f"[ERROR] Connection failed: {exc}\n")
        messagebox.showerror("Connection Failed", str(exc))

    def _disconnect(self) -> None:
        try:
            if self._sftp:
                self._sftp.close()
        except Exception:
            pass
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass

        self._sftp = None
        self._client = None
        self._connected = False
        self._remote_os = "linux"

        self._connect_btn.configure(text="Connect",
                                     fg_color="#2d8a4e", hover_color="#236b3d")
        self._status_label.configure(text="Disconnected", text_color="#c0392b")
        self._log_output("[~] Disconnected\n")
        log.info("SSH disconnected")

    def close(self) -> None:
        """Clean up SSH resources. Called when the app is closing."""
        self._disconnect()

    # ================================================================== Command execution

    def _exec_command(self, cmd: str, callback=None) -> None:
        """Execute a command on the remote server in a background thread."""
        if not self._connected or not self._client:
            self._log_output("[ERROR] Not connected to a server.\n")
            return

        def _run():
            try:
                stdin, stdout, stderr = self._client.exec_command(cmd, timeout=30)
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                exit_code = stdout.channel.recv_exit_status()

                def _show():
                    self._log_output(f"$ {cmd}\n")
                    if out:
                        self._log_output(out)
                        if not out.endswith("\n"):
                            self._log_output("\n")
                    if err:
                        self._log_output(f"[stderr] {err}")
                        if not err.endswith("\n"):
                            self._log_output("\n")
                    if exit_code != 0:
                        self._log_output(f"[exit code: {exit_code}]\n")
                    if callback:
                        callback(out, err, exit_code)
                self.after(0, _show)

            except Exception as exc:
                self.after(0, lambda: self._log_output(
                    f"$ {cmd}\n[ERROR] {exc}\n"))
                log.error("Remote command failed: %s", exc)

        threading.Thread(target=_run, daemon=True).start()

    def _on_cmd_enter(self, event=None) -> None:
        self._on_run_cmd()

    def _on_run_cmd(self) -> None:
        cmd = self._cmd_var.get().strip()
        if not cmd:
            return
        self._cmd_var.set("")
        self._exec_command(cmd)

    # ================================================================== Path helpers

    def _build_remote_path(self, directory: str, filename: str) -> str:
        """Build a normalized remote path from a directory and filename.

        Handles cross-OS path issues: strips trailing separators and uses
        the correct path joining for the remote OS so that Paramiko SFTP
        doesn't choke on Windows-style backslashes when the remote is Linux.
        """
        if self._remote_os == "windows":
            # Keep native Windows separators; strip trailing slash/backslash
            directory = directory.rstrip("/\\")
            return ntpath.join(directory, filename)
        else:
            # Linux remote: convert any backslashes to forward slashes
            directory = directory.replace("\\", "/").rstrip("/")
            return posixpath.join(directory, filename)

    # ================================================================== Archive extraction + SFTP upload

    def _ensure_remote_dir(self, remote_dir: str) -> None:
        """Create a remote directory (and parents) via SFTP, ignoring 'already exists'."""
        if self._remote_os == "windows":
            parts = remote_dir.replace("\\", "/").split("/")
        else:
            parts = remote_dir.split("/")

        # Build up each ancestor path and try to mkdir
        current = ""
        for part in parts:
            if not part:
                # preserve leading slash for absolute paths
                current = "/"
                continue
            current = posixpath.join(current, part) if current else part
            if not current or current == "/":
                continue
            try:
                self._sftp.mkdir(current)
            except IOError:
                # Directory already exists — that's fine
                pass

    def _extract_and_upload(self, local_path: str) -> tuple[bool, str]:
        """Extract an archive to a temp dir and upload all files via SFTP.

        Returns (success, message).  Runs on a background thread — callers
        must schedule UI updates back to the main thread.
        """
        archive_path = Path(local_path)
        mods_dir = self._remote_mods_dir

        # If the file is not a supported archive, fall back to a plain single-file upload
        if not is_supported_archive(archive_path):
            remote_path = self._build_remote_path(mods_dir, archive_path.name)
            self.after(0, lambda: self._log_output(
                f"[~] Uploading {archive_path.name} → {remote_path}\n"))
            self._sftp.put(local_path, remote_path)
            return True, f"Upload complete: {archive_path.name}"

        tmp_dir = tempfile.mkdtemp(prefix="wmd_remote_")
        try:
            # Extract the archive
            self.after(0, lambda: self._log_output(
                f"[~] Extracting {archive_path.name}...\n"))

            reader = open_archive(archive_path)
            try:
                entries = reader.list_entries()
                for entry in entries:
                    if entry.is_dir:
                        continue
                    data = reader.read_file(entry.filename)
                    dest = Path(tmp_dir) / entry.filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            finally:
                reader.close()

            # Walk the extracted temp dir and upload every file
            extracted_root = Path(tmp_dir)
            uploaded = 0
            for file_path in sorted(extracted_root.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(extracted_root)
                # Convert to forward-slash relative path
                rel_posix = rel.as_posix()
                remote_path = self._build_remote_path(mods_dir, rel_posix)

                # Ensure the remote parent directory exists
                remote_parent = posixpath.dirname(remote_path) if self._remote_os != "windows" else ntpath.dirname(remote_path)
                if remote_parent and remote_parent != mods_dir:
                    self._ensure_remote_dir(remote_parent)

                self.after(0, lambda rp=rel_posix, rmt=remote_path: self._log_output(
                    f"[~] Uploading {rp} → {rmt}\n"))
                self._sftp.put(str(file_path), remote_path)
                uploaded += 1

            return True, f"Upload complete: {uploaded} file(s) from {archive_path.name}"

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ================================================================== Action handlers

    def _action_list_mods(self) -> None:
        mods_dir = self._remote_mods_dir
        if self._remote_os == "windows":
            self._exec_command(f'dir "{mods_dir}"')
        else:
            self._exec_command(f"ls -lh {mods_dir} 2>/dev/null || echo '(directory not found)'")

    def _action_server_status(self) -> None:
        if self._remote_os == "windows":
            self._exec_command(
                'tasklist /FI "IMAGENAME eq windrose*" /FI "IMAGENAME eq gameserver*"'
            )
        else:
            self._exec_command(
                "ps aux | grep -i '[w]indrose\\|[g]ameserver' || echo 'No server process found'"
            )

    def _action_restart_server(self) -> None:
        if not self._connected:
            self._log_output("[ERROR] Not connected to a server.\n")
            return
        confirm = messagebox.askyesno(
            "Restart Server",
            "Are you sure you want to restart the game server?\n"
            "This will interrupt all connected players.",
        )
        if not confirm:
            return
        self._log_output("[~] Attempting server restart...\n")
        if self._remote_os == "windows":
            self._exec_command(
                'if exist restart_server.bat (call restart_server.bat) '
                'else (sc stop WindroseServer & sc start WindroseServer)'
            )
        else:
            self._exec_command(
                "if [ -f ./restart_server.sh ]; then bash ./restart_server.sh; "
                "elif systemctl is-active --quiet windrose-server 2>/dev/null; then "
                "sudo systemctl restart windrose-server; "
                "else echo 'No restart script or systemd service found. "
                "Use the console to restart manually.'; fi"
            )

    def _action_upload_mod(self) -> None:
        if not self._connected or not self._sftp:
            self._log_output("[ERROR] Not connected to a server.\n")
            return

        local_path = filedialog.askopenfilename(
            title="Select Mod File to Upload",
            filetypes=[
                ("Archive Files", "*.zip *.7z *.rar *.pak"),
                ("All Files", "*.*"),
            ],
        )
        if not local_path:
            return

        def _do_upload():
            try:
                success, msg = self._extract_and_upload(local_path)
                if success:
                    self.after(0, lambda: self._log_output(f"[+] {msg}\n"))
                    log.info("Upload mod: %s", msg)
                else:
                    self.after(0, lambda: self._log_output(f"[ERROR] {msg}\n"))
                    log.error("Upload mod failed: %s", msg)
            except Exception as exc:
                self.after(0, lambda: self._log_output(
                    f"[ERROR] Upload failed: {exc}\n"))
                log.error("SFTP upload failed: %s", exc)

        threading.Thread(target=_do_upload, daemon=True).start()

    def _action_download_mod_list(self) -> None:
        mods_dir = self._remote_mods_dir

        def _on_result(out, err, exit_code):
            if exit_code != 0 or not out.strip():
                return
            save_path = filedialog.asksaveasfilename(
                title="Save Mod List",
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                initialfile="server_mods.txt",
            )
            if save_path:
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(out)
                    self._log_output(f"[+] Mod list saved to {save_path}\n")
                except Exception as exc:
                    self._log_output(f"[ERROR] Failed to save: {exc}\n")

        if self._remote_os == "windows":
            self._exec_command(f'dir /B "{mods_dir}"', callback=_on_result)
        else:
            self._exec_command(
                f"ls -1 {mods_dir} 2>/dev/null || echo '(directory not found)'",
                callback=_on_result,
            )

    # ================================================================== Public API (for cross-tab use)

    def is_connected(self) -> bool:
        """Return True if an SSH session is currently active."""
        return self._connected and self._sftp is not None

    def upload_file(self, local_path: str, callback=None) -> None:
        """Upload a local file to the configured remote Mods Dir via SFTP.

        If the file is a supported archive (.zip, .7z, .rar), it is extracted
        first and the individual mod files are uploaded, preserving directory
        structure.  Non-archive files (e.g. .pak) are uploaded directly.

        Args:
            local_path: Absolute path to the local file to upload.
            callback: Optional callable(success: bool, message: str) invoked
                      on the main thread when the upload finishes.
        """
        if not self.is_connected():
            if callback:
                self.after(0, lambda: callback(False, "Not connected to a remote server."))
            return

        def _do_upload():
            try:
                success, msg = self._extract_and_upload(local_path)
                self.after(0, lambda: self._log_output(
                    f"[+] {msg}\n" if success else f"[ERROR] {msg}\n"))
                log.info("upload_file: %s", msg)
                if callback:
                    self.after(0, lambda: callback(success, msg))
            except Exception as exc:
                msg = f"Upload failed: {exc}"
                self.after(0, lambda: self._log_output(f"[ERROR] {msg}\n"))
                log.error("SFTP upload failed: %s", exc)
                if callback:
                    self.after(0, lambda: callback(False, msg))

        threading.Thread(target=_do_upload, daemon=True).start()

    # ================================================================== Console helpers

    def _log_output(self, text: str) -> None:
        """Append text to the console output area."""
        self._output.configure(state="normal")
        self._output.insert("end", text)
        self._output.see("end")
        self._output.configure(state="disabled")

    def _clear_output(self) -> None:
        self._output.configure(state="normal")
        self._output.delete("1.0", "end")
        self._output.configure(state="disabled")
