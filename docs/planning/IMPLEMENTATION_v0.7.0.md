# Windrose Mod Manager - v0.7.0 UI/UX Implementation Plan

## Release Goal

`v0.7.0` should make Windrose Mod Manager feel faster, clearer, and easier to trust.

This release should focus on:

- visible startup feedback
- true lazy UI construction
- app-wide inline status/result feedback
- clearer Dashboard entry points
- simpler Mods screen wording and scanability
- clearer hosted/server setup guidance
- better empty states, inline results, and error recovery text

This is intentionally **not** a load-order release. Load order is deferred until there is stronger evidence that Windrose users need it.

## Product Principle

The app should feel like a practical Windrose workflow tool, not a technical file manager.

Good v0.7 UX means:

- the user can tell what is happening
- actions use familiar words
- common next steps are visible
- dangerous actions are previewed
- technical details stay available but secondary

## Non-Goals

Do not implement:

- load order
- `retoc`
- pak unpacking/repacking
- configurable overhaul / generated pak building
- Nexus update checks/downloads
- FTPS
- RCON admin commands
- new framework features beyond wording/status cleanup if touched
- broad visual redesign unrelated to clarity/performance
- generic multi-game abstraction

## Research Findings Applied

Useful UX principles for this release:

- Visibility of system status: show what the app is doing during startup, connection tests, installs, refreshes, and compares.
- Match real-world language: use `Client`, `Local Server`, `Dedicated Server`, `Hosted Server`, `Active Mods`, and `Inactive Mods` instead of internal terms where possible.
- Error prevention: guide users before mistakes, especially hosted setup, destructive cleanup, and server-only framework installs.
- Recognition over recall: show next steps directly instead of requiring users to remember the guide.
- Minimalism: remove low-signal text from primary screens and keep technical logs/support details secondary.
- Button clarity: use concise verb labels and avoid clipped button rows.
- Accessibility: keep small text readable and improve contrast where existing muted text is too low contrast.

Conan Exiles Enhanced Manager patterns worth borrowing:

- Use a small, testable lazy-tab controller instead of tab-specific construction flags.
- Show a persistent app-level status/result banner for routine feedback, with popups reserved for destructive confirmation and real errors.
- Make Dashboard a true home screen: short summary, task shortcuts, compact status cards, `Needs Attention`, and support-info access.
- Keep hosted setup visually grouped into `Connection`, `Paths`, `Actions`, and `Inventory/Results`.
- Centralize UI colors and state helpers so tabs stop inventing their own muted text, card borders, and action colors.
- Borrow the structure and interaction model, not the Conan palette verbatim; Windrose should keep its own restrained identity.

## Current Baseline

Recent startup logs show:

- service setup is usually under `50 ms`
- `_initial_load` is usually around `300-350 ms`
- `_build_ui` is the main startup bottleneck at roughly `3.2-4.7 seconds`
- current lazy behavior lazy-refreshes tabs, but all tab widgets are still constructed at boot
- `ModsTab` is the largest UI surface and still loads its library during `__init__`
- Dashboard currently reaches into `ServerTab` internals, which makes true lazy Server construction harder

The best v0.7 performance work is startup shell + true lazy tab construction + deferred Mods loading.

The Conan manager already proves the desired direction in a simpler app shape: `LazyTabController`, startup messages, a banner-state helper, and a `Needs Attention` helper are all testable without creating Tk widgets. Windrose should use the same kind of small helper seams, adapted to its richer archive/framework/hosted model.

## Slice 1 - Startup Loading Shell

Goal:

- remove the "nothing happens" startup feeling

Implement:

- show the main window quickly with a lightweight loading panel
- build the global status/result banner before heavy tab construction
- use short status text:
  - `Starting Windrose Mod Manager...`
  - `Loading Dashboard...`
  - `Preparing Mods...` only when Mods is opened
- replace the loading panel with Dashboard once ready
- keep PyInstaller splash out of the default build

Acceptance:

- user sees a visible window/status before expensive tab construction completes
- no blank multi-second delay
- startup exceptions still surface clearly instead of being hidden behind the shell

## Slice 2 - True Lazy Tab Construction

Goal:

- construct only what is needed at startup

Implement:

