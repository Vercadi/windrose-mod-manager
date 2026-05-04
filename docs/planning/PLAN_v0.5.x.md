# Windrose Mod Manager - v0.5.x Working Plan

## Release Theme

**v0.5.x = Server Operations + Parity**

The next release line should make the app better at answering:

- What is running right now?
- What mods are actually active on each target?
- How do I keep friends and servers in parity?
- How do I back up, restore, and review server activity without digging through raw files?

This is **not** a generic server panel rewrite and **not** a copy of another manager.
It should borrow the strongest ideas from server-first tools while staying grounded in the current Windrose Mod Manager layout and strengths.

## Product Direction

v0.4.0 made target naming, archive flow, and applied-state handling much clearer.

v0.5.x should build on that by making the app feel like a practical daily cockpit for:

- client play
- local server hosting
- standalone dedicated server hosting
- hosted server management
- keeping friends in sync with the right mods

## Inspiration To Borrow Carefully

Useful ideas from newer server-first Windrose tools and screenshots:

- a clear server dashboard with status cards
- backups treated as a first-class area, not a hidden safety feature
- a dedicated activity/logs area
- grouped mod cards that can expand into child files

Things **not** to copy:

- their exact visual identity, logo feel, or page structure
- a fully server-only mental model
- a full SteamCMD/server-installer product unless that becomes an intentional scope
- a built-in clone of WindrosePlus or another admin/dashboard framework

Our advantage is still:

- client + local server + dedicated server + hosted server in one app
- safer mod install/uninstall and recovery workflows
- better parity and target awareness than a pure server utility

## Core Problems To Solve

### 1. Server state is still too fragmented

The app needs a clearer at-a-glance answer for:

- Windrose game running or not
- local server running or not
- dedicated server running or not
- hosted profile connected, disconnected, or not configured
- active world / active source
- pending restart or recent apply state

### 2. Archive/install metadata is too weak for version awareness

The app still does not know enough about an installed mod to answer:

- what upstream page it came from
- what file it came from on that page
- what version tag it was supposed to be
- whether a newer version may exist

The next release line should improve metadata capture for both archives and installs.

### 3. Modular bundle archives need better control

For bundle-style archives with several related paks, users should be able to:

- inspect the bundle clearly
- install the whole bundle
- install only selected child paks
- uninstall the whole bundle
- uninstall only selected child paks when that makes sense

This is especially useful for packs like grouped QoL bundles where each pak is its own module.

### 4. The current inspect/details surface is too cramped

The bottom details tray is not a good primary inspection surface for larger or more complex bundles.

### 5. Backups and activity need a more operational feel

Users should not need to think in terms of raw backup files and technical logs when they are just trying to:

- make a backup now
- restore a recent state
- confirm what happened
- review restart/apply/upload history

### 6. Mod frameworks and dependencies are still too implicit

Some Windrose mods depend on framework-style components such as UE4SS or other runtime helpers.

The app should get better at:

- recognizing likely framework/dependency archives
- showing where they belong
- warning when a dependent mod appears to need a missing framework
- separating "framework/runtime component" from normal gameplay/content mod installs

## Proposed v0.5.0 Scope

### 1. Server Dashboard

Add a clear top-level server dashboard inside the existing app structure.

Recommended cards/sections:

- Current source: Local Server / Dedicated Server / Hosted Server
- Status:
  - Windrose client running or not
  - Local/Dedicated server running or not
  - Hosted profile connected / offline / not configured
- Active world
- Mod counts by target
- Last backup
- Last apply / last restart
- Quick actions:
  - Launch Windrose
  - Launch Dedicated Server
  - Open server folder
  - Open settings file
  - Run compare
  - Back up now

Important UX note:

- This should fit your current layout and naming.
- It should not become a separate server-only app hidden behind unrelated tabs.

### 2. Metadata & Version Awareness

Add optional metadata capture and version-awareness foundations.

Recommended first pass:

- store optional per-archive and per-install metadata:
  - Nexus mod URL
  - Nexus mod ID
  - Nexus file ID
  - version tag
  - author/source label where known
- allow users to add or edit this metadata manually when missing
- surface a simple "possible update available" signal when:
  - a newer imported archive appears to match the same mod family, or
  - the stored Nexus/file metadata indicates a newer file exists

