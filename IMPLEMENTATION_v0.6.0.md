# Windrose Mod Manager - v0.6.0 Implementation Plan

## Release Goal

`v0.6.0` should make Windrose Mod Manager the safest practical way to install and manage UE4SS-based Windrose mods, while preparing the app for future server-admin and configurable-tweak workflows.

Primary theme:

- full UE4SS runtime support
- full UE4SS mod support
- clearer framework/dependency visibility
- safer server-operator foundations

Secondary theme:

- pull forward the most important unshipped `0.5.2` trust/polish items
- prepare for WindrosePlus support as an integration target after UE4SS support is stable
- keep the configurable overhaul/tweak-builder pipeline from `IMPLEMENTATION_configurable_overhaul.md` as a later fallback/advanced lane, not the center of `0.6.0`
- defer a future RCON admin panel unless a narrow detection/config-only slice is clearly safe

## Product Positioning

This release should keep the app focused on Windrose mod management.

It should not become:

- a generic UE4SS manager for every Unreal game
- a generic RCON/server-control panel
- a bundled third-party runtime distributor without permission
- a universal pak/asset editor
- an automatic Nexus download/update manager
- a full configurable overhaul builder unless the feasibility gates pass
- a clone of WindrosePlus or any other server-side framework

## Current Repo Reality

The repo already has useful foundations:

- archive inspection and loose-file planning in `windrose_deployer/core/archive_inspector.py` and `deployment_planner.py`
- local target roots for client, local server, and dedicated server in `target_resolver.py`
- hosted upload/delete/config support through SFTP/FTP in `remote_deployer.py`
- basic UE4SS/framework detection in `framework_detector.py`
- metadata/version hint foundations in `metadata.py` and `version_hints.py`
- dashboard/activity/profiles foundations from `0.5.x`
- generated tweak-builder planning in `IMPLEMENTATION_configurable_overhaul.md`

The repo does not yet have:

- a first-class UE4SS install mode
- clear separation between pak mods, loose mods, UE4SS runtime, and UE4SS mods in install UX
- UE4SS runtime state per target in the Dashboard/Mods screens
- hosted UE4SS validation
- UE4SS mod dependency warnings tied to actual target state
- RCON config detection or editing
- RCON client/admin panel
- safe generated-mod source modeling for tweak-builder output

## External Context

Known Windrose UE4SS-related mods:

- UE4SS for Windrose: installs a UE4SS runtime into `R5\Binaries\Win64`
- Windrose Source RCON Protocol: requires UE4SS and installs under `R5\Binaries\Win64\ue4ss\Mods`, with `settings.ini` for port/password
- WindrosePlus: server-side UE4SS framework that already covers multipliers, advanced server settings, generated override PAK rebuilds, RCON/admin features, query/status, and server-side scripting

Important permission rule:

- do not bundle/re-upload UE4SS unless explicit permission is granted by the author/license
- first implementation should support user-supplied UE4SS archives
- do not copy WindrosePlus behavior into the manager; support installing, detecting, configuring, backing up, and launching its documented workflows where safe

## v0.6.0 Must-Have Scope

### 1. UE4SS Runtime Detection

Detect UE4SS runtime state per target:

- Client
- Local Server
- Dedicated Server
- Hosted Server

Detection markers should include both common and Windrose-page-specific variants:

