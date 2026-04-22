# Windrose Mod Manager - v0.5.2 Implementation Brief

## Release Goal

**v0.5.2 should make the app feel more trustworthy and more self-explanatory in day-to-day use, without widening scope into another major subsystem release.**

This pass is about **operator polish + trust**:

- Dashboard should feel more in control of parity and attention state
- Activity / Backups copy and behavior should match the actual information architecture
- manifest drift should be surfaced to normal users, not only power users reading logs
- hosted setup should be clearer for the two real provider paths you now support:
  - Host Havoc
  - Indifferent Broccoli
- startup and tab performance should be improved before the larger `0.6.0` UE4SS work lands
- the largest UI files should be lightly decomposed where it lowers `0.6.0` regression risk

This release should **not** become:

- a full server control panel
- a full metadata/version-awareness release
- a credentials/security overhaul
- a full UI rewrite or large tab-splitting refactor
- FTPS support unless a concrete provider forces it
- UE4SS implementation work, except for planning/compatibility prep

## Current State After v0.5.1

The following are already shipped and should **not** be re-planned as v0.5.2 goals:

- Dashboard parity checks now run in place
- `Open Full Compare` exists as a separate action
- raw backup copies already support:
  - `Delete Selected`
  - `Delete All`
- raw backup rows are already lazy-loaded behind the advanced section
- hosted profiles already support:
  - `sftp`
  - `ftp`
- provider-aware protocol plumbing already exists through:
  - `RemoteProfile.protocol`
  - `create_remote_provider()`
  - `FtpProvider`
  - protocol-aware remote config / recovery identity

So `v0.5.2` should focus on the remaining polish gaps, not duplicate work already done in `v0.5.1`.

## Core Problems To Solve

### 1. Dashboard still depends too much on Server-tab state

Right now the Dashboard parity action uses the currently active source selected in `Server`.

That means:

- the user cannot clearly choose the compare target from the Dashboard itself
- the Dashboard feels partially dependent on another tab's hidden state

`v0.5.2` should let Dashboard own that choice more explicitly.

### 2. Important attention signals still live only in logs

Manifest drift currently logs warnings, but does not visibly surface in the main UI.

That means:

- users can have a real integrity problem
- but only discover it by reading the technical log

That undercuts the product goal of being a safe cockpit.

### 3. Copy still uses the old "Recovery" mental model in places

The current app surface is `Activity`, with backups inside it, but parts of the UI still say:

- `Recovery`
- `Open Recovery`
- `Recovery Center`

That creates unnecessary friction and makes the IA feel less intentional.

### 4. Activity can still feel heavy with larger histories

Raw backups are already lazy, but the main timeline still does a full rebuild and can feel slow once the history grows.

`v0.5.2` should improve this without redesigning the whole screen.

### 5. Hosted setup is correct, but still support-ticket prone

The protocol plumbing is now there, but support friction remains around:

- choosing the right provider mode
- understanding Host Havoc's split FTP/SFTP reality
- understanding Indifferent Broccoli's FTP path
- recognizing timeout / listing / reconnect issues in a user-friendly way

### 6. Startup and large-tab cost are still pre-0.6 risks

The largest UI files remain:

- `windrose_deployer/ui/tabs/mods_tab.py` at roughly 3.7k lines
- `windrose_deployer/ui/tabs/server_tab.py` at roughly 2.1k lines
- `windrose_deployer/ui/app_window.py` at roughly 800+ lines

The current lazy behavior is mostly refresh-lazy, not construction-lazy. The app still builds all major tab widgets at startup.

That matters because `0.6.0` UE4SS support will touch the heaviest surface, especially Mods and Server. A small performance/refactor pass now lowers risk later.

## Final Scope

## Must-Have

### 1. Dashboard Compare Target Control

Add explicit compare-source/target control directly to Dashboard.

Must include:

- a small target selector on Dashboard parity card
  - `Local Server`
  - `Dedicated Server`
  - `Hosted Server`
