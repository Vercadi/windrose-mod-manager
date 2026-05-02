# Windrose Mod Manager - v0.7.0 Load Order Implementation Plan

## Release Goal

`v0.7.0` should add practical load-order control without turning the manager into a pak editor and without depending on `retoc`.

The user-facing model should be simple:

- users set a mod priority
- the manager handles deployed filenames
- original archives are never modified
- companion files are always kept together

This release should focus on safe filename-prefix-based ordering for managed mods. Deep asset inspection is deferred unless a later release proves it is needed and low-risk.

## Non-Goals

Do not implement:

- patching or mutating third-party pak contents
- special-case `_P` removal as a normal workflow
- manual filename editing as the primary UX
- arbitrary user scripts for ordering
- load-order promises that are not backed by Windrose/UE behavior
- automatic conflict resolution without user review
- `retoc` integration
- deep `.pak/.utoc/.ucas` asset inspection

## User Experience

### Priority Model

Users should see a clear priority field, not filenames.

Recommended first UI:

- `Low`
- `Normal`
- `High`
- optional advanced numeric value later

Recommended backend mapping:

- `Low` -> `010_`
- `Normal` -> `050_`
- `High` -> `090_`

If numeric priority is added later, constrain it to a safe range such as `0-999`.

### Display Rules

The UI should show:

- current priority
- deployed filename
- original filename
- target
- whether a mod has companion files
- whether a priority change is pending

The UI should not require users to understand `_P`, `.utoc`, or `.ucas` naming to use the feature.

## Backend Behavior

### Filename Strategy

The manager should preserve original names by default and add a managed prefix.

Example:

```text
Original:
MoreStacks_100x_P.pak

Deployed:
050_MoreStacks_100x_P.pak
```

For companion groups, every companion must use the same base name:

```text
050_MyMod_P.pak
050_MyMod_P.utoc
050_MyMod_P.ucas
```

The source archive remains unchanged.

### Companion Group Rules

Treat these as one deployable group:

- `.pak`
- `.utoc`
- `.ucas`

Priority changes must rename/redeploy the whole group together. A partial rename is a release blocker.

### `_P` Handling

Preserve `_P` and the rest of the original filename by default.

Do not add normal UI for removing `_P`. If specific mods prove they need that behavior, handle it later as an advanced compatibility override with clear warnings.

## Data Model

Add optional fields in a backward-compatible way.

Likely fields on install/deployment records:

- `load_order_priority`
- `original_deployed_name`
- `current_deployed_name`
- `load_order_prefix`
- `companion_group_id`
- `companion_files`

Compatibility rules:

- old installs default to `Normal`
- old deployed filenames remain valid
- no existing manifest should fail to load
- unmanaged live files should be shown as unmanaged until adopted/reinstalled

## Operations

### Apply Priority Change

Flow:

1. User changes priority.
2. App previews filename changes.
3. App checks for collisions.
4. App renames/redeploys all companion files together.
5. App records history.
6. App refreshes installed/live scan.

### Safety

Must include:

- backup before replacing an existing deployed file
- collision checks before rename/redeploy
- rollback if any companion file operation fails
- manifest/history entry for the change
- recovery path to previous deployed name/order

### Hosted Servers

Hosted load order should use the same model, but via FTP/SFTP file operations.

Rules:

- preview first
- rename/redeploy companion groups together
- keep FTP restart messaging honest
- do not require shell access

If remote rename is not supported safely by the provider abstraction, implement hosted priority changes as upload new names then delete old tracked names after successful upload.

## Conflict Awareness

Conflict awareness in this release should stay filename/target based.

States:

- `filename conflict`
- `load order may decide winner`
- `same deployed filename`
- `same loose-file target`

Wording must avoid overclaiming. The app can help users control priority, but it should not claim every conflict is safely solved.

## Deep Inspection Deferred

Do not add `retoc` in `v0.7.0`.

Reason:

- load order can be useful without unpacking or inspecting pak contents
- adding external toolchain setup increases support cost
- the manager should first prove the simpler priority/deployed-filename model

If asset-level inspection returns later, treat it as a separate release and keep it optional.

## Implementation Slices

### Slice 1 - Data Compatibility

Add optional load-order fields with default values.

Acceptance:

- old manifests load
- new installs can store priority and deployed filename metadata

### Slice 2 - Companion Group Detection

Group `.pak`, `.utoc`, and `.ucas` by base name during install/live scan.

Acceptance:

- a UE5 bundle is shown and operated on as one group
- priority changes cannot split companions

### Slice 3 - Local Priority Apply

Implement preview and apply for local targets.

Targets:

- Client
- Local Server
- Dedicated Server

Acceptance:

- priority changes rename/redeploy tracked files safely
- rollback works on failure

### Slice 4 - Hosted Priority Apply

Implement hosted priority changes through FTP/SFTP where safe.

Acceptance:

- hosted tracked files can be reordered without shell access
- failed remote operations leave old files intact where possible

### Slice 5 - UI Integration

Add priority controls to the applied mod workflow.

Recommended UI:

- priority dropdown on applied mod details
- context menu:
  - `Set Priority -> Low`
  - `Set Priority -> Normal`
  - `Set Priority -> High`
- preview dialog before apply

Acceptance:

- user never needs to manually rename files
- filename details are visible but secondary

## Tests

Automated tests should cover:

- old manifest compatibility
- priority prefix generation
- companion group detection
- local rename/redeploy plan
- collision detection
- rollback behavior
- hosted upload-new/delete-old plan

Manual smoke tests should cover:

1. Install one pak-only mod.
2. Change priority to High.
3. Verify deployed filename prefix changes.
4. Uninstall and confirm tracked files are removed.
5. Install a `.pak/.utoc/.ucas` group.
6. Change priority and confirm all companion names change together.
7. Attempt a collision and confirm it is blocked before writes.
8. Hosted priority change over SFTP.
9. Hosted priority change over FTP if supported.
10. Verify basic install/uninstall is unaffected.

## Release Criteria

Ship only when:

- users can control load order by priority
- no third-party pak contents are modified
- companion files stay together
- old manifests load
- priority changes are previewed and tracked
- normal install/uninstall remains unaffected
- no external `retoc` setup is required

Do not ship if:

- priority changes can orphan `.utoc/.ucas` files
- `_P` removal is required for the normal path
- hosted failure can leave duplicate tracked files without clear recovery
- missing `retoc` blocks basic load-order controls

## One-Sentence Summary

`v0.7.0` should make load order a managed priority system: users choose priority, the app controls deployed filename prefixes, companion files move together, and original archives remain untouched.