- `R5\Binaries\Win64\UE4SS.dll`
- `R5\Binaries\Win64\ue4ss.dll`
- `R5\Binaries\Win64\UE4SS-settings.ini`
- `R5\Binaries\Win64\ue4ss-settings.ini`
- `R5\Binaries\Win64\dwmapi.dll`
- `R5\Binaries\Win64\dwmappi.dll`
- `R5\Binaries\Win64\ue4ss\`
- hosted equivalents under the configured server root

Acceptance:

- the app can answer whether UE4SS is installed for each configured target
- missing/inaccessible targets do not crash detection
- hosted detection works over FTP/SFTP file access where possible

### 2. UE4SS Runtime Install Workflow

Add explicit support for installing UE4SS runtime archives.

Behavior:

- detect likely UE4SS runtime archives during inspection/import
- show a distinct badge/category:
  - `UE4SS Runtime`
- offer an explicit install action:
  - `Install UE4SS Runtime`
- install to the correct root:
  - target root + `R5\Binaries\Win64`
- preserve archive structure correctly whether the archive contains:
  - files already rooted at `R5/Binaries/Win64`
  - files rooted at `Binaries/Win64`
  - runtime files at archive root
  - a top-level wrapper folder

Targets:

- Client
- Local Server
- Dedicated Server
- Hosted Server

Safety:

- back up overwritten runtime files before replacing
- track UE4SS runtime as a managed install
- uninstall should remove only files installed by the manager and restore overwritten originals
- warn if installing UE4SS to a target that is not configured

Acceptance:

- user can drag in UE4SS archive and install it correctly without manually choosing loose-file root details
- UE4SS runtime appears as managed, not as a normal pak mod

### 3. UE4SS Mod Install Workflow

Add explicit support for UE4SS mod archives.

Behavior:

- detect likely UE4SS mods when an archive contains paths like:
  - `ue4ss/Mods/<ModName>/...`
  - `R5/Binaries/Win64/ue4ss/Mods/<ModName>/...`
  - `<ModName>/Scripts/...` with UE4SS indicators
  - `<ModName>/enabled.txt`
  - `<ModName>/settings.ini`
- show a distinct badge/category:
  - `UE4SS Mod`
- install to:
  - target root + `R5\Binaries\Win64\ue4ss\Mods\<ModName>`
- normalize common archive wrapper layouts safely
- keep multi-file mod folders grouped as one managed install

Targets:

- Client
- Local Server
- Dedicated Server
- Hosted Server

Dependency handling:

- if target UE4SS runtime is missing, show:
  - `UE4SS runtime likely required`
  - `Install UE4SS first`
- do not block by default unless install plan is impossible
- allow expert override only if the user confirms

Acceptance:

- UE4SS mods install to the correct `ue4ss\Mods` folder
- UE4SS mods do not get misrouted to `~mods`
- dependency warnings are target-aware

### 4. UE4SS Mod Lifecycle Management

UE4SS runtime and UE4SS mods must participate in the normal managed lifecycle:

- install
- uninstall
- repair/reinstall when source archive exists
- backup overwritten files
- manifest history
- activity timeline
- target filters
- dashboard status/counts
- hosted upload/delete where applicable

Important:

- runtime installs and UE4SS mod installs should not be treated as pak-only installs
- they should be grouped by target and folder, not by individual loose files in the main UI

Acceptance:

- UE4SS runtime and UE4SS mods can be managed like first-class install types
- uninstall does not leave orphaned files installed by the manager

### 5. UE4SS UI Surfaces

Add UE4SS-aware surfaces without making the app cluttered.

Recommended UI changes:

- Mods tab:
  - badge archives as `Pak`, `Loose`, `UE4SS Runtime`, `UE4SS Mod`, `Mixed`
  - right-click actions:
    - `Install UE4SS Runtime To...`
    - `Install UE4SS Mod To...`
  - warning line when runtime is missing for the selected target
- Dashboard:
  - compact UE4SS status in the Status or Attention card
  - example:
    - `UE4SS: Client installed | Dedicated missing`
- Server tab:
  - show UE4SS runtime state for active server target
  - for hosted, show `Unknown` if remote detection cannot verify it
- Activity:
  - clear labels:
    - `Installed UE4SS runtime`
    - `Installed UE4SS mod`

Acceptance:

- users can understand UE4SS state without reading logs
- UE4SS does not visually disappear into generic loose-file installs

### 6. Hosted UE4SS Support

Hosted support should work over the existing SFTP/FTP provider layer.

Must include:

- hosted UE4SS runtime detection via remote path checks
- hosted UE4SS mod detection/listing where practical
- upload UE4SS runtime files to remote `R5/Binaries/Win64`
- upload UE4SS mods to remote `R5/Binaries/Win64/ue4ss/Mods`
- delete/uninstall hosted UE4SS installs that are tracked by the manager

Important warnings:

- FTP supports file access only
- FTP does not support remote restart commands
- Linux native servers may not support Windows UE4SS runtime layout
- Wine/Proton hosted setups may work if the host exposes the correct files

Acceptance:

- hosted UE4SS file deployment works without pretending restart/admin control is guaranteed

### 7. RCON Foundation

Prepare for an RCON admin panel, but keep it narrow.

Must include:

- detect likely RCON UE4SS mods such as Windrose Source RCON Protocol
- detect/edit local or hosted `settings.ini` for known RCON mod layouts where safe
- add optional server profile fields or a separate lightweight model for:
  - RCON host
  - RCON port
  - RCON password
  - enabled/disabled
- do not store RCON password inside mod profiles
- if storing RCON password before credential encryption exists, clearly mark it as local plain-text storage or allow "do not save password"

Dashboard preparation:

- add a placeholder/status slot only when configured:
  - `RCON: not configured`
  - `RCON: configured`
  - `RCON: connection test failed`
- add `Test RCON` only if a simple, safe client can be implemented

Cut rule:

- if protocol/client implementation becomes uncertain, ship only detection/config editing and defer live admin commands

Acceptance:

- the app is ready for RCON admin without becoming a full server panel in `0.6.0`

### 8. WindrosePlus Detection And Integration Groundwork

Treat WindrosePlus as an external server-side framework that the manager can support.

Must include if scope allows:

- detect WindrosePlus under:
  - `R5\Binaries\Win64\ue4ss\Mods\WindrosePlus`
  - hosted equivalents under the configured server root
- classify WindrosePlus as:
  - `UE4SS Mod`
  - `Server Framework`
- show that it requires UE4SS runtime on the target
- avoid presenting WindrosePlus as a normal pak-only mod

Should defer unless safe:

- editing WindrosePlus configs
- running the WindrosePlus PAK rebuild script
- launching a WindrosePlus dashboard
- any live RCON/admin commands

Acceptance:

- the app can recognize WindrosePlus and guide the user without cloning or owning the framework

## v0.6.0 Should-Have Scope

### 9. Metadata / Version Notification Foundation

Pull forward the metadata/version work already documented for `0.6`.

Must remain notification-only:

- no auto-download
- no auto-install
- no Nexus API dependency unless explicit metadata exists

Recommended first pass:

- make metadata editing easier to find for archives and installed mods
- support optional fields:
  - Nexus mod URL
  - Nexus mod ID
  - Nexus file ID
  - version tag
  - source label
  - author label
- improve "possible update available" hints when a newer imported archive appears to supersede an installed version
- add roadmap hooks for later upstream checks

Acceptance:

- users can maintain enough metadata for future update notifications
- wording stays careful:
  - `possible update available`
  - `newer imported archive may supersede this install`

### 10. Manifest Drift UI

Carry over the `0.5.2` trust item if not already shipped:

- surface manifest drift on Dashboard and/or Mods tab
- avoid modal spam
- give a clear action:
  - review in Mods
  - repair
  - reinstall

Acceptance:

- users see out-of-manager file changes without opening the technical log

### 11. Activity / Backup Polish

Carry over the `0.5.2` activity/backups polish if not already shipped:

- large history performance pass
- copy consistency: `Activity & Backups`, not stale `Recovery Center`
- backup delete selected/delete all remains clear
- activity rows for UE4SS installs are readable

Acceptance:

- UE4SS lifecycle events appear cleanly in the activity timeline

### 12. Hosted Provider QoL

Carry over remaining hosted setup polish:

- Host Havoc helper/preset rows
- Indifferent Broccoli helper/preset rows
- FTP diagnostic cleanup
- preserve explicit provider ports

Acceptance:

- hosted UE4SS setup has the same provider clarity as hosted pak installs

## Configurable Overhaul Integration

`IMPLEMENTATION_configurable_overhaul.md` remains valid, but it should not be merged into the UE4SS work as one giant feature.

For `v0.6.0`, include only the safe foundations if time allows:

### Configurable Overhaul Allowed In v0.6.0

- create a `Tweaks` research/catalog document
- define model/store skeletons only if they do not affect install behavior:
  - `TweakDefinition`
  - `TweakConfig`
  - `ToolchainSettings`
- add Settings placeholder for external toolchain only if clearly marked experimental:
  - `retoc path`
  - `.usmap path`
- add no end-user "Build & Install" button until manual proof and patch-engine spike pass

### Configurable Overhaul Not In v0.6.0 Unless Gates Pass

- no asset patch engine in production UI
- no generated tweak mod build/install
- no bundled template workspace in release build
- no hosted generated tweak deployment
- no UI that implies tweaks are ready before in-game proof exists
- no third-party pak patching or mutation

### Required Gates Before Shipping Tweak Builder

These gates come from `IMPLEMENTATION_configurable_overhaul.md` and remain mandatory:

1. manual combined mod proof:
   - comfort
   - inventory
   - ship
2. patch-engine spike:
   - load one known converted template asset
   - patch one primitive property
   - repack with `retoc`
   - verify in game
3. packaged resource spike:
   - packaged EXE can read tweak defs/templates
   - output is generated in writable app data

## Architecture Additions

### New / Expanded Models

Likely additions:

- `FrameworkInstallKind`
  - `standard_mod`
  - `ue4ss_runtime`
  - `ue4ss_mod`
  - `rcon_mod`
- `FrameworkTargetState`
- `RconProfile` or `RconSettings`
- optional `ModInstall.install_kind` defaulting to `standard_mod`
- optional `DeploymentRecord.install_kind` defaulting to `standard_mod`

Compatibility:

- old manifest records must default to `standard_mod`
- old activity/history records must still load
- no existing archive/install data should be invalidated

### New / Expanded Core Services

Recommended:

- `framework_detector.py`
  - expand current UE4SS detection
- `framework_state_service.py`
  - local and hosted UE4SS runtime state
- `framework_deployment_planner.py`
  - UE4SS runtime/mod path normalization
- `rcon_config_service.py`
  - detect/read/write known RCON `settings.ini`
- `rcon_client.py`
  - only if live RCON test/admin commands are included

Possible later configurable-overhaul services:

- `tweak_definition_store.py`
- `tweak_config_store.py`
- `toolchain_store.py`

### UI Files Likely Affected

- `windrose_deployer/ui/tabs/mods_tab.py`
- `windrose_deployer/ui/tabs/dashboard_tab.py`
- `windrose_deployer/ui/tabs/server_tab.py`
- `windrose_deployer/ui/tabs/backups_tab.py`
- `windrose_deployer/ui/tabs/settings_tab.py`
- `windrose_deployer/ui/app_window.py`

### Core Files Likely Affected

- `windrose_deployer/core/framework_detector.py`
- `windrose_deployer/core/deployment_planner.py`
- `windrose_deployer/core/remote_deployer.py`
- `windrose_deployer/core/installer.py`
- `windrose_deployer/core/integrity_service.py`
- `windrose_deployer/core/manifest_store.py`
- `windrose_deployer/core/recovery_service.py`
- `windrose_deployer/core/server_sync_service.py`
- `windrose_deployer/core/target_resolver.py`
- `windrose_deployer/models/mod_install.py`
- `windrose_deployer/models/deployment_record.py`

## Implementation Slices

### Slice 1 - Detection And State

Goal:

- expand UE4SS/RCON detection without changing install behavior yet

Tasks:

- improve `framework_detector.py`
- detect runtime archives, UE4SS mod archives, and likely RCON mods
- detect installed UE4SS state locally
- detect installed UE4SS state remotely with provider path checks
- add tests for archive layouts and target states

Acceptance:

- the app can classify UE4SS runtime vs UE4SS mod vs normal mod reliably enough for UI warnings

### Slice 2 - Data Compatibility

Goal:

- allow managed installs/history to record framework install kinds

Tasks:

- add optional install-kind fields with backward-compatible defaults
- update manifest serialization/load fallback
- update activity/history labels safely
- ensure old fixture data still loads

Acceptance:

- old app state loads unchanged
- UE4SS installs can be tracked distinctly

### Slice 3 - Local UE4SS Runtime Install

Goal:

- install UE4SS runtime correctly to local targets

Tasks:

- normalize common UE4SS archive layouts
- plan runtime files to `R5\Binaries\Win64`
- support Client / Local Server / Dedicated Server
- back up and track overwritten files
- add UI install action and warnings

Acceptance:

- user-supplied UE4SS archive installs correctly on local targets

### Slice 4 - Local UE4SS Mod Install

Goal:

- install UE4SS mods correctly to local targets

Tasks:

- normalize common UE4SS mod layouts
- plan mod folders to `R5\Binaries\Win64\ue4ss\Mods`
- warn if runtime missing
- track UE4SS mod folder as one managed install

Acceptance:

- user-supplied UE4SS mod archives install and uninstall cleanly on local targets

### Slice 5 - Hosted UE4SS Support

Goal:

- extend runtime/mod UE4SS install to hosted targets

Tasks:

- remote path planning for runtime and UE4SS mod folders
- hosted runtime detection
- hosted dependency warnings
- hosted upload/delete with existing SFTP/FTP providers
- honest restart limitations for FTP

Acceptance:

- hosted UE4SS installs work through file access without implying shell/admin control

### Slice 6 - UI Integration

Goal:

- make UE4SS understandable in the main app

Tasks:

- archive/applied badges
- right-click install actions
- target-aware dependency warnings
- dashboard UE4SS status
- server active-target UE4SS status
- activity labels

Acceptance:

- users can see and manage UE4SS state without guessing folder paths

### Slice 7 - RCON Preparation

Goal:

- support RCON mod setup without overbuilding server control

Tasks:

- detect likely RCON UE4SS mods
- detect/read/write known `settings.ini` where safe
- add optional RCON config model
- add Dashboard RCON status placeholder
- optionally add `Test RCON` if a small client is reliable

Acceptance:

- RCON setup becomes visible and configurable, but live admin commands can still be deferred

### Slice 8 - Trust / Metadata / Activity Polish

Goal:

- finish remaining documented trust polish if not already shipped

Tasks:

- manifest drift visible in UI
- metadata editing polish
- version notification foundation
- activity performance pass
- hosted provider QoL

Acceptance:

- 0.6 is not only a UE4SS release; it also improves trust and operations

### Slice 9 - Configurable Overhaul Foundations

Goal:

- prepare the tweak-builder lane without shipping unproven asset patching

Tasks:

- add/update tweak research catalog
- add experimental toolchain settings if useful
- no production build/install UI until gates pass

Acceptance:

- the configurable overhaul plan is advanced safely without destabilizing mod management

## RCON Admin Panel Future Shape

If live RCON support is viable after the foundation:

Dashboard card:

- server source
- RCON configured / connected / failed
- connect/test button
- player count if available

RCON tab/drawer:

- server info
- player list
- selected player details
- kick
- ban
- raw command box only behind an advanced toggle, if included at all

Security rules:

- never expose password in plain UI text
- do not store password unless user opts in
- do not include RCON secrets in exported profiles/support bundles
- make it clear RCON is server-admin access

Recommended release placement:

- `0.6.0`: detect/configure/test if reliable
- `0.6.x`: player list/info
- `0.7.0`: kick/ban/admin actions if users request it

## Testing Plan

### Automated Tests

Add/extend tests for:

- UE4SS runtime archive detection
- UE4SS mod archive detection
- RCON mod detection
- both `dwmapi.dll` and `dwmappi.dll` runtime markers
- local target path planning for UE4SS runtime
- local target path planning for UE4SS mods
- hosted target path planning for UE4SS runtime/mods
- missing runtime dependency warnings
- manifest compatibility with install-kind defaults
- uninstall/repair behavior for grouped UE4SS mod folders
- RCON settings parser/writer if included

### Manual Smoke Tests

Required:

1. Drag in UE4SS for Windrose archive
2. Install UE4SS runtime to Client
3. Install UE4SS runtime to Dedicated Server
4. Verify files land under `R5\Binaries\Win64`
5. Drag in a UE4SS mod archive
6. Verify missing-runtime warning appears when target lacks UE4SS
7. Install UE4SS mod to `R5\Binaries\Win64\ue4ss\Mods`
8. Uninstall UE4SS mod and verify the folder is removed/restored correctly
9. Repair/reinstall UE4SS runtime if source archive exists
10. Hosted FTP/SFTP UE4SS mod upload
11. Hosted UE4SS uninstall/delete for tracked files
12. Dashboard UE4SS status reflects installed/missing targets
13. Activity shows readable UE4SS install/uninstall events

If RCON foundation ships:

14. Detect RCON mod archive
15. Read/write known `settings.ini`
16. Test RCON connection where a server/plugin is available
17. Confirm password is not exposed or exported accidentally

If configurable-overhaul foundations ship:

18. Toolchain settings save/load
19. Tweak catalog loads
20. No user-facing Build button appears unless feasibility gates pass

## Release Criteria

Ship `v0.6.0` when:

- UE4SS runtime installs correctly on client/local/dedicated
- UE4SS mods install correctly on client/local/dedicated
- hosted UE4SS file deployment works or is explicitly marked experimental
- runtime dependency warnings are target-aware
- old manifests/settings still load
- activity/history remains readable
- tests pass
- packaged EXE smoke test passes

Do not ship if:

- normal pak installs regress
- UE4SS archives are routed to `~mods`
- missing UE4SS runtime is silently ignored
- uninstall removes files outside the manager's tracked install set
- hosted FTP/SFTP behavior regresses

## Cut Rules

Cut in this order if scope grows:

1. live RCON admin commands
2. RCON connection test
3. hosted UE4SS runtime detection, while keeping hosted upload if safe
4. metadata/version polish
5. configurable-overhaul toolchain settings
6. advanced dashboard polish

Do not cut:

- local UE4SS runtime install
- local UE4SS mod install
- dependency warnings
- manifest/storage backward compatibility
- safe uninstall/backup behavior

## Documentation Updates

Update:

- `README.md`
  - supported mod types should include UE4SS runtime and UE4SS mods
  - hosted notes should explain file-access-only limitations
- `ROADMAP.md`
  - v0.6 should point to this implementation plan
- Nexus description/sticky for release:
  - explain UE4SS support
  - explain that UE4SS is user-supplied unless permission to bundle is granted
  - explain hosted limitations honestly

## One-Sentence Summary

`v0.6.0` should make UE4SS a first-class, safe, target-aware workflow in Windrose Mod Manager, while laying careful groundwork for future RCON admin tools and the configurable tweak-builder without turning the app into a generic server panel or asset editor.