- `Run Compare` should use the Dashboard selection, not hidden Server-tab state
- `Open Full Compare` should still open the Server tab, but it should first sync the Server target to the Dashboard selection
- parity summary text should clearly say what was compared
  - example: `Client vs Dedicated Server`

Important:

- do not create a separate second source-of-truth model if it can be avoided
- Dashboard should drive the existing Server compare state, not fork it

Acceptance:

- a user can choose compare target directly from Dashboard
- compare results are predictable without first visiting Server
- detailed compare still opens in the right source context

### 1b. Guided Dashboard Sync Actions

Add a conservative `Review Sync Actions` flow after Dashboard compare.

Must include:

- show the action only after a compare has found actionable differences
- preview directional actions instead of offering a generic one-click `Sync`
- supported first-pass actions:
  - `Install missing client mods to Local Server`
  - `Install missing client mods to Dedicated Server`
  - `Upload missing client mods to Hosted Server`
  - `Review server-only removals`
- deletion/removal actions must be separate, clearly labeled, and unchecked by default
- hosted upload actions are allowed only for archive-backed/client-managed mods where the source archive still exists
- show target, mod name, source archive, and expected destination before applying
- execute through existing install/upload services so backups/history remain intact

Important:

- do not silently make targets match
- do not delete server-only mods as part of a default sync
- do not invent hosted uploads for unmanaged or missing-source mods
- if conflicts or variants are involved, force the user into the detailed review path

Acceptance:

- Dashboard can turn a clean compare result into a safe action preview
- users can install/upload missing client-side managed mods to the selected server target without manually re-finding every archive
- risky removals and ambiguous actions require explicit review

### 2. Surface Manifest Drift In The UI

Make drift visible outside the log.

Must include:

- a Dashboard attention state when manifest drift exists
- a compact visible signal such as:
  - `Drift detected`
  - `Review recommended`
  - `X managed mods changed outside the manager`
- a path from that signal to the right place:
  - `Mods`
  - `Activity`
  - or a focused integrity/details action

Important:

- keep the existing background scan
- do not block startup to compute drift
- do not spam modal popups

Acceptance:

- users can see drift without opening the technical log
- the signal is concise and actionable

### 3. Copy / IA Consistency Pass

Align the product language with the actual current tab structure.

Must include:

- replace stale `Recovery` references where the real destination is `Activity`
- update labels/buttons/help text such as:
  - welcome dialog
  - About / Help tips
  - Settings backup/help copy
  - any `Open Recovery` / `Open Recovery Center` wording that should now be `Open Activity` or `Open Activity & Backups`
- keep user-facing wording consistent across:
  - Activity
  - backups
  - restore
  - undo

Important:

- preserve the recovery concept, but present it inside the `Activity` IA
- avoid renaming underlying service/module classes unless necessary

Acceptance:

- users do not have to guess whether `Recovery` is a separate tab
- tab labels and help text match the visible navigation

### 4. Activity Performance Pass

Make Activity feel lighter on larger histories without redesigning the whole tab.

Must include:

- reduce full timeline rebuild cost where possible
- avoid re-rendering unchanged detail panes unnecessarily
- keep raw backup browser lazy as it already is
- consider a practical first-pass limit or chunked render for timeline rows if needed

Preferred implementation direction:

- preserve the current screen structure
- improve rendering behavior rather than redesigning the workflow
- profile before changing behavior too much

Acceptance:

- Activity opens and refreshes more smoothly on large histories
- no functional regressions in restore / undo / raw backup actions

### 5. Hosted Provider QoL

Make hosted setup more self-explanatory for the real providers now supported.

Must include:

- short provider hint rows or compact helper blocks for:
  - Host Havoc
  - Indifferent Broccoli
- quick-fill defaults or presets that are **explicit**, not auto-detected:
  - Host Havoc `SFTP` preset
  - Host Havoc `FTP` preset
  - Indifferent Broccoli `FTP` preset
- preset behavior should only set safe obvious defaults:
  - protocol
  - default port
  - auth mode where relevant
