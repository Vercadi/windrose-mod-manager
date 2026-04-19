# Windrose Mod Manager - v0.5.1 Implementation Brief

## Release Goal

**v0.5.1 should make the app faster to open, make Dashboard worth having, and expand hosted-server support for the providers users are actually asking about.**

This pass is focused on three practical upgrades:

- faster startup and less "heavy" feeling on first open
- a real operations-first Dashboard instead of a placeholder summary tab
- hosted transport support that matches real providers:
  - Host Havoc
  - Indifferent Broccoli

This release should **not** become:

- a full server panel clone
- a generic remote-file browser
- a broad hosting-provider integration layer
- a shell/SSH automation suite for every provider
- a risky rewrite of existing hosted config/install logic

## Locked Decisions Before Implementation

These are fixed for this pass unless a concrete blocker appears during coding:

- Startup target:
  - visible, usable main window in about `1 second` on the reference dev machine
  - no hosted connection tests on boot
  - no eager full refresh of every tab before the window appears
- Dashboard role:
  - Dashboard stays top-level only if it becomes the real operations home
  - it must answer "what is running, what source is active, and what needs attention?" quickly
  - if a section only repeats text from Server or Activity, cut it
- Hosted transport scope:
  - `sftp` = supported
  - `ftp` = supported
  - `ftps` = cut unless a real provider/test case forces it later
  - FTP remains file-transfer only; no restart-command support is promised there

## Provider Research

### Host Havoc

Host Havoc is mixed-transport in practice:

- their general FTP guide says some panels show `FTP Info`, while others show `SFTP Info`
- their Satisfactory mod guide explicitly says to choose `SFTP` when SFTP info is available

Product implication:

- Host Havoc support should not assume a single protocol
- the app should support **SFTP and FTP selection per hosted profile**
- protocol mismatch needs a clear error message so users do not hit confusing SSH-banner failures
- the hosted setup flow should accept Host Havoc's panel-style endpoint formats:
  - raw `host:port`
  - `sftp://host:port` when their panel exposes SFTP info
- the app must not overwrite or "simplify" an explicit Host Havoc port with a guessed default like `21` or `22`

### Indifferent Broccoli

Indifferent Broccoli's own guide says:

- all servers can be connected to using an FTP client
- hostname = server IP
- username/password = FTP credentials from server management
- port = `21 for FTP`

Product implication:

- plain **FTP support is required** if we want first-class Indifferent Broccoli support
- current SFTP-only behavior is not enough
- the hosted setup flow should make the Indifferent Broccoli path obvious:
  - protocol = `ftp`
  - host = server IP / FTP hostname
  - port = `21` unless the user explicitly changes it
  - username/password = FTP credentials from the provider panel

### Planning Inference

Based on the official provider docs reviewed here, the must-have transport scope is:

- `sftp` for Host Havoc cases where the panel exposes SFTP
- `ftp` for Host Havoc cases where the panel exposes FTP
- `ftp` for Indifferent Broccoli

No official provider documentation found in this audit requires FTPS, so FTPS should remain cuttable and out of the critical path for this pass.

### Source Links

