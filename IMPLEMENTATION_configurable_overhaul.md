# Windrose Configurable Overhaul System - Repo-Specific Implementation Plan

## 1. Viability Verdict

This feature is viable, but only if it is treated as a staged major feature and not a quick extension of the current archive installer.

The current repo already gives you most of the managed mod lifecycle you need:

- safe install / uninstall / backup / restore in `windrose_deployer/core/installer.py`
- tracked installs and history in `windrose_deployer/core/manifest_store.py`
- repair / verification in `windrose_deployer/core/integrity_service.py`
- target resolution and bundle install planning in `windrose_deployer/core/deployment_planner.py` and `windrose_deployer/core/target_resolver.py`
- local/hosted deployment seams in `windrose_deployer/core/remote_deployer.py`
- profile capture/compare plumbing in `windrose_deployer/core/profile_service.py`

What the repo does not have today:

- no Unreal asset patch engine
- no `retoc` wrapper
- no `.usmap` / mapping-path management
- no external-tool settings model
- no generated-build domain model
- no concept of a managed install whose source is not a normal archive file

So the manager side is viable. The real technical risk is the asset patch/build layer, not install lifecycle.

## 2. Recommended Release Placement

This should not be a `0.5.x` feature.

Recommended path:

- `0.5.2`: operator polish only
- `0.6.x`: groundwork + backend spike
- `0.6.x` or later: first end-to-end tweak builder release if the asset patch spike succeeds

If the patch-engine spike fails or stays brittle, stop before UI work and keep the result as internal tooling only.

## 3. Repo Audit Summary

### What can be reused directly

1. Managed install lifecycle
   - A generated tweak output can be tracked like any other managed mod once files exist on disk.
   - Installer already tracks installed files, overwrite backups, and uninstall restoration.

2. Backup/history/recovery
   - Build/install of generated output can append normal deployment history and backup records.

3. Profiles
   - Existing profile infrastructure can eventually include tweak-generated installs, but should not be the first implementation surface for tweak values.

4. Target model
   - Client / Local Server / Dedicated Server already exist and are stable.
   - Hosted support exists, but should be a later step for tweak-builder output.

5. Packaged app data flow
   - The app already writes mutable state to `%LOCALAPPDATA%` when frozen in `windrose_deployer/ui/app_window.py`.
   - That is compatible with runtime build output and tweak config storage.

### What is hardcoded today and must be addressed

1. Archive-only source assumptions
   - `ModInstall.source_archive` is assumed to be a real archive path in:
     - `windrose_deployer/core/integrity_service.py`
     - `windrose_deployer/core/profile_service.py`
     - `windrose_deployer/core/server_sync_service.py`
     - `windrose_deployer/core/version_hints.py`
     - `windrose_deployer/ui/tabs/mods_tab.py`
     - `windrose_deployer/ui/tabs/installed_tab.py`
   - Generated output must not be shoehorned into those paths without an explicit model change.

2. No toolchain configuration model
   - `windrose_deployer/models/app_preferences.py` only stores UI/confirmation/welcome behavior.
   - `data/settings.json` only stores `paths` and `preferences`.
   - A tweak builder needs explicit settings for `retoc`, mappings, and possibly template asset overrides.

3. No Unreal asset dependency in requirements
   - `requirements.txt` has no Unreal asset read/write library.
   - This is the main feasibility gate.

4. Packaged resources are not bundled yet
   - `windrose_mod_deployer.spec` currently bundles only icons and CustomTkinter/tkdnd assets.
   - Any template workspace or tweak definitions must be added explicitly.

## 4. Scope Boundaries

This system should stay inside these rules:

- only patch owned, supported template assets
- only patch known property paths
- only support known primitive property types at first
- only generate your own tweak output
- do not edit installed third-party mods
- do not become a generic pak editor
- do not expose raw asset browsing in the manager UI

If any design choice starts pushing toward "open any pak and edit it," cut it.

## 5. Product Shape

Keep two clear lanes.

### Lane A - existing mod manager

- import archives
- install / uninstall
- enable / disable
- repair / verify
- hosted uploads
- backups / recovery

### Lane B - configurable tweak builder

- tweak catalog UI
- generated build settings
- build and install one generated tweak mod
- reset / rebuild / remove generated output

This should become its own top-level app destination, not a hidden panel inside the current Mods archive workflow.

Recommended top-level tab name:

- `Tweaks`

## 6. Hard Gates Before Full Implementation

These are required gates. Do not skip them.

### Gate 0 - external tool / licensing decision

Decide how `retoc` is handled:

- bundled with the app, or
- user-supplied executable path

Because the repo currently vendors no such tool, the safe assumption is:

- v1 should use user-configured external tool paths

### Gate 1 - manual combined mod proof

Before building app automation:

1. manually prove one combined generated output containing:
   - one comfort tweak
   - one inventory tweak
   - one ship tweak
2. repack once
3. confirm the game loads all three together from one output bundle

If this fails, the manager should not proceed to automation yet.

### Gate 2 - patch-engine spike

Before full backend implementation:

1. create a tiny standalone patch spike in the repo
2. load one known converted template asset
3. patch one verified primitive property
4. save it
5. repack with `retoc`
6. verify in game

If this cannot be made reliable, stop and keep the workflow manual.

### Gate 3 - packaged build resource spike

Prove that the frozen EXE can:

- read bundled template assets / tweak defs
- copy them into a writable temp build folder
- generate output outside the install directory

## 7. Recommended V1 Scope

Keep V1 narrow.

### Supported tweak categories

Start with exactly three:

1. Comfort
   - proven comfort limit asset(s)

2. Inventory
   - one inventory/slot or stack tweak

3. Ship
   - one ship storage/buff tweak

### Supported value types

Only:

- `int`
- `float`
- `bool`

Defer:

- enums
- arrays
- structs
- nested complex object editing

### Supported targets in V1

Recommended V1:

- `Client`
- `Local Server`
- `Dedicated Server`

Defer for later:

- `Hosted Server`

Reason:

- the build/patch system is large enough already
- current hosted deployment is still archive-oriented or direct-upload oriented, not "generated artifact first"
- local stability should be proven before adding hosted parity

## 8. Repo-Specific Architecture

### 8.1 Bundled read-only resources

Do not store master templates under `data/`.

Recommended structure:

```text
assets/
  tweaks/
    defs/
      comfort_limit.json
      inventory_slots.json
      ship_storage.json
    templates/
      gameplay/
        comfort/
        inventory/
        ship/
```

Why:

- source mode can read these from the repo
- packaged mode can bundle them via PyInstaller
- runtime can treat them as read-only master sources

At build time, copy them into a writable temp workspace.

### 8.2 Mutable user/build state

Recommended new state files:

```text
data/
  tweak_config.json
  tweak_profiles.json
  generated_builds.json
  toolchain.json
generated/
  <build_id>/
    output/
    manifest.json
    logs/
    workspace/
```

For packaged builds, these should live under `%LOCALAPPDATA%/WindroseModDeployer/...`.

### 8.3 New domain models

Add models for:

- `TweakDefinition`
- `TweakTarget`
- `TweakConfig`
- `GeneratedBuildRecord`
- `ToolchainSettings`
- `GeneratedArtifact`

Recommended new fields on existing models:

- `ModInstall.source_kind: "archive" | "generated"` default `"archive"`
- `ModInstall.generated_build_id: str = ""`
- `DeploymentRecord.source_kind: "archive" | "generated"` default `"archive"`
- `ProfileEntry.source_kind: "archive" | "generated"` default `"archive"`

Why this is needed:

- current code assumes `source_archive` is a file path to an archive
- generated output should be represented explicitly, not faked as a missing zip

### 8.4 New core services

Recommended services:

- `TweakDefinitionStore`
- `TweakConfigStore`
- `ToolchainStore`
- `TemplateWorkspaceService`
- `RetocService`
- `AssetPatchEngine`
- `GeneratedBuildStore`
- `TweakBuilderService`
- `GeneratedModService`

Suggested files:

```text
windrose_deployer/
  models/
    tweak_definition.py
    tweak_config.py
    generated_build.py
    toolchain_settings.py
  core/
    tweak_definition_store.py
    tweak_config_store.py
    generated_build_store.py
    toolchain_store.py
    template_workspace.py
    retoc_service.py
    asset_patch_engine.py
    tweak_builder.py
    generated_mod_service.py
```

### 8.5 Patch engine strategy

This is the main technical risk.

The repo should define a narrow patch-engine interface, but keep the backend replaceable:

- input: copied template assets + tweak definitions + user values + mapping path
- output: saved edited assets in temp workspace