- introduce a small `LazyTabController` helper patterned after the Conan manager
- add `ensure_dashboard_tab()`, `ensure_mods_tab()`, `ensure_server_tab()`, `ensure_activity_tab()`, `ensure_settings_tab()`, and `ensure_help_tab()` helpers on `AppWindow`
- make cross-tab actions call those helpers only when the destination tab or workflow is actually needed
- add lightweight summary/helper APIs so Dashboard refresh does not force `ServerTab` or `ModsTab` construction

Initial startup should build:

- root window
- update banner shell
- status/result banner shell
- tab container
- Dashboard/loading shell
- shared launch/status shell if still needed

Construct on first open:

- Mods
- Server
- Activity
- Settings
- Help

Rules:

- first open can briefly show `Loading...`
- tab construction must be idempotent
- cross-tab calls must create needed tabs safely or use lightweight app-level helpers
- no duplicate refresh storms

Acceptance:

- startup no longer constructs every heavy tab
- each tab still refreshes correctly when opened
- tests prove each lazy tab factory runs once

## Slice 3 - Dashboard as Friendly Home

Goal:

- Dashboard should be useful without feeling like a budget admin panel

Improve Dashboard with clearer task shortcuts:

- `Install mods`
- `Manage active mods`
- `Set up hosted server`
- `Check client/server match`
- `Restore vanilla`
- `Open support info`

Keep status cards compact:

- Client
- Local Server
- Dedicated Server
- Hosted Server
- Frameworks
- Needs Attention

Use the Conan Dashboard pattern as the baseline:

- one short home summary
- one row of task shortcuts
- compact target/status cards
- a persistent `Needs Attention` area
- support-info access in the Dashboard footer or action area

Rules:

- no long technical summaries in primary cards
- no duplicate text from Server/Activity
- Dashboard can link to details instead of showing everything
- Dashboard should not require full ServerTab/ModsTab construction for basic state

Acceptance:

- user can understand "what should I do next?" from Dashboard
- Dashboard first render does not require heavy tabs where avoidable
- `Needs Attention` is generated by a testable helper, not buried in widget code

## Slice 4 - Deferred Mods Loading

Goal:

- Mods should not slow app launch before the user opens Mods

Implement:

- remove eager `_load_library()` from `ModsTab.__init__`
- load library and render Active/Inactive rows on first Mods open
- cache library and manifest/history snapshots for one render pass
- avoid repeated `manifest.list_mods()` and `manifest.list_history()` scans in row loops
- keep Refresh behavior explicit and correct

Acceptance:

- app startup is not dominated by Mods UI/library rendering
- first Mods open loads correctly and shows progress if needed

## Slice 5 - Mods Screen Wording and Scanability

Goal:

- make Mods easier to understand at a glance

Keep core terms:

- `Active Mods`
- `Inactive Mods`
- `Client`
- `Local Server`
- `Dedicated Server`
- `Hosted Server`

Improve rows:

- stronger target badges
- clearer framework/server-only badges
- clearer unmanaged/managed state
- fewer long secondary text lines
- better selected state
- avoid clipped buttons in Compact, Default, and Large UI sizes

Improve empty states:

- Active Mods empty:
  - `No active mods for this target. Install an inactive mod to get started.`
- Inactive Mods empty:
  - `No inactive mods yet. Drag a downloaded .zip, .7z, .rar, .pak, .utoc, or .ucas here, or click Add.`
- Hosted inventory empty:
  - `No hosted mods loaded yet. Select a hosted profile and refresh hosted mods.`

Acceptance:

- users can scan large lists faster
- empty panels explain the next step

## Slice 6 - Hosted Setup Guidance

Goal:

- reduce support tickets from FTP/SFTP confusion

Improve Hosted Setup as a guided flow:

1. `Choose protocol`
2. `Enter FTP/SFTP credentials`
3. `Test connection`
4. `Detect paths`
5. `Save profile`

Recommended layout:

- `Connection`: profile, protocol, host, port, username, auth
- `Server Paths`: server folder, mods folder, settings file, saves
- `Actions`: save profile, test connection, auto-detect paths, refresh inventory
- `Hosted Results`: connection/path diagnostics, inventory, and copyable support text

Copy rules:

- `Host / IP` should say hostname only, not web panel URL
- `FTP port is usually 21`
- `Query, Game, and RCON ports are not FTP ports`
- `Server Folder = .` guidance appears only when it fits the situation
- distinguish connection failures from path failures

Acceptance:

- Nitrado/Host Havoc/Indifferent Broccoli users get clearer next steps
- diagnostics stay non-secret and copyable