Important scope rule:

- v0.5.0 should focus on metadata capture and simple update checks
- it does **not** need to become a full auto-download/update manager

### 3. Bundle-Aware Mod Cards

Improve archive/applied presentation for modular packs.

Goal:

- a bundle archive can expand into child paks/files
- users can act on the bundle or the child items

Recommended behavior:

- Archive card:
  - install whole bundle
  - choose selected child paks
  - inspect child list cleanly
- Applied card:
  - show installed child items
  - uninstall whole bundle
  - optionally uninstall selected child items if the archive/manifest structure supports it safely

Guardrail:

- do not turn this into manual load-order management
- keep the model archive/manifest based, not drag-drop ordering

### 4. Inspect UX Redesign

Replace the tiny bottom inspect experience for complex archives.

Preferred options:

- right-side drawer with a larger vertical space, or
- centered inspect dialog/modal for archive details, variants, conflicts, and child files

The current bottom tray can stay for lightweight details, but it should not be the only usable inspection surface for bigger packs.

### 5. Backups Become First-Class

Promote backups into a clearer operational workflow.

Recommended capabilities:

- Back up now
- Restore selected backup
- Open backup folder
- Retention / cleanup controls
- Better labels for:
  - config backup
  - world/save backup
  - mod/install recovery backup

### 6. Activity / Logs Screen

Create a clearer action history view.

Include:

- installs / uninstalls
- apply / restart actions
- hosted uploads / deletes
- backup / restore actions
- launch events where possible
- searchable technical details below or behind expansion

This should feel like an operations timeline, not just a raw console dump.

### 7. Framework & Dependency Awareness

Add a lightweight framework/runtime awareness layer.

Recommended first pass:

- recognize common framework-style packages such as UE4SS-style runtime installs
- show a distinct category/badge for framework/runtime components
- detect likely install destination differences, for example:
  - framework files into `R5\\Binaries\\Win64`
  - normal pak mods into `~mods`
- warn when a mod appears to depend on a missing framework/runtime
- avoid pretending dependency detection is perfect; keep it conservative and editable

### 8. Profiles

Add a narrow first version of Profiles as saved desired state.

Recommended first pass:

- profiles store:
  - selected mods
  - selected variants
  - target choices
  - optional server settings snapshot
  - optional world settings snapshot
- profiles should support:
  - save current state as profile
  - compare profile to current state
  - apply profile
  - delete profile

Important safety rules:

- applying a profile must always show a preview first
- profiles should not silently mass-replace state with no comparison view
- credentials and secrets should never be stored inside profiles:
  - hosted passwords
  - private keys
  - other auth secrets

Important scope rule:

- this is a narrow saved-state feature
- it is **not** a full load-order/profile ecosystem in v0.5.0

## Proposed v0.5.1 Scope

This is the right place for follow-up polish after the larger v0.5.0 workflow changes land.

### Candidate items

- scheduled backup helpers
- scheduled restart helpers
- lightweight server health cards
- more compact bundle card layouts
- richer installed mod/version visibility
- better metadata editing and update-check polish
- smarter framework/dependency hints
- profile export/import polish

### v0.5.2 polish items

- Dashboard should allow changing the active compare/source target directly so parity checks are not tied to whatever was last selected in `Server`
- Dashboard parity should add `Review Sync Actions` after compare:
  - install missing client mods to Local Server
  - install missing client mods to Dedicated Server
  - upload missing client mods to Hosted Server
  - keep server-only removal actions separate and unchecked by default
  - preview every action before writing
- Manifest drift should surface in the main UI instead of living only in the technical log
- Copy should align with the current `Activity` IA instead of telling users to go to a missing `Recovery` tab
- Activity tab performance pass:
  - faster timeline refresh
  - reduce unnecessary full timeline rebuilds
  - keep the advanced raw-backup browser lazy
- Startup performance note:
  - v0.5.2 should reduce refresh fan-out and Activity render cost where safe
  - true construction-lazy tabs are deferred because Dashboard, Mods, and Server still have direct cross-tab dependencies
  - handle true lazy construction in a separate `v0.5.3` / early `v0.6` prep pass after extracting small cross-tab coordinator/helper seams
- Hosted setup should gain compact provider-specific QoL for:
  - Host Havoc
  - Indifferent Broccoli