V1 patch engine requirements:

- patch known assets only
- patch known property paths only
- support primitive writes only
- fail loudly on unexpected asset layout or property mismatch

Do not build a generic asset editor API.

If no reliable pure-Python asset writer is available, use a very small external/helper backend instead of building a binary parser from scratch inside the current app.

### 8.6 Generated output install strategy

Do not route the first implementation through the normal archive import/library path.

Reason:

- current install, integrity, profile, sync, and UI layers assume a real archive source path
- forcing generated output into that assumption will create low-signal special cases everywhere

Recommended approach:

1. `TweakBuilderService` produces final generated files in a managed output folder
2. `GeneratedModService` installs those files directly into target `~mods` folders
3. the install is recorded in the manifest as `source_kind="generated"`
4. the UI presents it as a managed generated mod with:
   - rebuild
   - uninstall
   - open generated output
   - open build logs

Later, if needed, a generated build can also export a zip for sharing/debugging.

## 9. Implementation Slices

### Slice 0 - research catalog and proof docs

Goal:

- convert the long design note into a tracked supported-tweak catalog

Build:

- a working document under `docs/` or repo root for:
  - category
  - asset path
  - property path
  - default value
  - test value
  - in-game validation note

Acceptance:

- at least 3 verified candidate tweaks
- one per starting category

### Slice 1 - toolchain and resource foundations

Goal:

- make external tool paths and bundled tweak resources explicit

Build:

- `ToolchainSettings` model/store
- settings UI for:
  - `retoc` executable path
  - mappings / `.usmap` path or directory
  - optional output root override
- resource resolver for bundled tweak defs/templates
- PyInstaller spec updates to bundle tweak resources

Acceptance:

- source mode and packaged mode both resolve tweak resources correctly
- tool paths persist safely

### Slice 2 - generated source model compatibility

Goal:

- teach the app that a managed install can be generated, not archive-backed

Build:

- `source_kind` compatibility fields on:
  - `ModInstall`
  - `DeploymentRecord`
  - `ProfileEntry`
- backward-compatible defaults for old data
- UI-safe handling for generated installs in:
  - Mods
  - Installed details
  - Recovery / history
  - version hints
  - server sync

Acceptance:

- old manifests still load unchanged
- generated installs do not pretend to have an archive to inspect/reinstall

### Slice 3 - backend build pipeline

Goal:

- automate the build from tweak config to generated output

Build:

- tweak definition loader
- tweak config loader
- template copy into temp workspace
- patch-engine invocation
- `retoc` wrapper
- generated build record/log capture

Pipeline:

1. load current tweak config
2. copy bundled templates into temp workspace
3. patch the copied assets
4. run `retoc`
5. produce final generated output
6. store build metadata

Acceptance:

- one build command can generate a tweak bundle from config without manual UAssetGUI edits

### Slice 4 - local generated install lifecycle

Goal:

- make the generated output practical and safe

Build:

- `GeneratedModService.install_generated(...)`
- backup and replace previous generated output before install
- track generated build id in manifest
- uninstall previous generated output cleanly before reinstall
- record generated install history
- "restore defaults" behavior that rebuilds and installs vanilla-supported values or removes generated output

Acceptance:

- rebuilding replaces the previous generated tweak mod cleanly
- uninstall restores state like other managed mods

### Slice 5 - Tweaks UI lane

Goal:

- expose the tweak builder as a separate, controlled workflow

Recommended UI:

- new top-level tab: `Tweaks`
- grouped categories:
  - Comfort
  - Inventory
  - Ship
- each tweak shows:
  - label
  - short description
  - vanilla/default value
  - input control
  - reset action
- bottom actions:
  - `Build & Install`
  - `Restore Defaults`
  - `Open Generated Output`
  - `Open Build Log`
  - `Open Toolchain Settings`

Do not place this inside the normal archive list.

Acceptance:

- user can change supported values, build once, and understand what was generated

### Slice 6 - generated build visibility in existing app surfaces

Goal:

- integrate the generated tweak mod into the rest of the app without confusing it with imported archives

Build:

- Mods/Applied list generated badge:
  - `Generated`
- detail panel for generated installs:
  - build id
  - target(s)
  - build timestamp
  - changed tweak values
- Recovery history titles for generated rebuild/install/remove actions
- Dashboard quick action:
  - `Open Tweaks`

Acceptance:

- generated tweak output is visible and manageable, but clearly separate from imported archives

### Slice 7 - optional tweak profiles

Goal:

- allow saving/loading named tweak settings

Build:

- separate tweak profiles store
- save current tweak config as profile
- load profile into Tweaks UI
- compare profile vs current values before apply

Important:

- do not piggyback on the existing mod-install profile system in the first implementation
- tweak profiles are simpler and should stay separate initially

Acceptance:

- users can save/load named tweak presets safely

### Slice 8 - hosted/server parity follow-up

Goal:

- extend generated output beyond local targets if the local builder is stable

Later build:

- upload generated bundle to hosted server
- reuse remote deployment/provider plumbing where practical

Do not put this into V1 unless local build/install is already solid.

## 10. Settings and Toolchain UX

The current Settings screen has no toolchain section. Add one.

Recommended new Settings tab or sub-section:

- `Toolchain`

Fields:

- `retoc executable`
- `Mappings (.usmap) path`
- `Generated output folder` (optional override)
- `Open tweak resources`
- `Run toolchain validation`

Validation should check:

- file exists
- path is executable where relevant
- mappings path exists
- bundled tweak definitions load

## 11. Integrity / Repair / Profiles Impact

These systems must be adjusted deliberately.

### Integrity

Current behavior:

- verifies installed files against original archive bytes

Generated behavior needed:

- verify against stored generated build manifest / output bytes instead

### Repair

Generated repair should:

- either rewrite from stored generated output
- or force rebuild, then reinstall

Recommended V1:

- `Repair` for generated installs becomes `Rebuild & Reinstall`

### Profiles

Current profile compare is archive-path keyed.

Generated installs should not participate in archive-based compare until:

- `source_kind` compatibility exists
- keying rules are defined

Recommended V1:

- generated tweak installs are excluded from normal mod profiles or represented as a special entry kind

## 12. Test Plan

Add tests for:

### Stores / compatibility

- `ToolchainSettings` load/save
- `TweakConfig` load/save
- `GeneratedBuildRecord` load/save
- manifest/profile compatibility with new `source_kind` defaulting to `"archive"`

### Builder internals

- tweak definition validation
- template workspace copy
- invalid property path rejection
- invalid value range rejection
- `retoc` command formation
- generated build metadata capture

### Install lifecycle

- install generated output into client/local/dedicated targets
- rebuild replaces previous generated install
- uninstall generated install removes files cleanly
- generated install history entries are recorded

### UI-safe behavior

- generated installs do not show archive-only actions
- generated installs show generated details/badges

## 13. Manual Smoke Checklist

Before shipping the first tweak-builder release:

1. Build comfort/inventory/ship tweak output from UI
2. Install to Client
3. Confirm generated files land in `~mods`
4. Launch game and verify all three tweaks in-game
5. Rebuild with changed values
6. Confirm previous generated install is replaced cleanly
7. Uninstall generated tweak mod
8. Confirm files are removed and no stale generated files remain
9. Install to Local Server and Dedicated Server
10. Confirm generated install history appears correctly
11. Confirm packaged EXE build can perform the same flow

## 14. Cut Rules

If risk grows, cut in this order:

1. hosted generated-output deployment
2. tweak profiles
3. float/bool support beyond the minimum tested fields
4. multi-target install in one click
5. advanced UI polish

Do not cut:

- template-copy build model
- managed generated install tracking
- explicit `source_kind` compatibility
- manual proof / patch-engine feasibility gates

## 15. Recommended Immediate Next Actions

1. Create a supported-tweak research document with:
   - comfort candidate
   - one inventory candidate
   - one ship candidate

2. Decide the toolchain policy:
   - user-supplied `retoc` path
   - user-supplied mappings path

3. Do the manual combined-mod proof outside the UI

4. After that, implement a backend spike only:
   - `ToolchainSettings`
   - `TweakDefinition`
   - `TweakConfig`
   - `RetocService`
   - `AssetPatchEngine` prototype
   - `GeneratedBuildRecord`

5. Only after the spike succeeds, start the full `Tweaks` UI lane

## 16. One-Sentence Summary

The configurable overhaul system is viable for this repo because the manager already has a strong managed install lifecycle, but it must be built as a separate tweak-builder lane with owned templates, explicit generated-build modeling, and a hard feasibility gate around the Unreal asset patch engine and `retoc` toolchain.
