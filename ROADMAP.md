# Windrose Mod Manager - Roadmap

## v0.2.0 - Trust Baseline

The first public build people will keep using. Safety invariants and identity must be correct before persistent user data exists in the wild.

### Safety & Identity
- [x] Uninstall restores originals from backup (not just delete)
- [x] Reinstall preflight validation (don't destroy working install before confirming replacement)
- [x] Accurate Install All counting (succeeded/failed/skipped)
- [x] UUID-based mod identity (no name collisions, stable across renames)
- [x] Manifest schema versioning with forward migration (v1 name-based ids auto-migrate to v2 UUIDs)
- [x] Pre-migration manifest backup (`app_state.v1.bak.json` created before any schema rewrite)
- [x] Manifest collision guard (safety net even with UUIDs)

### Safety Regression Tests
- [x] Overwrite install then uninstall restores original file content
- [x] Duplicate display names get different mod IDs
- [x] v1 manifests migrate to UUID-based v2 schema
- [x] Migration creates backup copy of old manifest before rewriting
- [x] Invalid plans report as failures, not successes

### Features
- [x] Archive library (persistent sidebar, survives restarts)
- [x] Quick install (double-click or right-click)
- [x] Uninstall from Mods tab (right-click or detail panel)
- [x] Installed mod count badge
- [x] Multi-mod drag/drop and browse
- [x] Start Game / Start Server buttons with combined launcher
- [x] About tab with version, author, links
- [x] Update check (GitHub Releases API, startup + manual)
- [x] Uninstall All button with confirmation
- [x] Installed tab search/filter
- [x] Reinstall option (with preflight)

### Release Gates
- [ ] `pytest` green (all safety + unit tests pass)
- [ ] Migration tested on a real pre-v0.2.0 `app_state.json` with name-based mod IDs
- [ ] Packaged-build smoke test: install, uninstall, reinstall cycle works correctly from the PyInstaller `.exe` (path behavior often changes once packaged)

---

## v0.2.1 - Hotfix & State Consistency

Small release focused on fixing shipped correctness issues before remote/rented-server support lands.

### Release blockers
- [x] Disabled mods that overwrote files still restore originals on uninstall
- [x] Restore backup writes to the currently configured `ServerDescription.json`, not a stale path from backup metadata
- [x] Mods tab supports multiple installs from the same archive path without ambiguous badges/uninstall actions
- [x] Changing Backup Directory takes effect immediately, or the UI explicitly requires restart before claiming success

### Regression coverage
- [x] Disable -> uninstall -> original file restored after overwrite
- [x] Server config restore targets the active configured path only
- [x] Same archive installed to multiple targets remains representable in Mods tab
- [x] Backup-directory change is honored by live services

### UX follow-up
- [x] Grouped conflict display (by mod, file count, target path)
- [x] Conservative variant detection (flag uncertain cases for user decision instead of guessing)
- [ ] Better error messages for common failure modes
- [ ] UI polish based on first user reports

---

## v0.3.0 - Remote Server & Recovery

The next major feature set: make the tool useful for rented servers while strengthening recovery and verification.

### Product direction
- [x] Remote/rented-server support is a first-class feature
- [x] Managed remote deployment uses **SFTP/SSH first**
- [ ] FTPS can be added if hosts require it
- [x] Plain FTP is deferred unless a host forces it, because it is the weakest protocol option

### Remote server MVP
- [x] Saved remote connection profiles
- [x] Connection test and validation before any upload
- [x] Configurable remote mods directory
- [x] Remote install uses a real deployment plan, not raw archive dumping
- [x] Variant-aware remote install (only the selected variant is uploaded)
- [x] Remote upload preserves only planned files/paths
- [x] Remote file listing / path verification
- [x] Clear post-upload summary (succeeded/failed/skipped with reasons)
- [x] Restart guidance or optional restart action after deploy

### Remote architecture rules
- [x] Introduce a small remote provider abstraction (`RemoteProvider`)
- [x] Implement `SftpProvider` first
- [x] Keep archive path safety rules for remote deployment too
- [x] No arbitrary remote shell/command console in the MVP
- [x] No fake "supports every rented host" claim until multiple hosts are validated

### Recovery & verification
- [x] Verify install (check manifest against actual files on disk, report drift)
- [x] Repair install (re-extract missing files from archive if archive is still available)
- [x] Better batch action summaries (succeeded/failed/skipped with reasons)
- [x] Drift detection on startup (warn if files changed outside the manager)

### Test matrix
- [x] Remote install uses deployment plan output, not raw archive contents
- [x] Remote install uploads only the selected variant
- [x] Unsafe archive paths are rejected in remote workflow too
- [x] Remote result summaries count succeeded/failed/skipped correctly
- [ ] End-to-end SFTP smoke test against a rented-server-like target

---

## v0.4.0 - Server Differentiation

This is where the product becomes more useful than generic mod managers for Windrose server operators.

### Server-safe apply
- [ ] Apply workflow: validate mod set, deploy, prompt for server restart, verify post-restart
- [ ] Running-server detection and warning before writes
- [ ] Apply guidance: surface which changes need a server restart vs. which are hot-loadable (if any)

### Client/server sync validation
- [ ] Define source of truth: manifest is authoritative, on-disk scan is verification
- [ ] Detect mismatched mod states between client and server targets
- [ ] Surface sync status clearly (which mods are client-only, server-only, or both)

### WorldDescription.json workflows
- [ ] Per-world discovery (enumerate worlds under SaveProfiles, show active world from ServerDescription.json)
- [ ] Running-server save behavior is explicit (warn/block/allow depending on what Windrose actually supports)
- [ ] Backup diff/restore (show what changed between backups, restore specific versions)
- [ ] Apply guidance (which settings need world restart vs. server restart)

---

## v0.5.x - Server Operations & Parity

Detailed working plan lives in `PLAN_v0.5.x.md`.
Detailed implementation brief lives in `IMPLEMENTATION_v0.5.0.md`.

High-level direction:
- [ ] Server dashboard with clearer local/dedicated/hosted status
- [ ] Metadata/version awareness foundation
- [ ] Bundle-aware archive/applied mod cards
- [ ] Better inspect surface for complex archives
- [ ] Backups and activity/logs become first-class workflows
- [ ] Framework/dependency awareness
- [ ] Narrow, preview-first Profiles

### v0.5.2 follow-up polish
- [x] Dashboard should let the user change the active compare/source target directly instead of depending on whatever is currently selected in `Server`
- [x] Dashboard parity should offer guided sync actions after compare, not a blind one-click sync:
  - install missing client mods to Local Server
  - install missing client mods to Dedicated Server
  - upload missing client mods to Hosted Server
  - review server-only removals separately
  - require preview and confirmation before any writes
- [x] Manifest drift should be surfaced in the main UI, not only the technical log
- [x] Copy should align with the current `Activity` information architecture instead of stale `Recovery` wording
- [x] Activity tab performance pass so large timelines/raw backup lists feel lighter to open and refresh
- [x] Startup performance pass before the next major UI expansion:
  - v0.5.2 only reduced refresh fan-out and Activity render cost; true lazy tab construction is deferred
  - true lazy construction for non-default heavy tabs should be done as a separate focused pass after cross-tab dependencies are loosened
  - first candidates: Activity and Help, then Settings, then the heavier Mods/Server tabs
  - keep first window paint fast and measurable
  - preserve startup timing diagnostics
- [ ] Light UI decomposition before UE4SS/load-order work:
  - extract reusable Mods/Server helpers where it lowers future risk
  - avoid a broad visual rewrite in this release
- [x] Hosted setup should gain provider-specific QoL for Host Havoc / Indifferent Broccoli paths
- [x] FTP diagnostics should be clearer for mismatch, auth, timeout, listing failures, and FTP-root-relative path confusion
- [ ] Metadata/setup groundwork for future per-mod version notifications:
  - make optional mod source/version metadata easier to view and maintain
  - improve `possible update available` hints where metadata exists
  - do **not** promise full automatic mod update checks yet

### v0.5.2 shipped notes

- Guided sync is intentionally conservative: it only offers additive client-to-server install/upload actions when the source archive is still available and no variant/component/conflict ambiguity is detected.
- Server-only and hosted-only removals are intentionally review-only in this release.
- Nitrado-specific support is handled through clearer FTP-root path diagnostics, not a provider-specific integration layer.
- True construction-lazy tabs and broader UI decomposition remain deferred to a focused `v0.5.3` / early `v0.6` prep pass.

### Deferred startup refactor note

Do not treat true lazy tab construction as complete just because v0.5.2 improved startup behavior. Dashboard, Mods, and Server still call into each other directly in several places, so making those tabs construction-lazy should happen only after a small coordinator/helper extraction. The safe target is `v0.5.3` or early `v0.6` prep, before adding UE4SS/load-order UI to the already-heavy tabs.

---

## v0.6 - UE4SS, Framework Support, and WindrosePlus Foundations

Detailed implementation plan lives in `IMPLEMENTATION_v0.6.0.md`.

The next larger release should make UE4SS a first-class, safe, target-aware workflow while carrying forward the most important trust and metadata groundwork.

### Primary UE4SS scope
- [ ] Detect UE4SS runtime state per target:
  - Client
  - Local Server
  - Dedicated Server
  - Hosted Server
- [ ] Install user-supplied UE4SS runtime archives to the correct `R5\Binaries\Win64` target
- [ ] Install UE4SS mods to the correct `R5\Binaries\Win64\ue4ss\Mods` target
- [ ] Show target-aware warnings when a UE4SS mod likely needs a missing UE4SS runtime
- [ ] Track UE4SS runtime/mod installs in the normal managed lifecycle:
  - backup
  - uninstall
  - repair/reinstall
  - activity/history
- [ ] Support hosted UE4SS file deployment over existing SFTP/FTP provider plumbing where safe
- [ ] Do not bundle/re-upload UE4SS unless explicit permission is granted

### RCON preparation
- [ ] Detect likely RCON UE4SS mods such as Windrose Source RCON Protocol
- [ ] Detect/read/write known RCON `settings.ini` files where safe
- [ ] Add optional RCON configuration state without storing secrets in profiles
- [ ] Prepare a Dashboard RCON status slot
- [ ] Defer live admin commands if the protocol/client work is not reliable enough for v0.6.0

### WindrosePlus integration path
- [ ] Treat WindrosePlus as a supported server-side capability layer, not something to clone
- [ ] Keep WindrosePlus optional:
  - normal pak/UE4SS workflows must still work without it
  - do not turn the app into a WindrosePlus-only server panel
- [ ] Detect WindrosePlus when installed under UE4SS mods
- [ ] Support installing/updating WindrosePlus from a user-supplied archive or explicit release workflow only if licensing/permission stays clear
- [ ] First-pass WindrosePlus integration target is local Windows dedicated servers:
  - detect install state
  - show quick actions such as `Open WindrosePlus Folder` and `Open WindrosePlus Dashboard`
  - back up and edit common configs where safe:
    - `windrose_plus.json`
    - `windrose_plus.ini`
    - `windrose_plus.food.ini`
- [ ] For local/dedicated Windows servers, optionally run the WindrosePlus rebuild step before launch when configured
- [ ] For hosted servers, support file upload/config editing first and be honest that dashboard/rebuild/restart depends on host shell/panel support
- [ ] Defer cloning WindrosePlus admin/RCON features into a native in-app panel until the install/config/status workflow is stable

### Trust and metadata carry-forward
- [ ] Surface manifest drift more deeply and consistently in the UI
- [ ] Continue optional metadata/version notification groundwork
- [ ] Keep version notifications notification-only at first:
  - `update available`
  - `not configured`
  - `check failed`
- [ ] Do **not** turn version checking into auto-download/update in the first pass

### Configurable overhaul groundwork
- [ ] Keep `IMPLEMENTATION_configurable_overhaul.md` as the source of truth for the tweak-builder lane
- [ ] Create/maintain a supported tweak research catalog
- [ ] Add only safe model/toolchain foundations unless the manual proof and patch-engine gates pass
- [ ] Do not ship asset patching/build UI until the feasibility gates are proven in-game

---

## v0.6.1 - Framework Lifecycle Fixes

Detailed implementation plan lives in `IMPLEMENTATION_v0.6.1.md`.

This patch release started as lifecycle correctness after `v0.6.0`, then pulled forward the safest local framework-management pieces from the `0.6.x` plan.

- [x] Uninstalling the last active `UE4SS` runtime install should return the source archive to `Inactive Mods`
- [x] Uninstalling the last active `UE4SS` mod install should return the source archive to `Inactive Mods`
- [x] Dashboard `Frameworks` state should refresh immediately after framework uninstall/install lifecycle changes
- [x] Audit all framework uninstall entry points so row uninstall, bulk uninstall, and reinstall paths behave consistently
- [x] Block likely server-only framework packages such as `WindrosePlus` and `RCON` from client install targets
- [x] Hide or disable invalid client presets for server-only framework packages where practical
- [x] Copy newly imported archives into the manager archive library by default so inactive/reinstall/repair flows do not depend on browser downloads paths
- [x] Add a lightweight Dashboard `Refresh` button for local framework state, mod counts, and attention indicators without triggering hosted connection tests
- [x] Add regression coverage for framework archive re-entry and dashboard refresh correctness

---

## v0.6.2 - WindrosePlus and Framework Compatibility

This follow-up should make installed framework packages feel deliberately supported, while still treating them as server tooling rather than normal gameplay mods.

### Frameworks section
- [x] Add a dedicated `Frameworks` section inside the Server/Dashboard workflow
- [x] Keep the section grouped by framework type:
  - `UE4SS`
  - `RCON`
  - `WindrosePlus`
- [x] Make each framework block status-first, with only relevant actions visible for detected/configured targets

### UE4SS framework support
- [x] Show UE4SS runtime status per target:
  - installed
  - missing
  - partial/broken
- [ ] Keep UE4SS runtime clearly separate from UE4SS mods in the UI
- [x] Edit known `UE4SS-settings.ini` safely with backup before save
- [x] Show that `UE4SS-settings.ini` changes usually require a server/game restart
- [x] Add repair/reinstall for UE4SS runtime when the source archive is available
- [x] Warn when installing a UE4SS mod to a target that does not have UE4SS runtime installed

### RCON framework support
- [x] Show RCON status per target:
  - installed
  - not installed
  - configured
  - missing/blank password
- [x] Edit known `WindroseRCON\settings.ini` safely with backup before save
- [x] Expose only known fields such as port, password, and enabled/disabled state
- [x] Show that RCON setting changes may require restart/reload depending on the mod
- [ ] Add `Test RCON` later only after the protocol path is proven reliable

### WindrosePlus launch compatibility
- [x] Detect `StartWindrosePlusServer.bat` in the Local Server / Dedicated Server root
- [x] Add a launch option or automatic preference for the WindrosePlus wrapper when present:
  - normal dedicated launch remains available
  - WindrosePlus launch uses `StartWindrosePlusServer.bat`
  - user-facing wording explains that WindrosePlus may need Administrator/elevated launch
- [x] Add quick actions where local files exist:
  - `Run WindrosePlus Install`
  - `Open WindrosePlus Folder`
  - `Open WindrosePlus Config`
  - `Open WindrosePlus Dashboard`
  - `Rebuild WindrosePlus Overrides`
- [x] Detect WindrosePlus state clearly:
  - package installed
  - active under UE4SS mods
  - generated override PAK present
  - install script present
  - launch wrapper present
- [x] Detect generated WindrosePlus PAKs such as:
  - `WindrosePlus_Multipliers_P.pak`
  - `WindrosePlus_CurveTables_P.pak`
- [x] Warn if WindrosePlus files are present but `install.ps1`, UE4SS markers, or `StartWindrosePlusServer.bat` output is missing
- [ ] For hosted servers, keep WindrosePlus launch/rebuild wording honest:
  - file upload/config editing may be possible
  - running PowerShell/rebuild/start scripts depends on the host

### Known config editing
- [x] Add a framework config surface for known files only
- [x] Support safe load/edit/save with backups for:
  - `R5\Binaries\Win64\ue4ss\UE4SS-settings.ini`
  - `R5\Binaries\Win64\ue4ss\Mods\WindroseRCON\settings.ini`
  - `windrose_plus.json`
  - `windrose_plus.ini`
  - `windrose_plus.food.ini`
  - `windrose_plus.weapons.ini`
  - `windrose_plus.gear.ini`
  - `windrose_plus.entities.ini`
- [x] Do not add raw arbitrary file editing for framework folders
- [x] Show what each edit likely requires:
  - UE4SS settings usually require restart
  - RCON settings may require restart/reload depending on the mod
  - `windrose_plus.json` may include a mix of live settings and settings that require restart/rebuild
  - WindrosePlus multiplier/config changes may require rebuild before launch

### WindrosePlus rebuild support
- [x] Add `Rebuild WindrosePlus Overrides` for local/dedicated Windows targets
- [x] Run the documented WindrosePlus build script when available:
  - `windrose_plus\tools\WindrosePlus-BuildPak.ps1`
  - pass `-ServerDir <server root>`
  - pass `-RemoveStalePak`
- [x] Capture and display success/failure output clearly
- [x] Do not auto-run scripts without explicit confirmation
- [x] Do not promise rebuild support for hosted servers unless shell/script execution is available and tested

### Framework state quality
- [ ] Expand partial/broken framework state coverage:
  - `dwmapi.dll` exists but `ue4ss` folder is missing
  - `ue4ss\Mods` contains framework mods but UE4SS runtime is missing
  - UE4SS is installed on client while the selected/detected package is server-only
  - WindrosePlus package files exist but its installer/wrapper output is missing
- [x] Show repair guidance instead of treating partial state as fully installed

---

## v0.6.3 - RCON and Dashboard Convenience

This should stay convenience-focused until the RCON path is proven reliable.

- [x] Show `RCON configured / disabled / missing password` on Dashboard
- [x] Add `Open WindrosePlus Dashboard` using known dashboard config or default local URL where safe
- [ ] Add a conservative `Test RCON` action only after protocol behavior is verified
- [ ] Do not add kick/ban/admin command buttons until users ask for them and the command path is reliable
- [ ] Do not clone the WindrosePlus dashboard inside the manager

---

## v0.7 - Deep Mod Understanding & Load Order

Detailed implementation plan lives in `IMPLEMENTATION_v0.7.0.md`.

This release line should make the app better at understanding what mods actually touch, without editing other authors' mods.

### Retoc-powered inspection
- [ ] Add optional `retoc` tool setup:
  - user-supplied path first
  - optional bundled copy later only if license/packaging notices are handled
- [ ] Use `retoc` for deep inspection where possible:
  - list files/assets inside `.pak`
  - list files/assets inside `.utoc/.ucas`
  - cache asset-path manifests per archive/hash
- [ ] Keep basic install/uninstall usable without `retoc`
- [ ] Surface `retoc` failures as inspection limitations, not install blockers unless the action requires deep inspection

### Asset-level conflict awareness
- [ ] Move beyond filename-only conflict guesses where deep inspection data exists
- [ ] Show when multiple mods touch the same asset path
- [ ] Group conflicts by:
  - target
  - asset path
  - installed/archive source
- [ ] Keep wording careful:
  - `same asset touched`
  - `load order may decide winner`
  - `review recommended`

### Load order management, not patching
- [ ] Do not patch or mutate third-party pak contents in place
- [ ] Expose load order as a simple managed priority, not manual filename editing
- [ ] Support explicit load order for managed pak/io-store groups by controlling deployed file name prefixes where Windrose/UE load behavior allows it
- [ ] Map priority to backend-managed prefixes, for example:
  - `010_`
  - `050_`
  - `090_`
- [ ] Preserve the original filename after the managed prefix by default
- [ ] Do not special-case `_P` removal in the normal workflow
- [ ] Keep original archive files unchanged
- [ ] Rename companion files together:
  - `.pak`
  - `.utoc`
  - `.ucas`
- [ ] Store original filename, deployed filename, priority, target, and companion group in manifest/history
- [ ] Preview load-order changes before applying
- [ ] Back up and track any deployed-file rename/redeploy operation in manifest/history
- [ ] Preserve recovery path so users can return to the previous deployed order
- [ ] Keep any advanced filename override out of the default UI unless real compatibility cases prove it is needed

### UI refresh tied to real data
- [ ] Rework the Mods workspace around clearer data states:
  - Installed / Applied
  - Available Archives
  - Conflicts
  - Load Order
- [ ] Avoid a purely visual redesign before the load-order/conflict model exists
- [ ] Make large mod lists easier to scan:
  - denser rows
  - clearer badges
  - stronger selected/active state
  - conflict count and dependency warnings visible without opening logs
- [ ] Keep technical logs secondary and expandable, not dominant in the main workspace

---

## v0.8 - Nexus Updates & Download Integration

This should be a staged Nexus integration, not a silent auto-update system.

### Update available checks
- [ ] Use stored Nexus metadata to check for newer files:
  - game domain
  - mod ID
  - file ID
  - installed/downloaded version
  - last checked timestamp
- [ ] Show clear states:
  - `update available`
  - `up to date`
  - `not configured`
  - `check failed`
- [ ] Cache results and respect rate limits
- [ ] Do not scrape Nexus pages when API metadata is missing

### Nexus account/API compliance
- [ ] Register the app with Nexus before public API-based download features
- [ ] Do not rely on personal API keys for public users except development/testing
- [ ] Send proper Nexus API request headers:
  - application name
  - application version
- [ ] Store tokens/keys securely before enabling broad Nexus download support

### User-authorized downloads
- [ ] Add one-click/manual-confirmed update download where Nexus API support and user account permissions allow it
- [ ] Keep downloads user-initiated:
  - no silent background mod replacement
  - no automatic install without preview
- [ ] After download, route through the existing archive review/install workflow
- [ ] Support fallback flow:
  - open Nexus page
  - user downloads manually
  - user imports archive into manager

---

## v1.0 - Framework Extraction (future)

**Rule: don't build a framework until there is a second game. But keep the current code ready for extraction.**

Second adapter must prove the abstraction without changing Windrose behavior. The extraction is only valid if the Windrose adapter works identically before and after.

Current design seams to maintain:
- Windrose-specific discovery/config logic is grouped (not scattered)
- Path assumptions stay out of generic install/manifest/backup code
- Archive/install/manifest/backup logic is game-agnostic
- Plugin-style adapter model is the extraction target, not the current implementation

When a second UE game needs mod management, extract the generic core into a shared framework and keep Windrose as the first adapter.

---

## Design Principles

1. **The app should always be able to answer**: "what changed, what was replaced, and how do I get back to the previous state?"
2. **Don't ship persistent public state with weak identity semantics.** Fix identity before the first real release, not after.
3. **Design for extraction, don't perform extraction yet.** Light seams now, full plugin architecture later.
4. **Safety over features.** Every release must pass its safety regression suite.