- FTP diagnostics should get clearer mismatch/auth/timeout/listing messages
- Metadata/setup groundwork for future mod version notifications:
  - make metadata easier to review/edit
  - improve `possible update available` hints
  - keep this metadata-first, not a full upstream checker yet

### v0.5.2 release result

Shipped in `v0.5.2`:

- Dashboard compare target selector for Local Server, Dedicated Server, and Hosted Server
- preview-first `Review Sync Actions`
- safe additive client-to-local/dedicated installs via the existing install/backup/history path
- safe additive client-to-hosted uploads via the existing hosted deployment path
- server-only and hosted-only removals listed for review only
- Dashboard manifest drift visibility
- Activity / Backups copy cleanup
- Activity refresh/render cost reduction
- safer discovery when old saved Steam paths point to inaccessible drives
- FTP path-existence fallback when `SIZE` is unavailable
- clearer hosted path diagnostics for FTP-root-relative paths, including Nitrado-style setups
- provider shortcuts for Host Havoc and Indifferent Broccoli

Deferred from this pass:

- true construction-lazy tab creation
- broad Mods/Server tab decomposition
- richer metadata/version editing
- automatic per-mod update checks/downloads

## Defer For Later

These are valid ideas, but should not be part of the first v0.5.x planning pass:

- FTP support
- WindrosePlus support as an optional UE4SS-based capability layer:
  - detect it
  - install/configure it
  - open its dashboard/launcher
  - local Windows dedicated first
- Nexus API integration / auto-download
- automatic mod update tracking
- share-code or cloud-backed parity sync
- full profile/loadout matrix management
- multi-game framework extraction
- deep SteamCMD/server installer ownership
- code-signing workflow as an in-app feature
- full automatic per-mod update checking/downloading

## UX Rules For v0.5.x

1. Keep the app recognizably yours.
2. Borrow structure, not branding.
3. Prefer grouped cards and status summaries over walls of buttons.
4. Keep client/server/hosted parity obvious at all times.
5. Do not hide important safety/recovery paths behind visual cleanup.
6. If a detail view cannot be read at default window size, it is the wrong surface.
7. Do not treat framework/runtime components exactly like normal pak mods when the install path or role is different.
8. Profiles should save desired state, not credentials.

## Suggested Release Messaging

If this plan holds, the release message for v0.5.0 should sound like:

**"v0.5.0 makes Windrose Mod Manager better at running servers, understanding mod dependencies, and keeping installs easier to trust."**

Not:

- "new server manager"
- "all-in-one host panel"
- "SteamCMD automation suite"

## Decision Notes

### Bundle install/remove behavior

The strongest next improvement is:

- allow a modular archive to expand into child paks/files
- let the user choose whole-bundle or selected-child install

This is a better fit than treating every child pak as a separate completely unrelated archive row.

### Metadata-first update checks

The strongest realistic update-check path is:

- capture optional upstream metadata now
- show simple update signals when that metadata exists
- leave full automatic download/update flows for later

This is much more achievable than trying to jump straight to full Nexus-driven update automation.

### Future version notifications

A good later step is:

- notify when a newer mod version appears to exist upstream
- only when enough metadata exists to make that check credible
- keep the first release notification-only

That means:

- no auto-download
- no auto-install
- no pretending certainty when metadata is incomplete

### Framework/runtime support

The UE4SS-style use case suggests a useful next improvement:

- distinguish framework/runtime installs from normal pak installs
- show the destination clearly
- warn when a dependent mod likely needs that framework first

This should be implemented as a lightweight detection-and-guidance layer, not a massive dependency manager.

### Profiles

Profiles are reasonable as long as they stay narrow.

The right first definition is:

- a saved desired state for mods and optional settings
- compare before apply
- target-aware
- no load-order system
- no hidden secrets

This keeps the feature useful while leaving room to expand it later.

### Inspect behavior

The current inspect tray is acceptable for quick text output, but not for serious archive review.

The next implementation plan should treat this as a design problem to solve directly, not a minor tweak.

### Similarity caution

There is visible overlap now between your tool and other Windrose utilities in category, terminology, and broad dark-UI conventions.

That is another reason to keep:

- your own layout logic
- your own labels
- your own navigation priorities

The goal is to improve server operations in your product, not visually converge with theirs.