- [Host Havoc - How to use an FTP client with your server](https://hosthavoc.com/billing/knowledgebase/488/How-to-use-an-FTP-client-with-your-server.html)
- [Host Havoc - How to install mods on your Satisfactory server](https://hosthavoc.com/billing/knowledgebase/604/How-to-install-mods-on-your-Satisfactory-server.html)
- [Indifferent Broccoli - How to use an FTP Client](https://wiki.indifferentbroccoli.com/General/FTP)

## Current Architecture Audit

### Startup path today

Current startup is still eager in a few important places:

- `windrose_deployer/ui/app_window.py`
  - `_init_services()` loads settings, reconciles paths, wires services
  - `_build_ui()` constructs every top-level tab on startup
  - `_initial_load()` refreshes Mods, Server, Dashboard, Help, and Activity immediately
- `windrose_deployer/core/discovery.py`
  - `reconcile_paths()` currently calls `discover_all()` every launch

Implementation implication:

- the first optimization pass should target eager refresh and eager discovery first
- do not guess about startup cost; use the new timing logs to measure before and after

### Hosted transport assumptions today

Current hosted logic is still SFTP-shaped in key places:

- `windrose_deployer/core/remote_deployer.py`
  - defaults provider creation to `SftpProvider`
  - restart flow calls `provider.execute(...)`
- `windrose_deployer/core/remote_config_service.py`
  - defaults provider creation to `SftpProvider`
  - remote backup source URIs are hardcoded as `sftp://...`
  - restore parsing only accepts `sftp://...`
- `windrose_deployer/models/remote_profile.py`
  - no protocol field exists yet
  - auth model is still `password` / `key`
  - restart command is part of the current model and UI

Implementation implication:

- FTP support cannot be treated as a UI-only change
- protocol-aware provider routing and protocol-aware backup identity are the real compatibility seams

### Compatibility data captured for this pass

The current local data shape is now represented by sanitized fixtures under `tests/fixtures/compat/`:

- current `settings.json` shape
- current `remote_profiles.json` shape without a protocol field
- current `app_state.json` schema 2 shape
- legacy `app_state.v1.bak.json` style shape without schema version
- current hosted backup-record shape with `sftp://...` source paths

## Final Scope

## Must-Have

### 1. Startup Performance Pass

Reduce time-to-usable-window without changing core workflows.

Must include:

- show the main window before heavy secondary refreshes complete
- avoid eager refresh of every tab during boot
- refresh only the visible/default workspace first
- lazy-load non-visible tabs on first open
- defer non-critical work to background or idle:
  - About / Help refresh
  - Activity / Recovery refresh
  - non-visible server inventory refresh
  - non-visible dashboard summaries that can wait
- add lightweight startup timing logs so packaged-build slowdowns can be diagnosed

### 2. Dashboard Rebuild

Keep Dashboard, but rebuild it as a real operations home.

Must include four compact cards:

- **Status**
  - Windrose running / not running
  - Local Server configured / running / not configured
  - Dedicated Server configured / running / not configured
  - Hosted connected / offline / not configured
- **Current Setup**
  - active source
  - active world
  - active hosted profile when relevant
  - last apply / restart / backup
- **Mod Parity**
  - counts by target
  - clear review state:
    - no compare run yet
    - review recommended
    - compare looks clean
- **Quick Actions**
  - Launch Windrose
  - Launch Dedicated Server
  - Open Client Mods
  - Open Local Server Mods
  - Open Dedicated Server Mods
  - Open Server Folder
  - Back Up Now

Design rules:

- no long low-signal text blocks
- no repeated summaries that already exist elsewhere
- no "empty admin dashboard" look
- compact, status-first, decision-first layout

### 3. Hosted Transport Expansion for Real Providers

Add hosted profile protocol support aligned with Host Havoc and Indifferent Broccoli.

Must include:

- hosted profile `protocol` field
  - `sftp`
  - `ftp`
- endpoint normalization for hosted profiles:
  - accept `host`
  - accept `host:port`
  - accept `sftp://host:port`
  - preserve explicit ports from provider panels
- existing SFTP support remains default and fully compatible
- new FTP provider for:
  - path exists
  - list entries/files
  - ensure dir
  - upload bytes
  - delete file
  - read bytes
- provider factory routing by profile protocol

Hosted setup must include:

- protocol dropdown
- protocol-specific helper text
- hide key-auth inputs when protocol is `ftp`
- default port behavior:
  - `22` only when protocol is `sftp` and no explicit port was supplied
  - `21` only when protocol is `ftp` and no explicit port was supplied
- clear guidance text for common providers:
  - Host Havoc may expose either FTP or SFTP info depending on the service/panel
  - Indifferent Broccoli uses FTP on port 21 per their guide
- input copy that says "Host / IP" rather than implying the user should enter a web panel URL

Connection-testing behavior must include:

- explicit protocol mismatch messaging
  - example: using SFTP against FTP should say the selected protocol likely does not match the host
- no more opaque "SSH banner" type failures in the UX layer
- provider-aware connection hints:
  - Host Havoc: "Use the FTP Info or SFTP Info from your panel exactly as shown."
  - Indifferent Broccoli: "Use FTP credentials from Server Management and port 21."

### 4. Hosted Config / Recovery Compatibility

Make hosted config editing and hosted recovery protocol-aware, not SFTP-hardcoded.

Must include:

- protocol-aware remote source URIs for backups/restores
- backward-compatible loading for old `sftp://...` backup source paths
- protocol-aware restore handling
- no breakage to current hosted save / restore flows

### 5. Hosted UX Cleanup

Use the new protocol support to simplify Hosted setup and make it more provider-friendly.

Must include:

- clearer hosted setup wording
- better error text when a provider only supports FTP
- clearer distinction between:
  - file access support
  - remote restart support

Important:

- FTP should support file actions
- FTP should **not** claim restart-command support if the provider does not expose remote command execution
- restart command support remains SFTP/SSH-only unless a separate command channel exists
- when protocol is `ftp`, restart-command fields and copy should be hidden or clearly marked unavailable instead of merely disabled without explanation

## Cut If Needed

These can move to `v0.5.2` if scope grows too much:

### A. FTPS

- keep this out unless a target provider actually needs it
- do not overbuild beyond Host Havoc + Indifferent Broccoli needs

### B. Rich Dashboard Polish

- animations
- charts
- process resource graphs
- advanced history widgets

### C. Background Refresh Sophistication

- periodic refresh schedulers
- aggressive cache invalidation systems
- per-card independent refresh loops

### D. Provider Presets

- prebuilt one-click templates for Host Havoc / Indifferent Broccoli
- can wait until the underlying protocol support is stable

## Explicitly Deferred

- generic multi-provider abstraction pass
- FTP command execution / restart support
- full host autodetection
- passive/active mode UI tuning unless needed by real testing
- share-code/profile ecosystem work
- Nexus auto-download

## Architecture / Data Changes

### Remote profile model

Extend `RemoteProfile` with:

- `protocol: str = "sftp"`

Likely helper additions:

- normalized endpoint parsing so provider-style host strings can be stored safely as:
  - host
  - port
  - protocol

Compatibility rule:

- existing profiles without protocol load as `sftp`

### Remote provider routing

Keep `RemoteProvider` as the stable interface.

Add:

- `FtpProvider`
- provider-router/factory logic used by:
  - `RemoteDeploymentService`
  - `RemoteConfigService`

Likely helper additions:

- hosted endpoint parser / normalizer
- protocol-aware default-port helper

### Backup / remote source identity

Current remote config recovery uses SFTP-specific source URIs.

Must change to protocol-aware handling while preserving old data.

Compatibility rule:

- old `sftp://...` records still restore
- new records include protocol-aware remote source identity

## Likely Files / Systems Affected

### UI

- `windrose_deployer/ui/app_window.py`
- `windrose_deployer/ui/tabs/dashboard_tab.py`
- `windrose_deployer/ui/tabs/server_tab.py`

### Core

- `windrose_deployer/core/discovery.py`
- `windrose_deployer/core/remote_deployer.py`
- `windrose_deployer/core/remote_config_service.py`
- `windrose_deployer/core/remote_provider.py`
- `windrose_deployer/core/sftp_provider.py`

Likely additions:

- `windrose_deployer/core/ftp_provider.py`
- protocol-aware provider factory helper
- startup timing helper or lightweight diagnostics

### Models / Storage

- `windrose_deployer/models/remote_profile.py`
- `windrose_deployer/core/remote_profile_store.py`
- hosted backup/recovery path parsing in recovery/config code

## Implementation Slices

## Slice 1 - Startup Performance Foundations

Goal:

- improve time-to-first-usable-window

Tasks:

- measure current startup timings
- reduce eager boot refresh work
- lazy-load non-visible tabs
- defer non-critical refreshes with `after(...)` or background threads

Acceptance:

- the window is usable before all secondary refreshes finish
- startup feels faster even in packaged builds

## Slice 2 - Dashboard Rebuild

Goal:

- make Dashboard a real operations home

Tasks:

- replace the current loose summary layout with four compact cards
- make parity/review state explicit
- tighten spacing and hierarchy
- remove low-value repeated text

Acceptance:

- Dashboard adds value on its own
- users can tell what is running, what source is active, and what needs attention immediately

## Slice 3 - Hosted Profile Protocol Support

Goal:

- support real provider transports cleanly

Tasks:

- add `protocol` to hosted profiles
- update load/save defaults
- add protocol selector to hosted setup
- make helper text provider-aware

Acceptance:

- existing hosted profiles still load
- users can choose FTP or SFTP explicitly

## Slice 4 - FTP Provider

Goal:

- support FTP file operations for providers like Indifferent Broccoli

Tasks:

- implement `FtpProvider` using Python `ftplib`
- support:
  - connect/login
  - list files/entries
  - read/write bytes
  - create directories
  - delete files
- prefer `MLSD` when available
- fall back to simpler directory listing methods if needed

Acceptance:

- FTP hosted inventory works
- FTP hosted upload/delete works
- FTP hosted config read/write works

## Slice 5 - Protocol-Aware Hosted Services

Goal:

- make hosted config and recovery protocol-neutral

Tasks:

- route `RemoteDeploymentService` by protocol
- route `RemoteConfigService` by protocol
- make remote source URIs protocol-aware
- preserve compatibility with old SFTP recovery records

Acceptance:

- SFTP still works unchanged
- FTP-backed hosted save/restore flows work

## Slice 6 - Hosted UX and Error Cleanup

Goal:

- remove ambiguity for users configuring third-party hosts

Tasks:

- improve test-connection messages
- detect likely protocol mismatch and say so clearly
- clarify restart support limits for FTP
- tighten Hosted setup wording around Host Havoc / Indifferent Broccoli cases

Acceptance:

- users get actionable feedback instead of low-level protocol confusion

## Recommended Build Order

1. Slice 1 - Startup Performance Foundations
2. Slice 2 - Dashboard Rebuild
3. Slice 3 - Hosted Profile Protocol Support
4. Slice 4 - FTP Provider
5. Slice 5 - Protocol-Aware Hosted Services
6. Slice 6 - Hosted UX and Error Cleanup

Reasoning:

- startup and dashboard are self-contained user-facing wins
- protocol storage must exist before FTP behavior can be wired
- FTP provider alone is not enough until config/recovery stop assuming SFTP

## Test / Validation Plan

### Must-have automated coverage

- remote profile load/save with default `protocol="sftp"`
- backward-compatible load for old profiles
- protocol-aware provider routing
- protocol-aware backup source parsing
- FTP provider file list/read/write/delete behavior via mocks
- startup lazy-refresh behavior where practical

### Must-have manual smoke tests

- cold app launch with existing settings and library
- confirm the visible main window appears in about `1 second` on the reference dev machine before secondary work finishes
- first paint / usable window timing check
- Dashboard shows useful status at default size
- Host Havoc profile:
  - paste panel `FTP Info` host:port and connect in FTP mode
  - paste / enter panel `SFTP Info` and connect in SFTP mode
  - verify an explicit non-default panel port is preserved
- Indifferent Broccoli profile:
  - FTP connection test on port 21
  - hosted mod inventory
  - hosted upload
  - hosted delete
  - hosted config load/save
- verify restart messaging stays honest for FTP
- verify existing SFTP hosted profile still works unchanged
- verify old hosted backups still restore

## Release Criteria

Ship `v0.5.1` only when:

- startup is visibly lighter than `v0.5.0`
- Dashboard clearly adds value
- Host Havoc users can choose the right protocol instead of guessing
- Indifferent Broccoli users can connect without SFTP errors
- existing SFTP hosted users are not regressed

If FTP-backed config/recovery compatibility gets risky, cut hosted config-over-FTP first and ship FTP inventory/upload/delete before destabilizing SFTP.
