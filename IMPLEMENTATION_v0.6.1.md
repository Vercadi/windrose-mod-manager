# Windrose Mod Manager - v0.6.1 Implementation Plan

`v0.6.1` started as a narrow patch release focused on fixing framework lifecycle regressions introduced or exposed by `v0.6.0`.

Implementation note:

- the final pass also pulled forward the safest local framework-management pieces from the broader `0.6.x` plan
- hosted framework launch/rebuild and live RCON admin/test commands remain deferred
- normal pak install/uninstall behavior must remain unchanged

The primary goal is simple:

- uninstalling `UE4SS` runtime or `UE4SS` mods should return their source archive to `Inactive Mods` when the last active install is removed
- uninstall/install/remove actions that affect framework state should refresh the Dashboard immediately and correctly

This is primarily a lifecycle-correctness and trust patch with local UE4SS/RCON/WindrosePlus management affordances.

---

## Scope

### Must fix

1. `UE4SS` runtime uninstall should restore the archive lifecycle correctly
   - if the user imported a source archive and installed it
   - and the last active install for that archive is uninstalled
   - the source archive should appear in `Inactive Mods` again

2. `UE4SS` mod uninstall should do the same
   - folder-style `ue4ss\Mods\<ModName>` installs must behave like normal managed installs in the active/inactive workspace
   - uninstalling the last active target should make the original source archive visible in `Inactive Mods`

3. Dashboard framework state must refresh after lifecycle actions
   - uninstalling `UE4SS` runtime must update the `Frameworks` card immediately
   - uninstalling `UE4SS` mods must update the `Frameworks` card immediately
   - related actions that change framework state should not require tab switching or app restart before Dashboard is correct

4. Audit all framework uninstall entry points
   - row uninstall
   - bulk uninstall
   - selected component uninstall where applicable
   - reinstall path that first uninstalls
   - hosted remove path only if it touches framework state in the same workspace

5. Tighten server-only framework install guardrails
   - keep `WindrosePlus` blocked from `Client` targets
   - also block likely `RCON` framework mods from `Client` targets
   - hide or disable invalid `Client` / `Client + ...` presets for server-only framework packages where practical
   - keep generic `UE4SS` mods client-installable only when they are not detected as `RCON` or `WindrosePlus`

6. Make imported archives manager-owned by default
   - when a user drags/drops or adds `.zip`, `.7z`, or `.rar`, copy the archive into the manager archive library folder
   - register the copied file as the source archive instead of the browser downloads path
   - keep the original file untouched
   - reuse an existing library copy when the same archive/hash is already present
   - keep loose `.pak/.utoc/.ucas` drops using the generated bundle behavior

7. Add a lightweight Dashboard refresh action
   - add a small `Refresh` button to the Dashboard header
   - refresh Dashboard state, framework state, mod counts, and visible attention indicators
   - do not run hosted connection tests from this button
   - optionally show a simple `Last refreshed` timestamp if it does not clutter the card layout

### Still deferred

- live RCON test/admin commands
- hosted WindrosePlus shell/rebuild execution
- arbitrary framework folder editing
- broader dashboard redesign
- startup/performance refactors unless directly required to make framework state correct

---

## Current symptoms to address

### 1. Framework source archives do not reliably re-enter `Inactive Mods`

The normal inactive list depends on library entries plus manifest state:

- a source archive remains in the archive library
- it appears as inactive when no managed installs still reference it

`v0.6.1` should verify that framework installs follow the same rule as standard pak installs.

Likely risk areas:

- framework install kinds may not reconcile cleanly with archive-library visibility after uninstall
- component or grouped uninstall paths may leave manifest/library state out of sync
- uninstall may remove the managed record correctly but still fail to make the archive visible in the inactive filter/view immediately

### 2. Dashboard framework state does not reliably refresh after uninstall

The Dashboard reads framework state from filesystem-backed detection.

`v0.6.1` should verify that all uninstall flows which remove framework files:

- trigger the app-level refresh path
- refresh the Dashboard after the filesystem changes are complete
- do not leave stale framework state visible until another manual refresh/tab change occurs

### 3. Imported archive source paths are fragile

Today, dropped Nexus downloads may remain tied to the original browser downloads path.

That creates avoidable missing-source issues when users clean `Downloads`, move archives, or try to reinstall/repair/profile-apply later.

`v0.6.1` should make the manager's archive library own imported archives by default.

### 4. Dashboard needs a manual refresh affordance

Framework state can change outside the manager when users run WindrosePlus installers, delete files in Explorer, rebuild generated PAKs, or manually repair UE4SS files.

`v0.6.1` should add a small Dashboard refresh action so users can re-read local operational state without switching tabs or restarting the app.

---

## Implementation Slices

### Slice 1 - Framework Archive Lifecycle Audit

Goal:
Verify how `UE4SS` runtime/mod installs move between `Active Mods` and `Inactive Mods`.

Tasks:

- audit how framework installs are represented in:
  - archive library entries
  - manifest mod records
  - active/inactive filtering
- compare framework uninstall behavior against normal pak uninstall behavior
- confirm whether the issue is:
  - missing library entry reuse
  - stale UI refresh
  - lingering manifest references
  - install-kind-specific filtering

Acceptance:

- after uninstalling the last active target for a `UE4SS` runtime archive, the archive appears in `Inactive Mods`
- after uninstalling the last active target for a `UE4SS` mod archive, the archive appears in `Inactive Mods`

### Slice 2 - Uninstall Path Corrections

Goal:
Make framework uninstall semantics consistent across all uninstall entry points.

Tasks:

- audit and normalize:
  - single uninstall
  - bulk uninstall
  - selected component uninstall
  - reinstall flow
- ensure framework installs do not leave behind stale active state when the last managed target is removed
- ensure source archive association remains intact for re-entry into `Inactive Mods`
- ensure server-only framework packages do not offer misleading client install actions

Acceptance:

- all uninstall entry points produce the same archive lifecycle result for framework installs
- no uninstall path leaves a framework archive stranded outside both `Active Mods` and `Inactive Mods`
- `WindrosePlus` and `RCON` do not install to `Client` targets from any normal preset path

### Slice 3 - Dashboard Refresh Correctness

Goal:
Make Dashboard framework state immediately reflect lifecycle changes.

Tasks:

- verify app-level refresh helpers after uninstall/install/remove flows
- ensure Dashboard refresh happens after the actual filesystem state is changed
- add a manual Dashboard `Refresh` button that calls the same local refresh path
- audit whether framework state detection is re-read on refresh for:
  - client
  - local server
  - dedicated server
- only extend hosted refresh if hosted framework removal is intended to affect the same Dashboard state model
- avoid implicit hosted connection tests from Dashboard refresh

Acceptance:

- uninstalling `UE4SS` runtime updates Dashboard framework state immediately
- uninstalling `UE4SS` mods updates Dashboard framework state immediately
- clicking Dashboard `Refresh` re-reads local framework state and mod counts
- no tab switch or app restart is needed for the Dashboard to become correct

### Slice 4 - Regression Tests

Goal:
Protect the framework lifecycle behavior so `0.6.x` does not regress again.

Tasks:

- add/extend tests for:
  - framework archive becoming inactive again after last uninstall
  - framework uninstall removing final manifest reference correctly
- dashboard/framework refresh helper coverage where practical
  - Dashboard manual refresh behavior where practical
  - `WindrosePlus` and `RCON` client-target rejection
  - imported archive copy/reuse behavior
- prefer focused service/UI logic tests over brittle full-UI automation

Acceptance:

- automated coverage exists for the archive lifecycle regression
- automated coverage exists for the uninstall path that previously regressed

### Slice 5 - Archive Library Ownership

Goal:
Make `Inactive Mods` source files reliable by copying imported archives into the manager library.

Tasks:

- choose/use a stable archive-library folder under the app data directory
- on archive import, copy supported archive files into that folder
- hash before/after or otherwise detect duplicates so repeated imports do not create noisy copies
- update archive library entries to point at the manager-owned copy
- preserve existing library entries that still point to external files, but new imports should use the managed copy
- keep generated loose-pak bundle imports working as they do today

Acceptance:

- dragging a Nexus zip from `Downloads` creates/uses a copy in the manager archive library
- deleting the original file from `Downloads` does not break reinstall, repair, or inactive-mod display
- importing the same archive twice reuses the existing manager-owned copy

### Slice 6 - Local Framework Management Surface

Goal:
Expose safe, known framework actions without turning the app into a server panel.

Tasks:

- add Dashboard `Manage Frameworks`
- show UE4SS / RCON / WindrosePlus sections by local target
- edit known config files with backups only
- expose RCON fields as port/password/enabled
- add WindrosePlus install, dashboard, config, launch-wrapper, and rebuild actions for local/dedicated Windows targets
- require confirmation before running WindrosePlus scripts

Acceptance:

- users can manage known framework files without browsing folders manually
- no arbitrary file editor is exposed
- live RCON admin/test commands remain deferred

---

## Likely Files / Systems

UI:

- `windrose_deployer/ui/tabs/mods_tab.py`
- `windrose_deployer/ui/tabs/dashboard_tab.py`
- `windrose_deployer/ui/app_window.py`

Core / model touch points:

- `windrose_deployer/core/installer.py`
- `windrose_deployer/core/framework_state_service.py`
- `windrose_deployer/core/framework_detector.py`
- `windrose_deployer/core/hash_utils.py`
- `windrose_deployer/models/mod_install.py`

Tests:

- `tests/test_framework_state_service.py`
- `tests/test_framework_detector.py`
- add a focused `mods_tab` / archive lifecycle regression test if practical

---

## Manual Smoke Tests

Required:

1. Import a `UE4SS` runtime archive
2. Install it to one local target
3. Confirm it appears in `Active Mods`
4. Uninstall it
5. Confirm it appears in `Inactive Mods`
6. Confirm Dashboard `Frameworks` card updates immediately

7. Import a `UE4SS` mod archive
8. Install it to one local target
9. Confirm it appears in `Active Mods`
10. Uninstall it
11. Confirm it appears in `Inactive Mods`
12. Confirm Dashboard `Frameworks` card updates immediately

13. Repeat uninstall through:
   - row uninstall
   - bulk uninstall
   - reinstall path if applicable

14. Verify `WindrosePlus` and `RCON` packages cannot be installed to `Client only`
15. Verify `Client + Local Server` / `Client + Dedicated Server` does not partially install server-only framework packages to client
16. Drag a Nexus zip from `Downloads` into the manager and verify the library source points at the manager archive folder
17. Delete or move the original `Downloads` zip and verify reinstall/repair/inactive-mod display still works
18. Import the same archive again and verify it reuses the existing library copy instead of duplicating it noisily
19. Manually change/remove a local framework marker file and click Dashboard `Refresh`
20. Verify Dashboard updates local framework state without running hosted connection tests

Do not ship `v0.6.1` if:

- a framework archive disappears from both active and inactive views after uninstall
- Dashboard still shows stale framework state after uninstall
- normal pak uninstall behavior regresses while fixing framework behavior
- server-only framework packages can still be installed to client from normal UI paths
- newly imported archives still depend on browser downloads paths by default
- Dashboard refresh runs hosted connection tests unexpectedly

---

## Release Positioning

`v0.6.1` should be presented as a trust/correctness hotfix for `v0.6.0`:

- fixes `UE4SS` archive lifecycle after uninstall
- fixes Dashboard framework state not updating after uninstall
- prevents server-only framework packages from being installed to client targets
- makes newly imported archives manager-owned by default so inactive/reinstall/repair flows stay reliable
- adds a lightweight Dashboard refresh action
- no broad new feature scope