## Slice 7 - Inline Results and Error Recovery Text

Goal:

- reduce popups and make errors actionable

Implement:

- add a small `BannerState` / `show_banner()` style helper for routine info/success/warning/error messages
- use inline result banners/status text for routine success
- keep popups for destructive confirmation, real errors, and conflict decisions
- rewrite common error messages to include:
  - what failed
  - likely cause
  - next action

Examples:

- `FTP connected, but the mods folder was not found. Try Server Folder = . or use Auto-Detect Paths.`
- `This looks like a server-only framework mod. Install it to Local Server, Dedicated Server, or Hosted Server.`
- `The source archive is missing. Re-add the archive before reinstalling this mod.`

Acceptance:

- users do not need technical logs for common failures
- support comments can ask for copied diagnostics only when needed

## Slice 8 - UI Feedback and Action States

Goal:

- make every action visibly respond before, during, and after it runs

Implement:

- add a small global/latest-action status area where practical, preferably the app-level banner
- use per-panel loading text for expensive refreshes:
  - `Loading active mods...`
  - `Loading inactive mods...`
  - `Refreshing hosted files...`
  - `Checking dashboard status...`
- add inline success/error banners for routine results
- keep popups for destructive confirmation, real errors, and conflict decisions
- add busy button states:
  - `Installing...`
  - `Uninstalling...`
  - `Testing connection...`
  - `Refreshing...`
  - `Restoring...`
- show progress text for multi-item actions:
  - `Installing 2 of 7...`
  - `Uninstalling Expanded Horizons...`
- add a compact recent-actions mini-feed on Dashboard:
  - show last 3 relevant actions only
  - link to Activity for full history
- add a persistent `Needs Attention` area for actionable warnings:
  - missing source archive
  - FTP path missing
  - drift detected
  - server-only framework difference
  - hosted profile not configured
- add short toast-style transient messages only where useful:
  - `Copied diagnostics to clipboard`
  - `Opened folder`

Consistency rule:

- every long-running action must have visible state before, during, and after
- do not leave users guessing whether a click worked

Cut rule:

- if this grows too much, keep busy button states, loading text, and inline result banners in v0.7, then split recent-actions/feed polish to v0.7.1

Acceptance:

- installs, uninstalls, hosted tests, refreshes, compares, backup/restore, and Restore Vanilla all show clear action feedback
- routine success does not rely on modal popups
- users can see the latest result without opening logs

## Slice 9 - Wording Consistency Pass

Goal:

- remove confusing mixed terminology

Audit and align:

- `archive` -> `inactive mod` in primary UI, keep archive in details/support text
- `applied` -> `active` where user-facing
- `remote` -> `hosted` where user-facing
- `source root` -> `server folder` where user-facing
- `deployment` -> `install/upload` where user-facing
- `recovery` -> `Activity / Backups` unless referring to restore behavior directly

Acceptance:

- major screens use the same target names and action names
- help/sticky wording matches the app

## Slice 10 - Accessibility and Density Polish

Goal:

- improve readability without a visual rewrite

Implement where practical:

- centralize the Windrose palette and card/input/list styling in `ui_tokens.py` or a small companion helper
- use one primary accent and one secondary/action-neutral color consistently; do not copy Conan's bronze palette directly
- improve contrast for muted small text
- keep status colors readable on dark background
- keep button labels under control and avoid clipping
- ensure Compact/Default/Large still fit primary controls
- use section headers and short helper text instead of paragraphs

Acceptance:

- important text remains readable in dark UI
- controls do not clip at normal window size

## Optional Slice - External UE4SS / Host-Managed Runtime UX

Goal:

- support users whose provider or manual setup uses a working UE4SS runtime that the manager did not install

Context:

- some hosted providers, such as BisectHosting, may expose UE4SS as a server-panel option rather than a normal uploaded archive
- some Windrose setups may require a specific experimental GitHub UE4SS build
- the manager should not force users to replace a working host-managed runtime with a Nexus package

Implement if it stays small:

- add `External UE4SS detected` / `UE4SS managed by host` state
- allow users to mark a target as `UE4SS installed externally`
- improve detection for common GitHub UE4SS release layouts
- add hosted/provider guidance:
  - `If your provider supports UE4SS in its panel, enable it there first.`
  - `Do not replace a working host-managed UE4SS runtime unless you know the provider allows it.`
  - `BisectHosting: enable UE4SS from the server Startup panel when available.`
