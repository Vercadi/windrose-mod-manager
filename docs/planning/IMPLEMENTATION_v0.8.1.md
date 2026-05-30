# Windrose Mod Manager v0.8.1 Implementation Plan

## Goal

Make the two most confusing first-run workflows obvious:

- importing mod files from anywhere on the PC
- configuring hosted FTP/SFTP paths, especially Nitrado-style hosted servers

This is a patch release. Keep it small, testable, and focused on discoverability and path safety. Do not start the broader config center redesign in this release.

## User Feedback Driving This Patch

### Import Confusion

A user could not find where to drag/drop mod files. They had the game on `E:` and mods on a separate `D:` drive, used auto-detect, and thought the manager would not let them change where mod files are loaded from.

Current state:

- Mods can already be imported from any drive through the `Add` button.
- Drag/drop is registered on the inactive archive pane, inactive archive list, and hint label when `tkdnd` is available.
- Normal archive imports are copied into the manager-owned archive library, so the original download location does not need to stay on the same drive.
- The UI does not make any of this obvious.
- Dropping a folder currently skips it as unsupported instead of scanning it for supported mod files.

### Hosted Nitrado Path Confusion

A user could connect to a Nitrado server but did not know what to enter for `Server Folder`.

Current state:

- The app says the server folder is the remote folder that contains `R5`.
- For an FTP file browser showing `windrose/R5/...`, that means `Server Folder = windrose`.
- The app's normal hosted pak path derives to `windrose/R5/Content/Paks/~mods`.
- Nitrado-facing guidance from users and Nitrado's guide points toward a built-in `windrose/Mods` folder for mod uploads.
- Other providers still document the normal Unreal pak path, for example GPORTAL uses `./R5/Content/Paks/~Mods`.
- UE4SS server-side mods commonly belong under `R5/Binaries/Win64/ue4ss/Mods`.

Provider references:

- Nitrado guide: `https://server.nitrado.net/en-GB/guides/how-to-install-windrose-mods`
- GPORTAL guide: `https://www.g-portal.com/wiki/en/windrose-how-do-i-add-mods-to-my-gportal-server/`
- WinterNode UE4SS guide: `https://winternode.com/help/games/windrose/setup/how-to-add-mods`

## Release Scope

### In Scope

- clearer Mods import UI
- obvious drop zone and fallback text
- folder import/drop scanning
- explicit wording that mod downloads can live on any drive
- hosted setup wording that uses `Server Folder` consistently
- Nitrado FTP preset and path helper
- remote path suggestions based on top-level FTP/SFTP listing when safe
- focused tests for import discovery and hosted path resolution
- Nexus sticky/comment response draft

### Out Of Scope

- new mod provider API integration
- Thunderstore/Gale integration
- generic config center
- remote delete/cleanup redesign
- hosted remote backup system
- changing default hosted path behavior for every provider
- automatic download from Nexus/CurseForge/Thunderstore

## Design Principles

- Do not make users understand the archive library before importing a mod.
- `Add Mod Files...` should be as obvious as drag/drop.
- Drag/drop is a convenience, not a requirement.
- Hosted setup should show examples from what users actually see in FTP clients.
- Nitrado support should be a preset/path mode, not a hard-coded global default.
- The app should prefer preview and path explanation over hidden magic.

## Slice 1 - Import And Drag/Drop Clarity

### UI Changes

Rename the inactive archive panel actions:

- `Add` -> `Add Mod Files...`
- keep `Refresh`
- add `Add Folder...` if it fits without crowding; otherwise place it in a small secondary import menu or context menu

Replace the inactive archive hint with shorter, more direct text:

```text
Drop mod archives here, or click Add Mod Files. Downloads can be on any drive.
```

Empty state should look like a drop zone, not a plain sentence:

```text
Drop mod archives here
or click Add Mod Files...

Supported: .zip, .7z, .rar, .pak, .utoc, .ucas
Files can be on D:, E:, Downloads, or any folder you choose.
```

If drag/drop is unavailable:

```text
Drag/drop is unavailable on this system. Use Add Mod Files instead.
```

When a folder is dropped or selected:

- scan only the selected folder by default, not the entire drive
- include supported files directly inside the folder
- include one directory level below if that avoids missing common extracted mod folders
- do not recursively scan deep folder trees by default
- if more than a safe limit is found, ask for confirmation before importing

Suggested safe limits:

- warn above 50 supported files
- hard-stop or require explicit confirmation above 250 supported files

### Import Behavior

Add helper:

```python
collect_importable_sources(paths: list[Path]) -> ImportCollection
```

It should return:

- archive files: `.zip`, `.7z`, `.rar`
- loose Unreal asset files: `.pak`, `.utoc`, `.ucas`
- skipped files with reason
- scanned folders
- warnings

Rules:

- direct files behave exactly as today
- folder import should group loose pak companions through the existing pak bundle importer
- unsupported files should be summarized, not spammed one by one after the first few
- duplicate archive detection should keep current hash reuse behavior
- manager-owned archive copy behavior must not regress

### Tests

Add focused tests for:

- importing archive from a different drive-style path, using `tmp_path` as the source
- dropped folder containing `.zip` imports the archive
- dropped folder containing `.pak/.utoc/.ucas` creates a pak bundle
- unsupported folder contents produce a concise warning
- drag/drop unavailable text is selected when `_dnd_enabled` is false
- manager-owned archive copies still land in app data for normal archives

## Slice 2 - Hosted Setup Wording And Provider Presets

### Wording Changes

Use `Server Folder` consistently in the visible UI. Avoid mixing `Remote Root` and `Server Folder` in user-facing labels.

Replace abstract guidance with concrete examples:

```text
Server Folder is the folder your FTP/SFTP login sees as the Windrose server root.

Examples:
- If the file browser shows windrose/R5, use Server Folder = windrose.
- If it opens directly to R5, use Server Folder = .
- If your provider has a separate Mods folder, use a provider preset or fill Mods Folder Override.
```

Resolved path preview should explain what each row means:

- `Mods upload folder`
- `Server settings file`
- `World saves folder`

### Provider Shortcuts

Add a `Nitrado FTP` shortcut.

Preset values:

- protocol: `ftp`
- port: `21`
- server folder: `windrose` if blank
- mods folder override: `windrose/Mods`
- server settings override: blank by default, because `windrose/R5/ServerDescription.json` is correctly derived from `Server Folder = windrose`
- save root override: blank by default, because `windrose/R5/Saved` is correctly derived from `Server Folder = windrose`

Status text:

```text
Nitrado FTP preset applied. Use FTP Credentials from the Nitrado panel. This uses Server Folder = windrose and uploads pak mods to windrose/Mods.
```

Keep existing generic presets:

- Host Havoc SFTP
- Host Havoc FTP
- Indifferent Broccoli FTP

Do not change the default derived mods folder for generic providers.

### Path Helper

Add optional helper button near hosted setup:

```text
Suggest Paths
```

Behavior:

- connect with current host/protocol/credentials
- list top-level remote entries
- do not write files
- if `windrose` exists and `windrose/R5` exists or likely exists, suggest `Server Folder = windrose`
- if `R5` exists at login root, suggest `Server Folder = .`
- if `windrose/Mods` exists, suggest `Mods Folder Override = windrose/Mods`
- if only `R5/Content/Paks` exists, keep normal derived path
- if no safe suggestion is found, show a short diagnostic and keep fields unchanged

This helper can be deferred if the provider listing APIs make it too large for v0.8.1. The Nitrado preset is the minimum viable fix.

### Tests

Add tests for:

- `RemoteProfile(remote_root_dir="windrose").resolved_mods_dir()` still derives `windrose/R5/Content/Paks/~mods`
- Nitrado preset data produces `remote_root_dir="windrose"` and `remote_mods_dir="windrose/Mods"`
- normalized paths handle `windrose`, `/windrose`, `.`, and `windrose/Mods`
- hosted diagnostics include `Server Folder`, `Mods Override`, protocol, host, and port, without password/key contents
- FTP restart command remains disabled/unavailable

## Slice 3 - First-Run And Help Copy

### Welcome Dialog

Current welcome has `Import First Archive`, but the feedback shows users may still search for "library app" or "drop folder".

Update import action text:

- `Import First Archive` -> `Add Mod Files...`

Add one sentence:

```text
Your downloads can be anywhere; the manager will track or copy what it needs.
```

