# Windrose Mod Manager - v0.7.1 to v0.9 Product Plan

## Product Direction

Windrose Mod Manager should stay a Windrose-focused deployment tool, not a generic platform client.

The app should handle the archives and runtime layouts Windrose users actually receive:

- manual zip, 7z, and rar archives
- Nexus downloads
- Discord or GitHub release archives
- multi-pak bundles
- multi-variant pak archives
- UE4SS runtime archives
- UE4SS mod archives
- hosted server upload workflows
- client/server parity checks
- known config files and generated override workflows

The source of the archive should matter less than the files inside it. Platform APIs, dependency ecosystems, and deep package-manager behavior are deferred unless they become necessary for Windrose-specific workflows.

## Research Summary

### UE4SS Runtime Capabilities

UE4SS supports Lua scripting, keybinds, hooks, custom console commands, GUI console tooling, and live property viewing/editing. That means an in-game admin or config surface is technically possible, but it requires a UE4SS mod or Windrose-specific runtime bridge.

Practical implication:

- manager-side config editing is reliable now
- in-game config/admin support should be treated as a later optional bridge
- the manager can install and configure that bridge, but cannot create in-game UI behavior without runtime code

### Mature Mod Manager Patterns

Useful patterns to borrow:

- Gale/r2modman: profiles, dependency visibility, config editor, simple install states
- Vortex: deployment preview, conflict detection, rules, file-level conflict review
- Mod Organizer 2: isolated source files, profile-specific activation, clear conflict visibility
- CurseForge: profile/modpack import/export, compatibility states, clear user-driven install flow

Windrose should borrow the interaction patterns, not the full ecosystem scope.

### Captain's Console Research Delta

`Captains Console` / `Windrose Captain's Console` is a separate unofficial local desktop admin panel for Windrose dedicated server management.

Useful observed features:

- SteamCMD and dedicated server install/update flow
- first-run provisioning help after install
- server root selection with launch target and process/server state
- start, stop, and restart controls
- Captain/server config editing
- World config editing
- discovered world list with active world state
- create, import, delete, and switch worlds
- backup and restore tools
- scheduled backups
- scheduled reboots
- logbook with filtering and export
- warnings area
- community mod workflow tools
- theme selector

Product reading:

- It is closer to a dedicated-server console than a mod manager.
- Windrose Mod Manager should not copy its layout or code, but it should borrow the workflow idea of a compact server operations surface.
- The strongest borrow is not the online provider search; it is the server-owner workflow: selected server, current state, safe config/world actions, live logs, and recovery controls in one place.
- The UI is dense and functional, but should not be copied directly. Windrose Mod Manager should keep its v0.7 cleanup direction: shorter text, clearer cards, better spacing, and preview-first actions.

Implementation rule:

- Treat Captain's Console as research only. Do not copy code, artwork, names, or exact UI composition without explicit permission.

## Non-Goals Through v0.9

- Do not build a generic Thunderstore/Gale replacement.
- Do not add silent mod downloads or silent automatic updates.
- Do not add deep pak asset inspection or `retoc` workflows unless normal archive planning proves insufficient.
- Do not add a broad load-order system until Windrose users show a real need.
- Do not promise in-game config/admin panels before there is a working UE4SS bridge.
- Do not replace a working host-managed UE4SS runtime unless the user explicitly chooses that.

## v0.7.1 - Public Introduction Polish

### Goal

Make the current app credible before introducing it broadly to the Windrose community.

The main user-facing promise should be:

> The manager inspects Windrose archives before installing, can handle common multi-variant pak archives, and explains what it will deploy to client, local server, dedicated server, or hosted server targets.

### Slice 1 - Archive Summary Panel

Show a concise summary whenever an archive is selected or imported:

- archive filename
- detected install kind
- pak count
- companion Unreal asset count (`.utoc`, `.ucas`)
- variant groups found
- loose file count
- config or manifest files found
- UE4SS mod/runtime detection
- root/prefix detection
- warnings for mixed or ambiguous layouts

Suggested primary wording:

- `Contains 4 pak files`
- `Detected 3 numbered variants`
- `Looks like a UE4SS mod`
- `Contains config files`
- `Review recommended: mixed archive layout`