- preserve manual edits and explicit user-entered ports

Important:

- this is provider guidance, not provider detection
- do not hardcode paths or invent magic behavior

Acceptance:

- a user can choose a known provider path quickly
- the setup flow reduces support confusion without becoming a provider platform

### 6. FTP Diagnostics / Reliability Polish

Tighten error handling around common FTP failure modes.

Must include:

- clearer error translation for:
  - protocol mismatch
  - auth failure
  - path/listing failure
  - timeout / dropped connection where detectable
- better wording when listing falls back from `MLSD`
- reconnect guidance where the failure is likely transient

Important:

- do not promise active/passive mode UI unless testing proves it is required
- keep the interface simple until a real provider case needs more knobs

Acceptance:

- hosted FTP failures are easier to understand
- support issues can be diagnosed from the in-app message more easily

### 7. Startup Performance And Lazy Tab Construction

Improve startup before `0.6.0`.

Implementation note after the v0.5.2 pass:

- v0.5.2 reduced refresh fan-out and Activity timeline render cost safely
- true construction-lazy tab loading was intentionally deferred
- reason: Dashboard, Mods, and Server still have direct cross-tab calls, so making those tabs construction-lazy without first extracting a small coordinator/helper seam would create avoidable startup and first-open race risks
- recommended follow-up: make this a dedicated `v0.5.3` or early `v0.6` prep task before adding UE4SS/load-order UI

Must include:

- true lazy construction for non-default heavy tabs where practical:
  - Mods
  - Server
  - Activity
  - Settings if low risk
- Dashboard should remain the default first constructed/visible tab
- non-visible tabs should be built on first open, not all during startup
- keep existing service initialization stable
- avoid duplicate refresh storms when a tab is created for the first time
- keep startup timing logs so improvements are measurable

Important:

- do not make the UI appear broken while a tab is first-created
- do not defer data loading so aggressively that user actions race with missing widgets
- prefer a small tab factory/cache over a large scheduler framework

Acceptance:

- cold launch gets visibly faster
- opening a heavy tab for the first time may do work, but it should happen after the main window is usable
- tests and manual smoke show no tab refresh regressions

### 8. Pre-0.6 UI Decomposition

Lightly split the heaviest UI files where it directly reduces upcoming UE4SS risk.

This is not a rewrite.

Recommended extraction targets from `mods_tab.py`:

- install preset / context-menu helpers
- archive/applied card data helpers
- selection state helpers
- metadata editor/dialog helpers
- live inventory grouping helpers

Recommended extraction targets from `server_tab.py`:

- hosted setup panel helpers
- source/target selection helpers
- compare/sync helpers
- dashboard source bridge helpers

Rules:

- preserve behavior first
- extract pure/helper logic before widget-heavy code
- avoid broad renames
- keep diffs reviewable
- add tests for extracted non-UI logic where practical

Acceptance:

- UE4SS work has clear places to add classification/planning/status logic
- Mods and Server tabs are less risky to modify
- no behavior change beyond measured performance/maintainability improvements

### 9. Compatibility Fixture Expansion

Add fixtures before `0.6.0` introduces new install kinds or generated-output state.

Must include fixtures for:

- current `0.5.1` settings
- current app state with metadata fields
- FTP hosted profile
- SFTP hosted profile
- profile/store state if present
- large-ish manifest/history sample for Activity performance testing

Purpose:

- protect old data when `0.6.0` adds UE4SS install kinds
- protect future generated tweak output schema changes
- make startup/activity performance tests more realistic

Acceptance:

- old fixtures still load
- new fixtures load
- compatibility tests make future schema changes safer

## Should-Have

### 10. Documentation / Hygiene Cleanup

Clean up small consistency issues found in review.

Recommended:

- fix README log filename drift:
  - docs say `windrose_deployer.log`
  - code writes `deployer.log`