- when runtime is marked external, allow UE4SS mod installs without showing a hard missing-runtime warning
- keep the warning softer:
  - `UE4SS was not installed by the manager. Make sure it is enabled/running on this target.`

Rules:

- do not bundle UE4SS
- do not auto-download UE4SS
- do not overwrite host-managed runtime files unless the user explicitly installs a runtime package
- do not pretend external UE4SS can be verified if the provider hides the runtime files

Cut rule:

- if this becomes more than wording/state/detection, split it into `v0.7.1` and keep the main `v0.7.0` startup/UX release focused

Acceptance:

- users with provider-enabled UE4SS can still use the manager for UE4SS mods
- the app distinguishes `missing`, `installed by manager`, `detected externally`, and `user-marked external`
- hosted users get provider-aware guidance instead of being told only to install the Nexus runtime

## Likely Files To Touch

UI:

- `windrose_deployer/ui/app_window.py`
- `windrose_deployer/ui/tabs/dashboard_tab.py`
- `windrose_deployer/ui/tabs/mods_tab.py`
- `windrose_deployer/ui/tabs/server_tab.py`
- `windrose_deployer/ui/tabs/backups_tab.py`
- `windrose_deployer/ui/tabs/settings_tab.py`
- `windrose_deployer/ui/tabs/about_tab.py`

Possible helpers:

- `windrose_deployer/core/lazy_tabs.py`
- `windrose_deployer/core/needs_attention.py`
- `windrose_deployer/models/ui_state.py`
- small dashboard summary helper/service if needed
- small UI wording/constants helper if it prevents duplicated strings
- centralized UI palette/state helpers if `ui_tokens.py` becomes too broad

Docs:

- `docs/planning/ROADMAP.md`
- Nexus sticky/quick guide draft after implementation

## Tests

Add/update tests where practical for:

- lazy tab construction state
- startup/status message helpers
- banner state normalization and colors
- Needs Attention helper output
- Dashboard summary helper behavior
- Mods first-load guard
- hosted diagnostics wording helpers
- support diagnostics still redact secrets
- no regression in existing install/uninstall/restore/profile tests

Always run:

- `python -m compileall windrose_deployer -q`
- `python -m pytest -q`
- `git diff --check`

## Manual Smoke Checklist

1. Cold-launch app.
2. Confirm loading shell/status appears quickly.
3. Confirm the app-level banner shows startup and routine action results.
4. Confirm Dashboard loads and shows useful actions.
5. Open Mods first time and verify lists load correctly.
6. Open Server first time and verify settings/hosted setup still work.
7. Open Activity first time and verify backups/history render.
8. Install a normal pak mod.
9. Install/uninstall a UE4SS/framework mod.
10. Run hosted setup test with FTP profile.
11. Run hosted setup test with SFTP profile.
12. Trigger a path-missing hosted error and verify wording.
13. Confirm Compact/Default/Large UI sizes do not clip primary controls.
14. Confirm Restore Vanilla still previews and refreshes Dashboard/Mods.
15. Confirm support export still redacts secrets.

## Release Criteria

Ship only when:

- startup gives immediate visible feedback
- heavy tabs are no longer all constructed before first view where feasible
- Dashboard feels useful as a home screen
- Mods empty states and labels are clearer
- Hosted setup wording is easier to follow
- common errors are actionable
- existing install/uninstall/server/hosted/framework/restore workflows still pass tests

Do not ship if:

- lazy construction causes broken cross-tab refreshes
- the loading shell hides real startup exceptions
- Mods/Server first-open behavior feels broken
- wording changes make support/debugging less precise

## Deferred After v0.7

### Load Order - Needs Validation

Load order is deferred until there is stronger evidence Windrose users need it.

If implemented later, use a managed priority/prefix model:

- user chooses priority
- app controls deployed filename prefixes
- `.pak/.utoc/.ucas` move together
- original archives stay unchanged
- no `retoc` required

### v0.8 Candidate

- Nexus metadata/update checks
- user-authorized Nexus downloads
- no silent auto-install

### Future Deep Inspection

Do not include `retoc` in v0.7.

If deeper pak/asset inspection becomes necessary later, treat it as a separate optional feature after the normal manager workflows are stable.

## One-Sentence Summary

`v0.7.0` should make Windrose Mod Manager faster to open, easier to understand, and more helpful in everyday client/server/hosted workflows without adding risky new mod-file mechanics.