Keep full paths and technical detail in an expandable details area.

### Slice 2 - Variant Picker Polish

The manager already detects common numbered variant groups and plans only the selected variant. The UI should make that obvious.

Improve the picker:

- title: `Choose Pak Variant`
- subtitle: `Only the selected variant will be installed.`
- show clean pak filenames
- group variants by detected base name
- default to a sensible first variant without hiding the choice
- add `Cancel` behavior that stops the install cleanly

Do not select all variants by default for a detected multi-variant archive.

### Slice 3 - Pre-Install Report

Before local install or hosted upload, show a compact review:

- target: Client, Local Server, Dedicated Server, or Hosted Server
- source archive
- selected variant or selected components
- files to install/upload
- destination preview
- UE4SS status:
  - `Installed`
  - `Managed outside the app`
  - `Missing`
  - `Not required`
- overwrite/conflict risk
- backup behavior

This should become the single trust-building step before writes.

### Slice 4 - Support Diagnostics

Add `Copy Diagnostics` and later `Export Support Zip`.

Diagnostics should include:

- app version
- build type if available
- configured client/server/dedicated paths
- hosted profile name and provider type, with secrets redacted
- UE4SS mode per target
- selected archive/install plan summary
- latest visible error/result
- log path

Diagnostics must not include passwords, API keys, or raw private FTP credentials.

### Slice 5 - Wording And Fit

Clean the most visible clipped or overlong text:

- prefer short labels in primary UI
- move explanations into details panels
- avoid paragraphs inside small cards
- keep button text short
- use tooltips/details for technical terms

Example:

- replace `Compare to review parity between client installs and the hosted server...`
- with `Compare client and server mods.`

### v0.7.1 Release Criteria

- multi-variant archive flow is clear in source smoke
- pre-install report appears before local install and hosted upload
- diagnostics can be copied without secrets
- no clipped primary controls at Compact, Default, and Large UI scale
- `python -m compileall windrose_deployer -q` passes
- `python -m pytest -q` passes
- source smoke opens Dashboard, Mods, Server, Activity, Settings, and Help
- packaged smoke opens and reports the correct version

## v0.8.0 - Archive Intelligence And Deployment Confidence

### Goal

Make every archive import feel predictable, even when the archive layout is messy.

### Slice 1 - Layout Adapters

Add explicit archive layout adapters. These should be small classifier/planner helpers, not separate platform integrations.

Initial adapters:

- standard pak archive
- multi-pak bundle
- multi-variant pak archive
- UE4SS mod archive
- UE4SS runtime archive
- shim-like UE4SS runtime archive
- config-only archive
- mixed archive

Each adapter answers:

- what files are installable
- what files are metadata/support files
- what target root is expected
- whether the user must choose a variant/component
- what warnings should be shown

### Slice 2 - Component Selection For Complex Archives

Variant selection handles one common case. v0.8 should generalize selection for complex archives:

- choose one variant from a variant group
- choose optional companion paks
- keep `.pak`, `.utoc`, and `.ucas` companions together
- prevent installing metadata-only files by accident
- preserve the selected components in install history

### Slice 3 - Rich Install Metadata

Store enough metadata to support repair, reinstall, compare, and diagnostics:

- source archive path
- manager-owned archive path
- archive hash
- detected layout kind
- selected variant
- selected entries
- installed files
- target roots
- install warnings acknowledged

### Slice 4 - Conflict And Risk Review

Classify install risks before writes:

- overwrites managed file from same mod
- overwrites managed file from another mod
- overwrites unmanaged file
- missing target path
- missing UE4SS runtime
- UE4SS marked external
- hosted path not verified
- mixed layout requires manual review

Show risk in the pre-install report and block only when the action would be unsafe or ambiguous.

### Slice 5 - Compare And Sync Improvements

Improve client/server/hosted parity flows:

- explain why actions are disabled
- preserve selected variant/component when syncing
- avoid one-click sync for ambiguous variant/component archives
- show destination preview for each sync action

### v0.8.0 Release Criteria