- update the package docstring in `windrose_deployer/__init__.py` so it reflects the hosted/server scope more accurately
- refresh roadmap wording so the current release sections no longer read as if `v0.2.0` is still current

Acceptance:

- docs no longer contradict the shipped behavior in obvious places

## Cut If Needed

These can move to `0.5.3` or `0.6` if the polish pass starts to grow:

### A. Broad UI Decomposition

- full `ModsTab` rewrite
- full `ServerTab` rewrite
- widget-heavy presenter extraction

For `0.5.2`, keep only narrow helper extraction if the refactor starts to expand.

### B. FTP Advanced Options

- passive/active mode toggle
- reconnect interval controls
- advanced listing mode controls

Only add these if a real provider/test case proves they are needed.

### C. Support Bundle Export

Useful, but cuttable if the UI polish work already fills the release.

### D. Rich Dashboard Attention Center

- multi-alert banners
- dedicated integrity details panel
- alert history

For `0.5.2`, a compact signal is enough.

## Explicitly Deferred To v0.6+

- DPAPI / Windows Credential Manager / keychain secret protection
- SSH host-key verification / fingerprint pinning
- deep tab/module rewrite beyond the narrow pre-0.6 helper extraction
- metadata/version-awareness foundation
- dependency/framework surfacing expansion
- FTPS unless a named provider requires it
- UE4SS runtime/mod installation
- configurable tweak-builder UI or asset patching

## Architecture / Data Rules

### Dashboard compare ownership

The Dashboard compare selector should reuse the existing server source model rather than inventing a second parallel state system.

Recommended approach:

- Dashboard stores a small UI selection
- compare execution routes through `ServerTab`
- opening full compare synchronizes `ServerTab` to the same target

### Drift visibility

Do not change manifest or integrity storage shape for this release.

Preferred approach:

- keep the current drift scan
- store only a lightweight summary in UI state if needed
- do not introduce a new persistent schema unless clearly necessary

### Activity performance

Do not replace the entire Activity screen.

Preferred approach:

- optimize refresh and row rendering
- keep restore/undo semantics unchanged

### Provider presets

Provider presets should be UI helpers only.

They should **not**:

- imply an official provider integration
- auto-detect hosts
- overwrite explicit user input unexpectedly

## Likely Files / Systems Affected

### UI

- `windrose_deployer/ui/tabs/dashboard_tab.py`
- `windrose_deployer/ui/tabs/server_tab.py`
- `windrose_deployer/ui/tabs/backups_tab.py`
- `windrose_deployer/ui/tabs/about_tab.py`
- `windrose_deployer/ui/tabs/settings_tab.py`
- `windrose_deployer/ui/app_window.py`

### Core

- `windrose_deployer/core/integrity_service.py`
- `windrose_deployer/core/ftp_provider.py`
- `windrose_deployer/core/remote_deployer.py`
- `windrose_deployer/core/remote_config_service.py`

### Docs / release planning

- `README.md`
- `ROADMAP.md`
- `PLAN_v0.5.x.md`

## Implementation Slices

## Slice 1 - Copy and IA Consistency

Goal:

- remove stale `Recovery` wording and align help text with the actual `Activity` tab

Tasks:

- update welcome copy
- update About / Help copy
- update Settings backup/help copy
- update button labels that still imply a missing Recovery tab

Acceptance:

- the app's copy matches the visible navigation

## Slice 2 - Dashboard Compare Target Control

Goal:

- make Dashboard parity self-contained

Tasks:

- add explicit compare target selector
- route compare through that selector
- sync `Open Full Compare` to the same target
- update parity summary wording
- add `Review Sync Actions` for safe missing-client-to-server actions after compare
- keep removals separate and unchecked by default

Acceptance:

- Dashboard no longer depends on hidden Server-tab source state
- Dashboard can preview install/upload sync actions without doing blind sync

## Slice 3 - Manifest Drift Visibility

Goal:

- surface integrity attention in the UI

Tasks:

- expose drift summary to Dashboard
- add compact attention state / message
- add a clear navigation path to inspect/fix

