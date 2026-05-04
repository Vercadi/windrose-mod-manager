# v0.6.6 Implementation Plan - Restore Vanilla

## Goal

`v0.6.6` should add a clear, safe way to return a selected local target to a vanilla mod state.

This is a cleanup/safety release before `v0.7` load order.

The feature should solve this problem:

- Dashboard detects real framework or unmanaged files on disk
- Active Mods may be empty because those files are not tracked by the manager
- users need an obvious way to clean one target without manually deleting files

Use friendly wording:

- button: `Restore Vanilla`
- dialog title: `Restore Vanilla: Dedicated Server`
- result: `Dedicated Server restored to vanilla mod state.`

## Non-Goals

Do not implement:

- hosted/remote restore-to-vanilla
- load order
- Nexus update/download support
- retoc integration
- generic remote file browser
- RCON admin commands
- broad UI redesign
- deleting saves
- deleting `ServerDescription.json`, `WorldDescription.json`, or user server settings
- one-click global cleanup across every target

## Scope

Supported targets:

- `Client`
- `Local Server`
- `Dedicated Server`

Deferred:

- `Hosted Server`

Reason:

Hosted cleanup requires remote path safety, provider differences, stronger confirmation, and probably a separate hosted delete preview. Do not mix it into this local restore pass.

## Product Behavior

`Restore Vanilla` should restore the selected target to a vanilla mod state by optionally removing:

- managed mods
- unmanaged `~mods` files
- framework files

It must not touch:

- saves
- worlds
- server settings
- hosted files
- archives in the manager library
- backup history

## UX Flow

### Entry Points

Add `Restore Vanilla` in:

- Dashboard quick actions
- Mods tab action area
- Frameworks dialog when local framework files are detected

If layout gets tight, prioritize:

1. Dashboard quick action
2. Frameworks dialog action
3. Mods tab action

### Target Selection

If opened from a target-specific context, preselect that target.

Examples:

- Dashboard active compare/source target is `Dedicated Server` -> preselect `Dedicated Server`
- Mods scope is `Client` -> preselect `Client`
- Frameworks target dropdown is `Dedicated Server` -> preselect `Dedicated Server`

The dialog should still allow switching between:

- `Client`
- `Local Server`
- `Dedicated Server`

Do not show `Hosted Server` in this dialog for `v0.6.6`.

### Preview Dialog

Dialog title:

`Restore Vanilla: <Target>`

Intro copy:

`This removes selected mod files from this target only. Saves and server settings are not changed.`

Checkboxes:

- `Managed mods`
- `Unmanaged ~mods files`
- `Framework files`

Default checkbox behavior:

- `Managed mods`: checked when managed installs exist for the target
- `Unmanaged ~mods files`: checked when unmanaged files exist
- `Framework files`: unchecked by default even when detected

Reason:

Framework cleanup can remove UE4SS, RCON, WindrosePlus, and helper files. It should be explicit.

Preview sections:

- `Managed mods`
- `Unmanaged ~mods files`
- `Framework files`
- `Not touched`

`Not touched` should always mention:

- saves
- server settings
- archives
- hosted files

Action buttons:

- `Restore Vanilla`
- `Cancel`

Confirmation:

Use one final destructive confirmation after preview.

Copy:

`Remove the selected files from <Target>?`

## Definitions

### Managed Mods

Managed mods are manifest records whose effective targets include the selected target.

Implementation should reuse existing uninstall logic:

- `Installer.uninstall(mod)`
- manifest history record
- manifest remove
- normal refreshes

Do not manually delete managed files outside existing uninstall flow.

### Unmanaged `~mods` Files

Unmanaged files are live files in the selected target's `R5\Content\Paks\~mods` folder that are not represented by a manifest record.

Use existing live inventory/grouping logic where possible.

File groups should preserve existing UE bundle grouping:

- `.pak`
- `.utoc`
- `.ucas`

Preview should show bundle display names, not every companion file unless expanded later.

Removal behavior:

- delete selected unmanaged file groups
- create a backup copy first when practical
- record activity/history if current manifest history model supports it safely

If backup recording is too risky, at minimum move deleted unmanaged files to a restore folder under app backups instead of hard-deleting.

Recommended backup folder:

`backups/restore_vanilla/<timestamp>/<target>/`

### Framework Files

Framework files are known local framework/runtime artifacts detected under the selected target.

Use existing framework detector paths and add explicit removal plans for:

UE4SS:

- `R5\Binaries\Win64\dwmapi.dll`
- `R5\Binaries\Win64\dwmappi.dll`
- `R5\Binaries\Win64\xinput1_3.dll`
- `R5\Binaries\Win64\UE4SS.dll`
- `R5\Binaries\Win64\UE4SS-settings.ini`
- `R5\Binaries\Win64\ue4ss\`

RCON:

- `R5\Binaries\Win64\version.dll`
- `R5\Binaries\Win64\windrosercon\`
- legacy `R5\Binaries\Win64\ue4ss\Mods\WindroseRCON\` if present

WindrosePlus:

- `WindrosePlus\`
- `windrose_plus\`
- `StartWindrosePlusServer.bat`
- `windrose_plus.json`
- `windrose_plus.ini`
- `windrose_plus.food.ini`
- `windrose_plus.weapons.ini`
- `windrose_plus.gear.ini`
- `windrose_plus.entities.ini`
- generated override PAKs:
  - `R5\Content\Paks\WindrosePlus_Multipliers_P.pak`
  - `R5\Content\Paks\WindrosePlus_CurveTables_P.pak`
  - `R5\Content\Paks\~mods\WindrosePlus_Multipliers_P.pak`
  - `R5\Content\Paks\~mods\WindrosePlus_CurveTables_P.pak`

Framework removal behavior:

- back up files/folders before removal
- delete only known paths
- do not wildcard-delete unrelated `R5\Binaries\Win64` content
- do not delete all UE4SS mods unless removing the `ue4ss` folder was explicitly selected by `Framework files`

## Architecture

Add a small focused service instead of putting all cleanup logic in a tab.

Suggested file:

`windrose_deployer/core/restore_vanilla_service.py`

Suggested models:

```python
@dataclass
class RestoreVanillaItem:
    kind: str
    target: str
    label: str
    paths: list[Path]
    managed_mod_id: str = ""
    backup_required: bool = True

