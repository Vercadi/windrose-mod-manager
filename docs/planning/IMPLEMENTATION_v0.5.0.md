# Windrose Mod Manager - v0.5.0 Implementation Brief

## Release Goal

**v0.5.0 should make the app feel better at running servers, understanding mod dependencies, and making installs easier to trust.**

This release should improve three things at once:

- server operations visibility
- mod/install understanding
- confidence in what is installed and what may be missing or outdated

It should **not** become:

- a full server control panel clone
- a Nexus auto-download manager
- a load-order tool
- a giant profiles ecosystem

## Final Scope

## Must-Have

### 1. Server Dashboard

Add a clear server dashboard using the current app structure and naming.

Must include:

- current source summary:
  - Local Server
  - Dedicated Server
  - Hosted Server
- running/connected state:
  - Windrose client running or not
  - Local/Dedicated server running or not
  - Hosted profile connected / offline / not configured
- active world/source summary
- mod counts by target
- last backup
- last apply / restart
- quick actions:
  - Launch Windrose
  - Launch Dedicated Server
  - Open server folder
  - Open settings file
  - Run compare
  - Back up now

### 2. Metadata & Version Awareness Foundation

Add optional metadata capture for archives and installs.

Must include:

- per-archive and/or per-install optional metadata fields:
  - Nexus mod URL
  - Nexus mod ID
  - Nexus file ID
  - version tag
  - optional source/author label
- simple UI for viewing and editing that metadata
- local update hints:
  - newer imported archive looks like the same mod family
  - stored upstream metadata suggests a newer file exists
- clear "possible update available" wording instead of overclaiming certainty

### 3. Bundle-Aware Mod Cards

Improve handling for modular bundle archives and installs.

Must include:

- expandable archive cards or rows for child pak/file items
- expandable applied cards or rows for child installed items
- whole-bundle install
- selected-child install where safe
- whole-bundle uninstall
- selected-child uninstall only where manifest/archive structure makes it safe

### 4. Inspect UX Redesign

Replace the tiny bottom inspect surface for complex archives.

Must include one primary inspect surface:

- right-side drawer, or
- centered inspect dialog/modal

That surface must be able to show:

- archive overview
- child files/paks
- selected variant state
- conflicts/warnings
- metadata

The current bottom tray may remain as a light details/status surface, but not as the main inspection workflow.

### 5. Backups & Activity Become First-Class

Split operational history and backups into clearer user-facing workflows.

Must include:

- better backup screen or section:
  - Back up now
  - Restore selected backup
  - Open backup folder
  - Retention / cleanup controls
- clearer action/activity view:
  - installs / uninstalls
  - apply / restart actions
  - hosted uploads / deletes
  - backup / restore actions
  - launch events where possible
- move or demote the large technical log out of the main Mods workspace

### 6. Framework & Dependency Awareness

Add a lightweight framework/runtime understanding layer.

Must include:

- detect likely framework/runtime archives such as UE4SS-style installs
- show a framework/runtime badge or category
- distinguish likely destinations:
  - framework/runtime files under locations like `R5\Binaries\Win64`
  - pak mods under `~mods`
- warn when an archive likely depends on a missing framework/runtime
- conservative detection only; do not pretend dependency support is perfect

### 7. Profiles (Narrow First Version)

Profiles should exist in v0.5.0, but narrowly.

Must include:

- save current state as profile
- compare profile to current state
- apply profile
- delete profile
- profile content:
  - selected mods
  - selected variants
  - target choices
  - optional server settings snapshot
  - optional world settings snapshot

Safety rules:

- compare before apply is mandatory
- no silent mass replacement
- no credentials or secrets inside profiles

## Cut If Needed

These can move to `v0.5.1` if scope grows too much:

### A. Richer Metadata Editing

- inline metadata editing everywhere
- more advanced source/author fields
- better bulk metadata tools

### B. Selected-Child Uninstall

- keep whole-bundle uninstall if child-safe uninstall becomes too messy

### C. Advanced Activity Timeline Polish

- export
- filters
- richer grouping
- search beyond basic text filtering

### D. Profile Settings Snapshots

- if profile settings integration gets risky, ship profile mod-state first
- move settings snapshots to `v0.5.1`

### E. Hosted Connection Status Depth

- basic connected/offline/not configured is must-have
- deeper hosted health checks can move later

## Explicitly Deferred

- parity/share-code workflow
- Nexus auto-download
- FTP support
- full auto-update system
- full profile/loadout ecosystem
- SteamCMD/server installer ownership
- multi-game extraction

## Architecture / Data Changes

### Metadata model

Add a small metadata structure for archives/installs.

Possible fields:

- `nexus_mod_url`
- `nexus_mod_id`
- `nexus_file_id`
- `version_tag`
- `source_label`

Compatibility rule:

- all metadata fields must be optional
- missing metadata must not break older manifests or archive records

### Profiles model

Add a profile model/store with:

- profile id
- name
- notes
- target-aware desired entries
- optional settings snapshots

Compatibility rule:

- no secrets
- machine-specific credentials stay outside profiles

### Activity / backup presentation

Prefer presentation-layer changes over backup-engine rewrites.

Goal:

- keep existing backup/recovery internals stable
- improve how they are grouped and surfaced in the UI

## Likely Files / Systems Affected

### UI

