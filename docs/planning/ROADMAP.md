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

### v0.6.x hosted FTP follow-up

- [ ] Improve FTP timeout diagnostics after real Nitrado reports:
  - distinguish control-connection timeout from login failure and remote-folder/path failure
  - mention firewall, VPN, ISP/router FTP blocking, and provider-side session limits when the FTP banner is not reached
  - suggest WinSCP/FileZilla validation from the same PC before assuming a manager bug
  - include the resolved host/port/protocol in the connection-test result with the password hidden
  - consider a slightly longer FTP connect timeout or a retry before showing failure
  - avoid wording that overstates "wrong protocol" when the server may simply be unreachable from the user's machine

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

## v0.6.4 - Stabilization and Support Cleanup

Detailed implementation plan lives in `IMPLEMENTATION_v0.6.4.md`.

This should be a low-risk support-quality release before starting load order.

- [ ] Add redacted support info export:
  - app version
  - target summary
  - hosted profile protocol/host/port only
  - recent log/activity summary
  - framework state summary
- [ ] Polish hosted setup normalization and guidance:
  - trim hidden whitespace in host/user/path fields
  - show normalized host/port/protocol before testing
  - keep connection failures distinct from remote path failures
  - keep Nitrado wording focused on FTP Credentials and port 21
- [ ] Tighten framework status consistency:
  - UE4SS runtime vs UE4SS mods
  - RCON `version.dll` before generated settings exist
  - WindrosePlus package/install/rebuild/dashboard state
- [ ] Make compare/sync wording clearer for server-only framework tooling
- [ ] Keep Activity rendering capped/lightweight for large histories

---

## v0.6.5 - Bulk Selection and Profiles UX

Detailed implementation plan lives in `IMPLEMENTATION_v0.6.5.md`.

This should be a focused quality-of-life release before `v0.7` load order.

- [x] Add `Select All` to `Active Mods`, scoped to the current target tab/filter:
  - `All`
  - `Client`
  - `Local Server`
  - `Dedicated Server`
  - `Hosted Server`
- [x] Add `Select All` to `Inactive Mods`, scoped to the current target/filter/search.
- [x] Keep destructive work behind `Uninstall Selected` and confirmation, not a one-click `Uninstall All`.
- [x] Rename inactive bulk action from `Install` to `Install Selected`.
- [x] Rework Mods panel action rows so the new buttons do not clip at default or large UI sizes.
- [x] Make existing saved mod Profiles discoverable from the Mods screen.
- [x] Keep profile apply preview-first:
  - installs
  - uninstalls
  - missing source archives
  - local targets affected
- [x] Keep first-pass profile apply focused on local targets:
  - `Client`
  - `Local Server`
  - `Dedicated Server`
- [x] Treat hosted profile entries as review-only/deferred until remote upload/delete profile semantics are designed safely.

---

## v0.6.6 - Restore Vanilla

Detailed implementation plan lives in `IMPLEMENTATION_v0.6.6.md`.

This should be a focused cleanup/safety release before `v0.7` load order.

- [ ] Add local-only `Restore Vanilla` for:
  - `Client`
  - `Local Server`
  - `Dedicated Server`
- [ ] Defer hosted restore/cleanup until a safer remote delete workflow exists.
- [ ] Preview before removing anything.
- [ ] Let users choose what to remove:
  - managed mods
  - unmanaged `~mods` files
  - framework files
- [ ] Back up unmanaged and framework files before removal.
- [ ] Use existing uninstall flow for managed mods.
- [ ] Detect and clean known UE4SS, RCON, and WindrosePlus file sets.
- [ ] Do not touch saves, world files, server settings, hosted files, archive library, or backup history.
- [ ] Refresh Dashboard, Mods, Activity, and Backups after cleanup.

---

## v0.7 - UI/UX and Startup Polish

Detailed implementation plan lives in `IMPLEMENTATION_v0.7.0.md`.

This release should make the app faster to open, easier to understand, and more helpful in normal client/server/hosted workflows. Load order is deferred until there is stronger evidence Windrose users need it.

### UX / performance foundation
- [ ] Add an app-native startup loading shell so users see immediate feedback instead of a blank delay
- [ ] Add an app-level status/result banner for startup, routine success, warnings, and long-running action state
- [ ] Keep PyInstaller splash out of the default build unless a future packaging test proves it is safe for the onedir Tk app
- [ ] Introduce a small, testable lazy-tab controller patterned after the Conan Exiles manager
- [ ] Move from refresh-lazy tabs to construction-lazy tabs where safe:
  - Dashboard first
  - Mods on first open
  - Server on first open
  - Activity on first open
  - Settings/Help on first open