@dataclass
class RestoreVanillaPlan:
    target: str
    managed_mods: list[RestoreVanillaItem]
    unmanaged_files: list[RestoreVanillaItem]
    framework_files: list[RestoreVanillaItem]
    warnings: list[str]
```

Core responsibilities:

- resolve target roots
- build preview plan
- execute selected plan sections
- back up unmanaged/framework files
- call existing installer uninstall for managed mods
- return result summary

UI responsibilities:

- present target selector
- present preview sections
- collect checkbox selections
- show final confirmation
- refresh app tabs/dashboard after success

## Implementation Slices

### Slice 1 - Planning Service

Implement `RestoreVanillaService`.

Inputs:

- app paths
- manifest store or manifest mod list
- backup root

Functions:

- `build_plan(target: str) -> RestoreVanillaPlan`
- `execute_plan(plan, include_managed: bool, include_unmanaged: bool, include_frameworks: bool) -> RestoreVanillaResult`

Acceptance:

- builds a correct local-only preview for client/local/dedicated
- rejects hosted target
- returns clear warnings when a target path is not configured

### Slice 2 - Managed Mod Cleanup

Use existing uninstall flow for managed mods.

Acceptance:

- managed mods are removed from the selected target only
- manifest history is updated
- archive library is not deleted
- other targets are not touched

Important:

If a manifest record spans multiple targets, do not remove the entire mod from all targets unless current installer supports target-splitting safely.

Preferred behavior:

- if a mod is single-target, uninstall it
- if a mod spans multiple targets, mark it as `Needs review` unless existing target-split uninstall support is already available

Do not introduce unsafe partial manifest edits.

### Slice 3 - Unmanaged `~mods` Cleanup

Plan unmanaged live file bundles for the target.

Acceptance:

- groups `.pak/.utoc/.ucas` companions
- ignores files represented by managed installs
- backs up before removal
- removes only selected target files

### Slice 4 - Framework Cleanup

Plan known framework file sets for the target.

Acceptance:

- detects UE4SS/RCON/WindrosePlus file sets
- previews known paths
- backs up before removal
- removes only selected target framework files
- never deletes broad folders outside known framework paths

### Slice 5 - UI Dialog

Add `Restore Vanilla` dialog.

Likely UI files:

- `windrose_deployer/ui/tabs/dashboard_tab.py`
- `windrose_deployer/ui/tabs/mods_tab.py`
- maybe `windrose_deployer/ui/tabs/server_tab.py` only if the Frameworks dialog lives there

Acceptance:

- dialog fits default window
- wording is short and user-friendly
- shows clear preview
- default selections are safe
- final confirmation appears

### Slice 6 - Refresh and Activity

After execute:

- refresh Mods
- refresh Dashboard
- refresh Activity if available
- refresh Backups if backups were created

Acceptance:

- Dashboard no longer shows framework state after framework files are removed
- Active Mods no longer shows managed mods after managed cleanup
- result message is clear

## Tests

Add/update tests for:

- restore plan rejects hosted target
- restore plan includes managed single-target mods for selected target
- restore plan does not include mods hidden by another target
- restore plan groups unmanaged `.pak/.utoc/.ucas`
- restore plan detects UE4SS file set
- restore plan detects RCON file set
- restore plan detects WindrosePlus file set
- execute backs up unmanaged files before deleting
- execute backs up framework files before deleting
- multi-target managed mods are not silently removed from other targets

Run:

```powershell
python -m compileall windrose_deployer -q
python -m pytest -q
git diff --check
```

## Manual Smoke Checklist

1. Install a normal mod to `Client`.
2. Create one unmanaged `.pak` in client `~mods`.
3. Install or manually place UE4SS files on `Client`.
4. Open Dashboard and verify framework detection.
5. Open `Restore Vanilla`.
6. Select `Client`.
7. Preview `Managed mods`, `Unmanaged ~mods files`, and `Framework files`.
8. Run with only `Managed mods` checked; verify unmanaged/framework files remain.
9. Run with `Unmanaged ~mods files`; verify files are backed up and removed.
10. Run with `Framework files`; verify UE4SS/RCON/WindrosePlus files are backed up and removed.
11. Verify saves/config files are still present.
12. Verify Dashboard state updates.
13. Verify Hosted Server is not offered.

## Cut Rules

If scope grows too much, cut in this order:

1. Mods tab entry point
2. Frameworks dialog entry point
3. activity/history polish
4. partial multi-target managed uninstall

Do not cut:

- Dashboard `Restore Vanilla` entry point
- preview before delete
- backups before unmanaged/framework removal
- local-only target restriction

## Release Notes Draft

- Added local `Restore Vanilla` cleanup for Client, Local Server, and Dedicated Server.
- Lets you preview and remove managed mods, unmanaged `~mods` files, and framework files separately.
- Framework cleanup covers known UE4SS, RCON, and WindrosePlus files.
- Hosted server cleanup is intentionally deferred for a safer remote workflow.
