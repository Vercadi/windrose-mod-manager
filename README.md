# Windrose Mod Deployer

A Windows desktop application for managing mods for **Windrose** — supporting both the client game and the dedicated server.

## What It Does

- **Detects** Windrose client, dedicated server, and local config/save paths automatically
- **Analyzes** mod archives (zip) before install — classifies as pak-only, loose-file, mixed, or multi-variant
- **Deploys** mods to client, server, or both with proper file placement
- **Backs up** every file before overwriting and maintains a full backup history
- **Tracks** all installed files in a manifest so mods can be cleanly uninstalled or disabled
- **Edits** `ServerDescription.json` safely with validation and automatic backups
- **Detects conflicts** between installed mods writing to the same target files
- **Provides** a clean dark-mode desktop UI built with CustomTkinter

## MVP Scope

This is the initial release focused on reliable core workflows:

| Feature | Status |
|---|---|
| Client/server path detection | ✅ |
| Archive analysis (zip) | ✅ |
| Pak-only mod install | ✅ |
| Loose-file mod install | ✅ |
| Mixed mod install | ✅ |
| Multi-variant pak selection | ✅ |
| Install to client/server/both | ✅ |
| Manifest-tracked uninstall | ✅ |
| Mod disable/enable | ✅ |
| Backup & restore | ✅ |
| ServerDescription.json editor | ✅ |
| Conflict warnings | ✅ |
| 7z archive support | ❌ (zip only for MVP) |

## Project Structure

```
windrose-mod-deployer/
  app.py                          # Entry point
  requirements.txt
  README.md
  .gitignore
  windrose_deployer/
    __init__.py
    models/                       # Data classes
      app_paths.py                # Path configuration model
      archive_info.py             # Archive analysis result
      deployment_record.py        # Deployment tracking record
      mod_install.py              # Installed mod state
      server_config.py            # ServerDescription model
    core/                         # Business logic
      discovery.py                # Auto-detect game paths
      validators.py               # Path/config validation
      archive_inspector.py        # Archive content analysis
      target_resolver.py          # Resolve install targets
      deployment_planner.py       # Plan install operations
      installer.py                # Execute installs/uninstalls
      backup_manager.py           # Backup/restore operations
      manifest_store.py           # Persistent mod manifest
      conflict_detector.py        # File conflict detection
      server_config_service.py    # ServerDescription.json I/O
      logging_service.py          # App-wide logging
    ui/                           # CustomTkinter UI
      app_window.py               # Main window
      widgets/
        status_panel.py           # Status/log panel
        file_preview.py           # Archive file tree preview
      tabs/
        mods_tab.py               # Add & install mods
        installed_tab.py          # Manage installed mods
        server_tab.py             # Server config editor
        backups_tab.py            # Backup history & restore
        settings_tab.py           # Path configuration
    utils/                        # Shared helpers
      filesystem.py               # Safe file operations
      hashing.py                  # File hashing
      json_io.py                  # JSON read/write helpers
      naming.py                   # Name/path utilities
  data/
    .gitkeep
  backups/
    .gitkeep
```

## How to Run

### Prerequisites

- Python 3.12+
- Windows 10/11

### Setup

```bash
# Clone / navigate to the project
cd "H:\Moddding\Windrose\Windrose Mod Deployer"

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

## Supported Mod Types

| Type | Description |
|---|---|
| **Pak-only** | Archives containing `.pak` files (optionally with `.utoc`/`.ucas`) |
| **Loose-file** | Archives with folder structures to overlay onto the game directory |
| **Mixed** | Archives containing both pak files and loose files |
| **Multi-variant** | Archives with multiple alternative pak files — user selects which to install |

## Known Limitations

- Only `.zip` archives supported (no `.7z` or `.rar`)
- No drag-and-drop archive import yet
- No automatic mod updates or version tracking
- Conflict detection is warning-only — no load-order management
- World editing (`WorldDescription.json`) not implemented
- No networked features (no Nexus API, no auto-downloads)

## Future Roadmap

- 7z archive support
- Drag-and-drop mod import
- WorldDescription.json editor for server worlds
- Mod profiles (save/load sets of enabled mods)
- PyInstaller packaging for standalone `.exe`
- Mod version tracking and update detection
- Search/filter in installed mods list