Acceptance:

- drift is visible without opening the log

## Slice 4 - Activity Performance

Goal:

- make Activity feel lighter on large histories

Tasks:

- profile refresh path
- reduce redundant row rebuilds
- keep selection/detail state stable where practical
- add a pragmatic first-pass rendering optimization if needed

Acceptance:

- Activity feels smoother without workflow changes

## Slice 5 - Hosted Provider QoL

Goal:

- reduce hosted support friction

Tasks:

- add provider hint rows / quick presets
- preserve explicit user values
- improve FTP failure wording and reconnect guidance

Acceptance:

- Host Havoc and Indifferent Broccoli setup is more self-explanatory

## Slice 6 - Docs / Hygiene Cleanup

Goal:

- remove obvious doc drift

Tasks:

- fix README log filename note
- update package-level docstring
- refresh roadmap wording where it is now misleading

Acceptance:

- docs better match shipped behavior

## Slice 7 - Startup Performance / Lazy Construction

Goal:

- make the main window usable faster and reduce pre-0.6 startup risk

Tasks:

- introduce a small tab factory/cache in `app_window.py`
- construct Dashboard first
- construct heavy tabs on first open:
  - Mods
  - Server
  - Activity
  - Settings if low risk
- ensure first-open refresh runs once
- keep startup timing logs around construction and first-open refresh

Acceptance:

- startup timing is improved or at least clearly diagnosable
- no tab opens into an uninitialized/broken state

## Slice 8 - Pre-0.6 Helper Extraction

Goal:

- lower risk before UE4SS changes touch Mods and Server

Tasks:

- extract narrow pure/helper logic from `mods_tab.py`
- extract narrow pure/helper logic from `server_tab.py`
- prefer helpers that UE4SS will reuse:
  - install kind/classification helpers
  - target/source helpers
  - menu/action helper construction
  - live inventory grouping helpers
- add unit tests where helpers are non-UI

Acceptance:

- no behavior change
- future UE4SS install planning has clearer integration points

## Slice 9 - Compatibility Fixtures

Goal:

- protect existing state before `0.6.0` schema changes

Tasks:

- add current FTP profile fixture
- add app-state fixture with metadata
- add profile/store fixture if present
- add larger activity/history fixture
- add tests that old and new fixtures load

Acceptance:

- future install-kind/generated-output changes have compatibility coverage

## Recommended Build Order

1. Slice 0 - Release-blocking startup crash fix, if not already released
2. Slice 1 - Copy and IA Consistency
3. Slice 2 - Dashboard Compare Target Control
4. Slice 3 - Manifest Drift Visibility
5. Slice 4 - Activity Performance
6. Slice 7 - Startup Performance / Lazy Construction
7. Slice 8 - Pre-0.6 Helper Extraction
8. Slice 9 - Compatibility Fixtures
9. Slice 5 - Hosted Provider QoL
10. Slice 6 - Docs / Hygiene Cleanup

Reasoning:

- copy and compare control are quick wins with high UX value
- drift visibility is an important trust improvement
- Activity and startup optimization are safer once the UI wording is settled
- helper extraction should happen before UE4SS work starts, but stay narrow
- compatibility fixtures should exist before `0.6.0` adds new install kinds
- provider presets/diagnostics build on the stable `0.5.1` hosted transport layer

## Test / Validation Plan

### Must-have automated coverage

- inaccessible/missing Steam library paths do not crash startup discovery
- Dashboard compare target selection routes to the correct server source
- `Open Full Compare` synchronizes to the right target
- Dashboard `Review Sync Actions` builds only safe, directional install/upload actions
- Dashboard sync preview does not include default checked delete actions
- hosted sync actions skip unmanaged or missing-source mods
- manifest drift summary state is computed/surfaced correctly
- Activity refresh optimizations preserve:
  - restore
  - undo
  - raw backup delete selected/delete all
