# Windrose Mod Manager

A Windows desktop app for modding **Windrose** safely across the client, the local dedicated server, and hosted servers with SFTP or FTP file access.

**[Nexus Mods Page](https://www.nexusmods.com/windrose/mods/29)** | **[GitHub](https://github.com/Vercadi/windrose-mod-manager)**

## What It Does

Windrose Mod Manager is built around three practical jobs:

- manage archives and applied mods from one Library workspace
- edit local or hosted server settings safely
- recover from mistakes with backups, restore, repair, and undo-friendly history

This is not a generic mod organizer. It is a Windrose-specific client + server cockpit.

## Features

- Auto-detects Windrose client, standalone dedicated server installs, config, and server save paths
- Analyzes archives (`.zip`, `.7z`, `.rar`) before install
- Supports pak-only, loose-file, mixed, and multi-variant archives
- Unified **Library** workspace with:
  - tracked archives
  - applied mods grouped by target
  - right-click install, reinstall, uninstall, and repair actions
  - hosted live inventory view
- Installs mods to:
  - client
  - local server
  - both
  - hosted server over SFTP or FTP
- Variant chooser for archives with multiple pak options
- Drag-and-drop and multi-file archive import
- Repair / verify support for managed installs
- Safe uninstall that restores overwritten original files from backup
- **Server** cockpit for:
  - local server settings
  - hosted server settings
  - world settings
  - client/server sync review
  - optional hosted restart command
- Hosted profile setup with:
  - saved profiles
  - connection test
  - server-folder based path auto-detect
  - support for `.` when SFTP opens directly inside the server folder
  - password or SSH private-key auth
- **Recovery Center** with:
  - action-based recovery timeline
  - restore previous version
  - undo for supported actions
  - raw backup browser
  - backup retention cleanup
- Launch buttons for Windrose and the local dedicated server
- GitHub release update notifications with in-app download link
- Technical log panel for troubleshooting when needed

## Download

Grab the latest release from [Nexus Mods](https://www.nexusmods.com/windrose/mods/29) or [GitHub Releases](https://github.com/Vercadi/windrose-mod-manager/releases).

## Hosted Server Notes

Hosted support is built for providers that give you **SFTP or FTP access** to the server files.

You will usually need:

- host
- port
- username
- password or private key
- the server folder path on the remote machine

If your host does not expose SFTP or FTP file access, the hosted workflow in the app will not work.

For local server management, the app supports the standalone Steam **Windrose Dedicated Server** install and uses its `R5` folder for settings and world saves.

## Running From Source

### Prerequisites

- Python 3.12+
- Windows 10/11

### Setup

```bash
pip install -r requirements.txt
python app.py
```

### Run Tests

```bash
python -m pytest -q
```

## Supported Mod Types

| Type | Description |
|---|---|
| **Pak-only** | Archives containing `.pak` files, optionally with `.utoc` / `.ucas` companions |
| **Loose-file** | Archives with folder overlays for the Windrose install |
| **Mixed** | Archives containing both pak files and loose files |
| **Multi-variant** | Archives with multiple alternative pak choices; the user selects one |

## Supported Archive Formats

| Format | Notes |
|---|---|
| `.zip` | Full support |
| `.7z` | Requires `py7zr` (included in requirements) |
| `.rar` | Requires `rarfile` plus UnRAR on PATH |

**RAR note:** the `rarfile` Python package requires the [UnRAR](https://www.rarlab.com/rar_add.htm) command-line tool to be installed and available on your system PATH. Without it, `.rar` archives will fail to open.

## Project Structure

```text
windrose-mod-manager/
  app.py
  requirements.txt
  windrose_deployer/
    __init__.py
    models/
      app_paths.py
      archive_info.py
      deployment_record.py
      mod_install.py
      remote_profile.py
      server_config.py
      world_config.py
    core/
      archive_handler.py
      archive_inspector.py
      backup_manager.py
      conflict_detector.py
      deployment_planner.py
      discovery.py
      installer.py
      integrity_service.py
      logging_service.py
      manifest_store.py
      recovery_service.py
      remote_config_service.py
      remote_deployer.py
      remote_profile_store.py
      remote_provider.py
      server_config_service.py
      server_sync_service.py
      sftp_provider.py
      target_resolver.py
      update_checker.py
      validators.py
      world_config_service.py
    ui/
      app_window.py
      widgets/
        status_panel.py
      tabs/
        about_tab.py
        backups_tab.py
        mods_tab.py
        server_tab.py
        settings_tab.py
    utils/
      filesystem.py
      hashing.py
      json_io.py
      naming.py
  tests/
  assets/
```

## Where Data Lives

| Data | Location (source mode) | Location (packaged exe) |
|---|---|---|
| App state / manifest | `./data/app_state.json` | `%LOCALAPPDATA%/WindroseModDeployer/data/` |
| Settings | `./data/settings.json` | `%LOCALAPPDATA%/WindroseModDeployer/data/` |
| Archive library | `./data/archive_library.json` | `%LOCALAPPDATA%/WindroseModDeployer/data/` |
| Remote profiles | `./data/remote_profiles.json` | `%LOCALAPPDATA%/WindroseModDeployer/data/` |
| Backups | `./backups/` | `%LOCALAPPDATA%/WindroseModDeployer/backups/` |
| Logs | `./data/windrose_deployer.log` | `%LOCALAPPDATA%/WindroseModDeployer/data/` |

## Building The Executable

```bash
python -m PyInstaller windrose_mod_deployer.spec --noconfirm
```

The packaged app is written to `dist/Windrose Mod Manager/`.

When packaged, the app stores its working data under `%LOCALAPPDATA%/WindroseModDeployer/` instead of the repo directory.

## Known Limitations

- No automatic per-mod update tracking
- Conflict detection is still warning-only; there is no load-order system
- Hosted support requires working SFTP/SSH access to the server
- Windows only
- No Nexus API integration or automatic Nexus downloads
- No save editing, pak creation, or UE asset unpacking

## License

MIT License. See [LICENSE](LICENSE) for details.

## Author

**Vercadi**
