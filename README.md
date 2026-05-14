# Windrose Mod Manager

[![Latest release](https://img.shields.io/github/v/release/Vercadi/windrose-mod-manager)](https://github.com/Vercadi/windrose-mod-manager/releases)
[![GitHub downloads](https://img.shields.io/github/downloads/Vercadi/windrose-mod-manager/total?label=GitHub%20downloads)](https://github.com/Vercadi/windrose-mod-manager/releases)
[![License](https://img.shields.io/github/license/Vercadi/windrose-mod-manager)](LICENSE)
[![Nexus Mods](https://img.shields.io/badge/Nexus%20Mods-download-orange)](https://www.nexusmods.com/windrose/mods/29)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-support-ff5f5f)](https://ko-fi.com/vercadi)
[![Patreon](https://img.shields.io/badge/Patreon-support-f96854)](https://www.patreon.com/cw/Vercadi)

<p align="center">
  <img src="assets/banner.png" alt="Windrose Mod Manager banner">
</p>

A Windows desktop app for modding **Windrose** safely across the client, local server files, the standalone dedicated server, and hosted servers with SFTP or FTP file access.

This is not a generic mod organizer. It is a Windrose-specific client and server cockpit for managed installs, backups, recovery, hosted upload review, and server/world settings.

## Media

This README reuses the tracked banner at `assets/banner.png` and app icon at `assets/icon_256.png`. Additional screenshots and file-page images are hosted on the [Nexus Mods page](https://www.nexusmods.com/windrose/mods/29).

## Download

- Packaged app: [Nexus Mods](https://www.nexusmods.com/windrose/mods/29)
- Packaged app and checksums: [GitHub Releases](https://github.com/Vercadi/windrose-mod-manager/releases)
- Source repository: [GitHub](https://github.com/Vercadi/windrose-mod-manager)
- Latest release notes: [docs/releases/latest_release_notes.md](docs/releases/latest_release_notes.md)

## Installation

1. Download the latest release from Nexus Mods or GitHub Releases.
2. Extract the release archive anywhere on your PC.
3. Run `Windrose Mod Manager.exe`.
4. Let the app auto-detect Windrose paths, or set them manually in Settings.

## Update

Download the latest release archive and replace the previous extracted app folder. The app also checks GitHub Releases and shows an in-app update notice when a newer version is available.

## Usage

Windrose Mod Manager is built around three practical jobs:

- manage archives and applied mods from one Library workspace
- edit local or hosted server settings safely
- recover from mistakes with backups, restore, repair, and undo-friendly history

Main workflows:

- Import or drag in `.zip`, `.7z`, `.rar`, pak-only, loose-file, mixed, or multi-variant archives.
- Review archive contents before install.
- Install to client, local server, client plus local server, client plus dedicated server, or hosted server.
- Use Dashboard to compare client/server/hosted state and review sync actions before applying.
- Use Server for local, dedicated, and hosted settings.
- Use Activity & Backups to restore previous versions or inspect recovery history.

## Requirements

- Windows 10/11
- Windrose installed locally for client workflows
- Windrose Dedicated Server installed through Steam for dedicated server workflows
- SFTP or FTP file access for hosted server workflows

Hosted profile setup usually needs host, port, username, password or SSH private key, and the server folder path on the remote machine.

## Compatibility

Supported archive formats:

| Format | Notes |
|---|---|
| `.zip` | Full support |
| `.7z` | Requires `py7zr`, included in requirements |
| `.rar` | Requires `rarfile` plus UnRAR on PATH |

Supported mod/archive types:

| Type | Description |
|---|---|
| Pak-only | Archives containing `.pak` files, optionally with `.utoc` / `.ucas` companions |
| Loose-file | Archives with folder overlays for the Windrose install |
| Mixed | Archives containing both pak files and loose files |
| Multi-variant | Archives with multiple alternative pak choices; the user selects one |

If your host does not expose SFTP or FTP file access, the hosted workflow in the app will not work.

Known limitations:

- no automatic per-mod update tracking
- conflict detection is still warning-only; there is no load-order system
- hosted support requires working SFTP/SSH or FTP file access
- Windows only
- no Nexus API integration or automatic Nexus downloads
- no save editing, pak creation, or UE asset unpacking

## Bug Reports / Support

Open issues on [GitHub Issues](https://github.com/Vercadi/windrose-mod-manager/issues) and include the app version, what target you were using, the archive type, the action you tried, and relevant logs from the technical log panel.

Support continued work through [Ko-fi](https://ko-fi.com/vercadi) or [Patreon](https://www.patreon.com/cw/Vercadi).

## Privacy / Safety

The app has no analytics, advertising, or telemetry. See [PRIVACY_POLICY.md](PRIVACY_POLICY.md).

Safety model:

- installs and hosted uploads use review steps before writes
- uninstall restores overwritten original files from backup when available
- backups, restore, repair, and activity history are part of the normal workflow
- hosted support requires your explicit SFTP/FTP profile and actions

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

## Repository Layout

```text
windrose-mod-manager/
  app.py
  assets/
  docs/
    planning/
    releases/
  tests/
  windrose_deployer/
    core/
    models/
    ui/
    utils/
```

App data locations:

| Data | Source mode | Packaged exe |
|---|---|---|
| App state, settings, archive library, remote profiles | `./data/` | `%LOCALAPPDATA%/WindroseModDeployer/data/` |
| Backups | `./backups/` | `%LOCALAPPDATA%/WindroseModDeployer/backups/` |
| Logs | `./data/deployer.log` | `%LOCALAPPDATA%/WindroseModDeployer/data/deployer.log` |

Planning notes, implementation briefs, audit notes, release text, and Nexus release drafts live under [docs/](docs/) so the repository root stays focused.

## Building The Executable

```bash
python -m PyInstaller windrose_mod_deployer.spec --noconfirm
```

The packaged app is written to `dist/Windrose Mod Manager/`.

## License

MIT License. See [LICENSE](LICENSE).