### Help Tab

Add a short section:

```text
Adding mods
- Open Mods.
- Click Add Mod Files, or drop archives into Inactive Mods.
- Downloads can be on any drive.
- For extracted pak files, select or drop the pak/utoc/ucas files together.
```

Add a hosted setup section:

```text
Hosted server paths
- Server Folder is the folder that contains R5.
- If FTP shows windrose/R5, use windrose.
- If FTP opens directly inside the server folder, use .
- For Nitrado FTP, use the Nitrado FTP preset and FTP Credentials.
```

### Nexus Sticky Update Draft

After release, replace or add a sticky:

```text
v0.8.1 improves first-run import and hosted setup clarity.

- Mods tab now has clearer Add Mod Files / drop-zone wording.
- Mod downloads can be imported from any drive or folder.
- Folder drops/imports scan for supported mod files.
- Hosted setup now has clearer Server Folder examples.
- Added Nitrado FTP guidance/preset for users whose FTP browser shows windrose/R5 or windrose/Mods.

For Nitrado: use FTP Credentials from the panel, port 21, and the Nitrado FTP preset. Do not use Query, Game, or RCON ports for FTP.
```

## Slice 4 - Verification And Release

### Required Automated Checks

- `python -m compileall windrose_deployer -q`
- `python -m pytest -q`

### Required Source Smokes

- open Dashboard, Mods, Server, Activity, Settings, Help
- import archive with `Add Mod Files`
- import/drop folder containing supported archive
- import/drop folder containing loose pak companions
- confirm empty inactive mods state shows clear drop/add text
- open hosted setup
- apply Nitrado FTP preset
- verify resolved paths:
  - Server Folder: `windrose`
  - Mods upload folder: `windrose/Mods`
  - Server settings file: `windrose/R5/ServerDescription.json`
  - World saves folder: `windrose/R5/Saved`
- verify generic hosted profile defaults still derive `R5/Content/Paks/~mods`

### Packaged Smoke

Only package after tests pass:

- package exe/zip as `0.8.1`
- smoke-launch packaged exe
- confirm window title and diagnostics report `v0.8.1`
- verify Mods empty state and Hosted Setup can open in packaged build

## Release Criteria

- A new user can understand where to add mod files without reading a sticky comment.
- A user with mods on another drive can import them through a visible button.
- A folder drop/import works for normal downloaded archives and loose pak companions.
- A Nitrado user has a visible preset and concrete path examples.
- Generic hosted provider behavior is unchanged.
- No regression to v0.8.0 archive classification, variant selection, `All variants`, UE4SS external mode, or Review Sync Actions.

## Suggested Implementation Prompt

```text
Continue Windrose Mod Manager v0.8.1 from docs/planning/IMPLEMENTATION_v0.8.1.md.

Focus only on import/drag-drop clarity and hosted setup path guidance. Do not implement the broader config center.

Implement:
1. Mods import UX:
   - rename Add to Add Mod Files...
   - add clear inactive-mod drop-zone/empty-state wording
   - explain that downloads can be on any drive
   - support Add Folder or folder drop scanning for supported mod files
   - keep existing archive copy/hash reuse behavior
   - show fallback text if drag/drop is unavailable

2. Hosted setup UX:
   - use Server Folder consistently in visible labels
   - add concrete examples for windrose/R5, direct R5 login, and provider-specific Mods folder
   - add Nitrado FTP preset using protocol FTP, port 21, Server Folder windrose, Mods Folder Override windrose/Mods
   - preserve generic hosted defaults and existing provider presets

3. Help/welcome text:
   - update first-run import wording
   - add short Help guidance for adding mods and hosted server paths

4. Tests:
   - folder import scans supported files
   - loose pak companions still bundle together
   - unsupported folder contents produce concise warnings
   - Nitrado preset path values are correct
   - generic RemoteProfile derived path remains R5/Content/Paks/~mods
   - diagnostics stay redacted

Verification required:
- run python -m compileall windrose_deployer -q
- run python -m pytest -q
- run source smoke opening Dashboard, Mods, Server, Activity, Settings, Help
- source smoke import archive and folder
- source smoke hosted setup with Nitrado preset

Do not package/release unless explicitly asked.
```