- [ ] Decouple Dashboard summary data from full `ServerTab` construction where needed
- [ ] Defer Mods library loading/rendering until the Mods tab is first opened
- [ ] Add focused startup timing logs:
  - shell
  - dashboard build
  - mods tab build
  - mods library load
  - active/inactive mod render
  - server/activity tab build

### Dashboard as friendly home
- [ ] Borrow the Conan manager's home-screen structure where it fits Windrose:
  - short summary
  - task shortcuts
  - compact target/status cards
  - Needs Attention
  - support-info access
- [ ] Add clearer task shortcuts:
  - Install mods
  - Manage active mods
  - Set up hosted server
  - Check client/server match
  - Restore vanilla
  - Open support info
- [ ] Keep status cards compact and action-oriented
- [ ] Add a small testable `Needs Attention` helper for drift, missing archives, hosted path issues, and framework/server-only notes
- [ ] Avoid long technical summaries in primary cards

### Mods wording and scanability
- [ ] Keep primary user terms consistent:
  - Active Mods
  - Inactive Mods
  - Client
  - Local Server
  - Dedicated Server
  - Hosted Server
- [ ] Make large mod lists easier to scan:
  - denser rows
  - clearer badges
  - stronger selected/active state
  - framework/server-only state visible without opening logs
- [ ] Improve empty states:
  - Active Mods explains how to install a mod
  - Inactive Mods explains drag/drop and Add
  - Hosted inventory explains profile/refresh
- [ ] Avoid clipped buttons in Compact, Default, and Large UI sizes

### Hosted setup guidance
- [ ] Present hosted setup as a guided flow:
  - Choose protocol
  - Enter FTP/SFTP credentials
  - Test connection
  - Detect paths
  - Save profile
- [ ] Group hosted setup visually into:
  - Connection
  - Server Paths
  - Actions
  - Hosted Results
- [ ] Keep Nitrado/FTP wording clear:
  - FTP port is usually 21
  - Query/Game/RCON ports are not FTP ports
  - Host field should contain only the hostname, not a web panel URL
- [ ] Distinguish connection failures from path failures

### Inline results and wording cleanup
- [ ] Add a small banner-state/helper layer so routine results do not need modal popups
- [ ] Prefer inline result banners for routine success
- [ ] Keep popups for destructive confirmation, real errors, and conflict decisions
- [ ] Rewrite common errors to include:
  - what failed
  - likely cause
  - next action
- [ ] Align wording:
  - `archive` -> `inactive mod` in primary UI
  - `applied` -> `active` in primary UI
  - `remote` -> `hosted` in primary UI
  - `source root` -> `server folder` in primary UI
- [ ] Keep technical logs secondary and expandable, not dominant in the main workspace

### UI feedback and action states
- [ ] Add visible loading states for expensive refreshes:
  - Loading active mods
  - Loading inactive mods
  - Refreshing hosted files
  - Checking dashboard status
- [ ] Add busy button states for long-running actions:
  - Installing
  - Uninstalling
  - Testing connection
  - Refreshing
  - Restoring
- [ ] Show progress text for multi-item actions:
  - `Installing 2 of 7...`
  - `Uninstalling Expanded Horizons...`
- [ ] Add a compact Dashboard recent-actions mini-feed with only the last few relevant actions
- [ ] Add a persistent `Needs Attention` area for actionable warnings:
  - missing source archive
  - FTP path missing
  - drift detected
  - server-only framework difference
  - hosted profile not configured
- [ ] Add short toast-style messages only for small transient results like copied diagnostics or opened folders
- [ ] If this grows too large, keep loading states, busy buttons, and inline banners in v0.7, then split recent-actions polish to v0.7.1

### Accessibility and density polish
- [ ] Centralize the Windrose palette/card/input/list styling so tabs do not invent colors independently
- [ ] Borrow Conan's structure and consistency, not its bronze palette verbatim
- [ ] Improve contrast for muted small text where needed
- [ ] Keep status colors readable on dark background
- [ ] Use short section helper text instead of long paragraphs
- [ ] Verify Compact/Default/Large UI sizes still fit primary controls

### Optional v0.7.x framework UX support
- [ ] Add `External UE4SS detected` / `UE4SS managed by host` state where practical
- [ ] Let users mark a target as `UE4SS installed externally`
- [ ] Improve detection for common GitHub UE4SS release layouts
- [ ] Add provider guidance:
  - `If your provider supports UE4SS in its panel, enable it there first.`
  - `BisectHosting: enable UE4SS from the server Startup panel when available.`
- [ ] Do not force-install or replace UE4SS if a hosted provider already has a working runtime
- [ ] If this grows beyond wording/state/detection, split it to `v0.7.1`

---

## Future Load Order / Deep Inspection

Do not include load order or `retoc` in v0.7.

Load order is deferred until there is stronger evidence Windrose users need it. If implemented later, prefer a managed priority/prefix model where the app controls deployed filename prefixes and keeps `.pak/.utoc/.ucas` companions together.