- `windrose_deployer/ui/app_window.py`
- `windrose_deployer/ui/tabs/mods_tab.py`
- `windrose_deployer/ui/tabs/server_tab.py`
- `windrose_deployer/ui/tabs/settings_tab.py`
- `windrose_deployer/ui/tabs/about_tab.py`
- `windrose_deployer/ui/widgets/status_panel.py`

Likely additions:

- new dashboard widget/frame
- new inspect modal/drawer widget
- profile management dialog/panel
- metadata editor surface
- activity/history view

### Core

- `windrose_deployer/core/archive_inspector.py`
- `windrose_deployer/core/deployment_planner.py`
- `windrose_deployer/core/installer.py`
- `windrose_deployer/core/integrity_service.py`
- `windrose_deployer/core/recovery_service.py`
- `windrose_deployer/core/server_sync_service.py`
- `windrose_deployer/core/server_config_service.py`
- `windrose_deployer/core/world_config_service.py`
- `windrose_deployer/core/remote_deployer.py`
- `windrose_deployer/core/remote_config_service.py`

Likely additions:

- metadata service/store helpers
- profile store/service
- framework/dependency detector
- activity feed builder

### Models

- `windrose_deployer/models/mod_install.py`
- `windrose_deployer/models/deployment_record.py`
- archive library record model if present

Likely additions:

- metadata model
- profile model

## Implementation Slices

## Slice 1 - Metadata & Model Foundations

Goal:

- add optional metadata fields
- add profile data model/store
- keep load compatibility

Tasks:

- extend install/archive state with optional metadata
- add backward-compatible serialization
- add profile model + storage
- add migration/load tests

Acceptance:

- old data still loads
- new metadata fields are optional
- profiles can be saved/loaded without touching install logic yet

## Slice 2 - Inspect & Bundle UX

Goal:

- make archive inspection usable
- make modular bundles understandable

Tasks:

- implement new inspect drawer/modal
- show child pak/file items
- support bundle-level and selected-child planning
- improve archive/applied card expansion

Acceptance:

- a modular archive is understandable at default window size
- users can clearly choose whole-bundle vs selected-child install

## Slice 3 - Framework & Dependency Awareness

Goal:

- make UE4SS/framework-style content visible and less error-prone

Tasks:

- detect likely framework/runtime packages
- add framework badges/categories
- show likely install destination clearly
- warn on likely missing dependency

Acceptance:

- framework-like archives are not presented as plain pak mods
- dependent mods surface a useful warning when likely missing a framework

## Slice 4 - Server Dashboard

Goal:

- give users one clear server operations overview

Tasks:

- add dashboard cards/summary section
- wire local/dedicated running state
- wire hosted connected/offline/not configured state
- show active world/source summary
- add quick actions

Acceptance:

- users can tell server state without switching across several screens

## Slice 5 - Backups & Activity

Goal:

- move operational feedback out of the crowded Mods workspace

Tasks:

- demote or relocate technical log from Mods
- add activity/history surface
- improve backup actions/labels/retention controls
- connect history to install/apply/upload/restore actions

Acceptance:

- Mods screen is no longer dominated by the technical log
- users can review recent operational actions in a dedicated surface

## Slice 6 - Profiles

Goal:

- introduce narrow, safe saved-state profiles

Tasks:

- save current state as profile
- compare profile to current
- preview apply
- apply profile
- optional settings snapshot support if still in scope

Acceptance:

- a user can save and re-apply a named setup safely
- profile apply always shows intended changes first

## Slice 7 - Version Signals

Goal:

- use metadata to make updates easier to reason about

Tasks:

- surface local "possible update available" hints
- compare imported archives against installed metadata
- optionally query upstream metadata when enough fields exist

Acceptance:

- users can tell when an imported archive likely supersedes an installed one
- the app does not claim certainty where it only has heuristics

## Recommended Build Order

1. Slice 1 - Metadata & Model Foundations
2. Slice 2 - Inspect & Bundle UX
3. Slice 3 - Framework & Dependency Awareness
4. Slice 4 - Server Dashboard
5. Slice 5 - Backups & Activity
6. Slice 6 - Profiles
7. Slice 7 - Version Signals

Reasoning:

- metadata and profiles need stable storage first
- inspect/bundle changes unblock the hardest mod UX issue early
- framework awareness should shape later presentation decisions
- dashboard and activity come after the data surfaces are clearer
- version signals should sit on top of metadata, not be built first

## Test / Validation Plan

### Must-have automated coverage

- backward-compatible metadata serialization/loading
- profile save/load/apply comparison logic
- bundle planning for whole-bundle and selected-child actions
- framework detection heuristics
- update-signal logic for newer imported archives
- activity/recovery presentation rules where practical

### Must-have manual smoke tests

- inspect a large bundle archive at default window size
- install whole bundle
- install selected child items
- install a likely framework/runtime archive
- see dependency warning on a dependent archive
- save current setup as profile
- compare and apply a profile
- run backup now / restore / cleanup
- review activity timeline after installs, apply, restart, hosted upload/delete
- verify dashboard shows correct local/dedicated/hosted state

## Release Criteria

Ship `v0.5.0` only when:

- inspect is clearly usable at default window size
- metadata fields are stable and backward compatible
- framework/runtime installs are clearly distinguished
- dashboard state is understandable
- backups/activity no longer feel secondary
- profiles are safe and preview-based

If profiles or settings snapshots begin to destabilize the release, cut settings snapshots first, then move part of Profiles to `v0.5.1`.