- lazy tab construction does not skip first-open refresh
- extracted helper logic preserves existing install/source behavior
- compatibility fixtures load for:
  - old SFTP profiles
  - FTP profiles
  - app state with metadata
  - large activity/history data
- provider presets apply only expected defaults
- FTP diagnostic translation stays stable

### Must-have manual smoke tests

- cold startup with a stale/missing Steam library drive path
- cold startup timing before/after lazy construction
- first open of Mods, Server, Activity, and Settings
- welcome/help/settings copy no longer tells users to open a non-existent Recovery tab
- Dashboard compare can switch between:
  - Local Server
  - Dedicated Server
  - Hosted Server
- `Run Compare` updates the parity card for the selected target
- `Open Full Compare` opens Server with the same target active
- `Review Sync Actions` previews missing client mods for Local Server / Dedicated Server / Hosted Server
- server-only removals are shown separately and require explicit user selection
- drift warning appears on Dashboard after simulated out-of-band managed-file change
- Activity remains responsive with a large manifest/history set
- raw backup delete selected/all still works
- Host Havoc quick preset path:
  - FTP preset
  - SFTP preset
- Indifferent Broccoli quick preset path:
  - FTP + port 21
- explicit user-entered port survives preset use and save/load

### Pre-0.6 manual checks

- normal pak install/uninstall still works after helper extraction
- hosted FTP/SFTP install/delete still works after lazy tab construction
- Mods tab context menus still behave the same
- Server tab local/dedicated/hosted source switching still behaves the same
- packaged EXE still starts and opens all tabs

## Release Criteria

Ship `v0.5.2` only when:

- Dashboard parity control is self-explanatory
- guided sync actions are preview-first and do not perform blind deletes
- manifest drift is visible outside the technical log
- Activity feels lighter on larger histories
- main window is usable faster, or timing logs clearly show where remaining startup cost lives
- pre-0.6 helper extraction does not change behavior
- compatibility fixtures cover the state shapes likely to be affected by `0.6.0`
- hosted setup is clearer for real provider paths
- no `0.5.1` FTP/SFTP compatibility regressions are introduced

If provider-specific preset UX, FTP diagnostics, or helper extraction begins to expand too far, ship the crash fix plus copy/dashboard/drift/performance work first and defer the deeper provider or refactor polish to `0.5.3`.

## Implementation Result

Shipped for `v0.5.2`:

- Dashboard compare target selector for Local Server, Dedicated Server, and Hosted Server
- Dashboard compare updates the parity card for the selected target without forcing a tab jump
- `Open Full Compare` keeps the selected target in sync with the Server tab
- `Review Sync Actions` previews safe client-to-server actions after compare
- Local Server and Dedicated Server sync actions use the existing install, backup, and history path
- Hosted sync actions use the existing hosted deployment path
- server-only and hosted-only removals are listed for review and are not auto-applied
- manifest drift is stored on the app and surfaced on Dashboard
- Activity / Backups copy replaces stale Recovery wording
- Activity timeline render is capped for large histories and raw backup rendering remains behind the advanced section
- Activity refresh fan-out is reduced when the tab has not been loaded
- startup/discovery no longer fatally fails on inaccessible saved Steam paths
- FTP path checks fall back to parent listing when `SIZE` is unsupported
- hosted path errors explain FTP-root-relative paths, including Nitrado-style setups
- Host Havoc and Indifferent Broccoli provider shortcuts remain in Hosted Setup
- Dashboard status coloring correctly treats `Not running` as neutral instead of healthy
- failed hosted Dashboard sync no longer records a successful upload action

Deferred:

- true construction-lazy tab creation because Dashboard, Mods, and Server still have direct cross-tab dependencies
- broad Mods/Server UI decomposition
- richer metadata/version editing
- automatic per-mod update checks/downloads

Validation:

- `python -m compileall windrose_deployer`
- `python -m pytest -q --basetemp .pytest_tmp_full_052_release -o cache_dir=.pytest_cache_full_052_release` -> `171 passed`
- `git diff --check` -> clean except normal CRLF warnings