If deeper pak/asset inspection becomes necessary later, treat it as a separate optional feature after normal manager workflows are stable.

---

## v0.7.1 to v0.9 - Archive Intelligence, Config Safety, and Profiles

Detailed implementation plan lives in `IMPLEMENTATION_v0.7.1_to_v0.9.md`.

The next releases should improve the Windrose-specific manager experience before adding platform API integrations. The app should stay source-agnostic: inspect the archive, explain what it found, preview the install, then deploy safely to client, local server, dedicated server, or hosted server targets.

### v0.7.1 - Public introduction polish
- [ ] Add an archive summary panel:
  - pak count
  - companion Unreal asset count
  - variant groups
  - loose/config/manifest files
  - UE4SS mod/runtime detection
  - mixed layout warnings
- [ ] Polish the variant picker:
  - clear title and helper text
  - clean filenames
  - cancel stops the install cleanly
  - only the chosen variant is installed
- [ ] Add a compact pre-install/pre-upload report:
  - target
  - selected variant/components
  - file list
  - destination preview
  - UE4SS status
  - overwrite/conflict risk
- [ ] Add `Copy Diagnostics` with secrets redacted
- [ ] Shorten clipped or overlong primary UI wording

### v0.8.0 - Archive intelligence and deployment confidence
- [ ] Add explicit archive layout adapters:
  - standard pak archive
  - multi-pak bundle
  - multi-variant pak archive
  - UE4SS mod archive
  - UE4SS runtime archive
  - shim-like UE4SS runtime archive
  - config-only archive
  - mixed archive
- [ ] Generalize selection for complex archives:
  - choose variants
  - choose optional components
  - keep `.pak`, `.utoc`, and `.ucas` companions together
- [ ] Store richer install metadata:
  - archive hash
  - detected layout kind
  - selected variant/components
  - installed files
  - target roots
- [ ] Add conflict and risk review before writes:
  - managed overwrite
  - unmanaged overwrite
  - missing target path
  - missing or external UE4SS
  - hosted path not verified
- [ ] Improve compare/sync so ambiguous variant/component archives require manual review

### v0.8.1 - Config center
- [ ] Add a central or clearly grouped config surface for:
  - Client
  - Local Server
  - Dedicated Server
  - Hosted Server
  - UE4SS
  - WindrosePlus
  - RCON
- [ ] Detect and edit known config files:
  - `UE4SS-settings.ini`
  - UE4SS `mods.txt`
  - UE4SS mod `enabled.txt`
  - UE4SS mod `settings.ini`
  - WindroseRCON `settings.ini`
  - WindrosePlus `.json`
  - WindrosePlus override `.ini` files
- [ ] Back up before every config write
- [ ] Validate JSON before save and apply INI sanity checks where practical
- [ ] Show restart/rebuild requirements clearly
- [ ] Support hosted known-config download/edit/upload where provider access allows it

### v0.8.2 - Server operations and world safety
- [ ] Add a compact local/dedicated server control strip:
  - selected server folder
  - launch target
  - process/server state
  - start/stop/restart
  - open folder
- [ ] Add a testable warning center for server issues:
  - server running while editing config
  - active world mismatch
  - missing generated config
  - direct connection loopback address
  - high player count
  - missing or external UE4SS state
- [ ] Improve world workflows:
  - discovered world list
  - set selected world active
  - import world folder
  - create initial/new world where safe
  - backup/restore selected world settings
  - move world to trash instead of hard delete
- [ ] Add first-run provisioning guidance for local/dedicated server folders with missing generated config
- [ ] Improve logbook support:
  - live tail known server log files
  - keyword filter
  - export logs
  - include recent relevant lines in diagnostics
- [ ] Research app-local scheduled backups/restarts for local/dedicated targets only

### v0.9.0 - Profiles, presets, and optional runtime bridge
- [ ] Add narrow Windrose profiles:
  - Client only
  - Local test server
  - Dedicated server
  - Hosted server
- [ ] Export/import profiles without secrets
- [ ] Preserve selected variants/components in profiles
- [ ] Add guided presets for common setups:
  - hosted UE4SS external
  - manual UE4SS local
  - local test server
  - dedicated server parity baseline
  - WindrosePlus rebuild workflow
  - local server with scheduled backups
  - dedicated server with world/config safety checks
- [ ] Research an optional UE4SS runtime bridge for in-game status/config/admin support after manager-side config is stable

### Deferred platform integration
- [ ] Nexus metadata/update checks are still valuable, but come after archive intelligence and config safety
- [ ] Use official Nexus API rules when revisited
- [ ] Keep downloads user-authorized and preview-first
- [ ] Route every downloaded archive through the same review/install workflow
- [ ] Online provider search/install is deferred until source-agnostic archive review is stable

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