- archive classification has focused unit coverage
- selected component metadata survives restart
- local and hosted install paths use the same archive plan concepts
- conflict/risk review catches managed and unmanaged overwrites
- compare/sync does not upload extra variant paks

## v0.8.1 - Config Center

### Goal

Make file-based Windrose, server, UE4SS, and framework config safer than manual editing.

### Config Surfaces

Add a central config surface or clearly grouped config area for:

- Client config
- Local Server config
- Dedicated Server config
- Hosted Server config
- UE4SS runtime config
- UE4SS mod config
- WindrosePlus config and override files
- RCON config

### Known Config Files

Detect and edit known files first:

- `UE4SS-settings.ini`
- UE4SS `mods.txt`
- UE4SS mod `enabled.txt`
- UE4SS mod `settings.ini`
- WindroseRCON `settings.ini`
- WindrosePlus `.json`
- WindrosePlus override `.ini` files
- known server/world config files already supported by the app

### Safe Editing Rules

- backup before save
- validate JSON before save
- apply simple INI sanity checks where practical
- show `restart required`
- show `rebuild required` for WindrosePlus override changes
- for hosted targets, download, edit, backup, and upload known files

### v0.8.1 Release Criteria

- known config editor works for local and dedicated targets
- hosted known config edit/upload works where provider access allows it
- backups are created before writes
- invalid JSON cannot be saved
- diagnostics include config source paths without secrets

## v0.8.2 - Server Operations And World Safety

### Goal

Improve the existing Server surface so local and dedicated server owners can run, inspect, and recover the server without leaving the manager.

This should complement the mod deployment workflow, not turn the app into a generic server panel.

### Slice 1 - Server Control Strip

Add a compact, persistent server operations header when a local or dedicated server target is selected:

- selected server folder
- launch target detected
- process status
- server state
- start, stop, restart
- open folder
- refresh status

Process checks must use cached/background status helpers so the UI does not hitch.

### Slice 2 - Warning Center

Add a concise warning center for actionable server issues:

- server running while editing config
- active world ID does not match a discovered world
- no world saves discovered
- missing `ServerDescription.json`
- direct connection loopback address on a public server
- high `MaxPlayerCount` warning
- missing UE4SS runtime for UE4SS mods
- hosted profile/path not verified

Warnings should be copyable into diagnostics.

### Slice 3 - World Management

Add safer world workflows where Windrose paths are known:

- discovered world list
- active world state
- set selected world active
- import world folder
- create initial/new world if safe
- backup selected world settings
- restore selected world settings
- move world to trash instead of hard delete

Every write must be preview-first and backed up where possible.

### Slice 4 - First-Run Provisioning Guidance

For a local/dedicated server folder with missing generated config:

- explain that Windrose may need one first launch to generate files
- guide the user through start, wait for generated config, stop, reload
- auto-detect generated `WorldIslandId` where practical
- avoid overwriting real world data during repair/setup

SteamCMD install/update can remain deferred unless local dedicated server setup becomes a common support issue.

### Slice 5 - Logbook Improvements

Improve log visibility:

- live tail known Windrose log files
- keyword filter
- clear view
- export logs
- include recent relevant log lines in support diagnostics

### Slice 6 - Scheduled Safety Tasks

Research and optionally add app-local scheduled tasks:

- scheduled backups
- scheduled restarts/reboots
- visible next-run time
- clear warning that the app must be running
- disable by default

Use this only for local/dedicated targets. Hosted scheduling belongs to provider panels unless a provider API or remote command workflow is explicitly configured.

### v0.8.2 Release Criteria

- server control strip does not block tab opening
- warnings are generated by a testable helper
- world writes create backups or move data to trash
- log export works without including secrets
- scheduled tasks are disabled by default and survive app restart only when explicitly enabled

## v0.9.0 - Profiles, Presets, And Optional Runtime Bridge

### Goal

Make repeatable Windrose setups easy while keeping normal install workflows simple.

### Slice 1 - Windrose Profiles

Add narrow profiles, not a generic modpack ecosystem.

Profile examples:

- `Client only`
- `Local test server`
- `Dedicated server`
- `Hosted server`

Profile data:

- active mod set
- selected variants/components
- target paths
- hosted profile reference
- UE4SS mode
- relevant config snapshots or references

Do not store secrets in exported profiles.

### Slice 2 - Export And Import

Support sharing or backing up a setup:

- mod list
- source archive hashes
- selected variants/components
- target type
- config snapshots where safe
- missing archive warnings on import

Import must be preview-first and must not silently write files.

### Slice 3 - Presets

Add guided presets for common cases:

- hosted UE4SS external
- manual UE4SS local
- local server test setup
- dedicated server parity baseline
- WindrosePlus rebuild workflow
- local server with scheduled backups
- dedicated server with world/config safety checks

### Slice 4 - Optional UE4SS Runtime Bridge Research

Research a Windrose-specific UE4SS helper mod only after manager-side config is stable.

Potential bridge capabilities:

- show runtime status in-game
- expose console commands for manager-supported config reload/status
- expose admin-only commands where safe
- optionally expose a simple in-game config/admin UI

Bridge constraints:

- optional install
- clearly marked experimental until proven
- no dependency on it for normal pak installs
- no promise that every config can be hot-reloaded
- server/admin permission model must be understood before public release

### v0.9.0 Release Criteria

- profiles do not corrupt active installs
- export/import is preview-first
- selected variants/components survive profile export/import
- presets produce understandable install plans
- UE4SS bridge remains research-only unless it has focused runtime testing

## Deferred Work

### Nexus Update Integration

Nexus metadata and update checks remain valuable, but they are deferred behind archive intelligence and config safety.

When revisited:

- use official Nexus API rules
- keep downloads user-authorized
- never silently replace installed mods
- route downloaded files through the same archive review/install workflow

### Online Provider Search

Online provider search/install is deferred. Captain's Console includes CurseForge API search/install ideas, but Windrose Mod Manager should not add provider-specific search before archive intelligence, install preview, and config safety are stable.

When revisited:

- keep provider API keys out of primary setup unless needed
- keep downloaded archives preview-first
- do not install provider packages directly into live folders without archive inspection
- prefer source-agnostic import flow over platform-specific UI

### Load Order

Do not add load order until there is evidence Windrose needs it.

If implemented later, prefer a managed priority/prefix model:

- app controls deployed filename prefixes
- `.pak`, `.utoc`, and `.ucas` move together
- original archives remain unchanged
- preview before rename/redeploy

### Deep Pak Inspection

Do not include `retoc` or deep asset inspection in v0.7.x-v0.9 unless normal archive planning cannot solve the real user problem.

## Community Introduction Gate

Introduce the manager publicly after v0.7.1 when these claims are true in the UI, not just internally:

- archive summary is visible
- common numbered multi-variant archives prompt for a single variant
- install/upload preview shows destination and risk
- UE4SS external/host-managed mode is clear
- diagnostics can be copied for support

Suggested positioning:

> Windrose Mod Manager is focused on Windrose deployment workflows: manual archives, pak bundles, client/local/dedicated/hosted installs, backups, parity checks, and UE4SS-aware installs. It inspects archives before installing and can handle common multi-variant pak archives by asking which variant should be deployed.

## References

- UE4SS documentation: https://docs.ue4ss.com/
- UE4SS console command handler: https://docs.ue4ss.com/dev/lua-api/global-functions/registerconsolecommandhandler.html
- UE4SS installation guide: https://docs.ue4ss.com/installation-guide
- Gale package page: https://thunderstore.io/c/repo/p/Kesomannen/GaleModManager/
- Vortex page: https://www.nexusmods.com/mods/modmanager
- Vortex conflict docs: https://github.com/Nexus-Mods/Vortex/wiki/MODDINGWIKI-Users-General-Managing-File-Conflicts
- CurseForge profile docs: https://support.curseforge.com/en/support/solutions/articles/9000196904-creating-a-custom-profile
- Mod Organizer 2 overview: https://geckwiki.com/index.php?title=Mod_Organizer_2
- Captain's Console Nexus page: https://www.nexusmods.com/windrose/mods/332
- Captain's Console GitHub repository: https://github.com/jacopengel/CaptainsConsole
