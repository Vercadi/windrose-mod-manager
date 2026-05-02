# v0.6.5 Implementation Plan - Bulk Selection and Profiles UX

## Goal

`v0.6.5` is a focused quality-of-life release before `v0.7` load order work.

It should solve two user-facing pain points:

- users want an obvious `Select All` flow so they can bulk install/uninstall without ticking every row
- users want named profiles for switching between a heavy single-player setup and a smaller friends/server setup

This release should not add load order, Nexus auto-download, `retoc`, generic modpack sharing, hosted sync automation, or a large visual rewrite.

## UX Research Decisions

### Select All wording

Use `Select All`.

Do not use `Select Visible` in the UI. It is technically precise but reads awkwardly and can sound like only rows currently visible before scrolling.

Behavior:

- `Select All` applies to the current list context:
  - current target scope: `All`, `Client`, `Local Server`, `Dedicated Server`, or `Hosted Server`
  - current active/inactive panel
  - current inactive filter/search
- it includes matching rows below the scroll, not only rows physically on screen
- it does not select rows hidden by a different scope/filter/search

Supporting copy:

- Active Mods hint: `Select All uses the current target filter.`
- Inactive Mods hint: `Select All uses the current target/filter/search.`

### Bulk action safety

Do not add a primary `Uninstall All` destructive button.

The safer pattern is:

1. user clicks `Select All`
2. selected count updates
3. user clicks `Uninstall Selected`
4. destructive confirmation explains count and scope

This keeps the workflow fast while preventing accidental global removals.

### Button layout

Do not cram more controls into the existing one-line panel headers.

The current Mods tab already has dense controls:

- Active Mods header has summary, selected count, `Uninstall Selected`, and `Clear`
- Inactive Mods header has `Add`, filter dropdown, `Refresh`, search, selected count, `Install`, and `Clear`

Adding `Select All` and `Profiles` to those same rows risks clipping/cropping at default and large UI sizes.

Use a two-row action layout:

- title/summary row stays compact
- action row contains bulk controls
- long-running or less common actions move to secondary/overflow placement where needed

Only increase default window size if the revised two-row layout still clips at `Default` and `Large` UI sizes.

Current baseline:

- window geometry: `1280x860`
- minimum size: `1040x700`

Acceptable adjustment if required:

- default geometry: `1360x900`
- minimum size: keep near `1040x700` unless controls still crop

## Current Code Audit

### Existing bulk selection foundation

`ModsTab` already has the selection state needed:

- `_selected_archive_paths`
- `_selected_mod_ids`
- `_selected_live_files`
- `_on_install_selected_archives()`
- `_on_uninstall_selected_mods()`

`Uninstall Selected` already handles:

- managed active installs
- unmanaged live local files
- hosted live inventory files through `delete_remote_files`

Missing piece:

- no button/helper selects all rows in the current active or inactive context

### Existing profile foundation

Profiles already exist in backend code:

- `Profile`
- `ProfileEntry`
- `ProfileStore`
- `ProfileService`
- profile save/load/compare tests

`ModsTab` also contains a profile dialog implementation:

- save current state
- compare selected profile
- apply selected profile
- delete profile

Risk:

- the profile dialog is not currently discoverable from the main Mods/Dashboard UI
- hosted targets are not mapped through `_target_enum_for_value`, so first-pass profile apply should stay local-target only

## Scope

### Slice 1 - Active Mods Select All

Goal:

Make bulk uninstall obvious and safe.

Implement:

- add `Select All` button in the Active Mods panel action row
- select all active rows matching the current target scope
- include unmanaged live file bundles shown in the current active list
- include hosted live inventory rows when the current scope is `Hosted Server`
- keep `Clear` to undo selection
- keep `Uninstall Selected` disabled until at least one row is selected
- after selecting all, selected count updates immediately

Important behavior:

- when scope is `Client`, only client active rows are selected
- when scope is `Local Server`, only local server active rows are selected
- when scope is `Dedicated Server`, only dedicated server active rows are selected
- when scope is `Hosted Server`, only loaded hosted inventory rows are selected
- when scope is `All`, all currently represented local active groups are selected

Acceptance:

- user can uninstall all active mods in a specific target without manually ticking every row
- user cannot accidentally uninstall hidden targets when a narrower scope is active
- hosted bulk remove still uses existing hosted delete confirmation/path

### Slice 2 - Inactive Mods Select All

Goal:

Make bulk install obvious and safe.

Implement:

- add `Select All` button in the Inactive Mods panel action row
- select all inactive rows matching:
  - current target scope
  - current inactive filter dropdown
  - current search text
- keep `Clear` to undo selection
- rename inactive `Install` button to `Install Selected`
- after selecting all, selected count updates immediately

Important behavior:

- if user searches `stack`, `Select All` selects only inactive mods matching `stack`
- if filter is `Available Archives`, it selects only available inactive archives
- if filter/scope hides an archive, it must not be selected

Acceptance:

- user can bulk install all currently filtered inactive mods
- button text makes the selected-based behavior clear
- duplicate/manager-owned archive behavior remains unchanged

### Slice 3 - Mods Tab Layout Cleanup

Goal:

Add selection controls without clipping/cropping.

Implement:

- Active panel:
  - row 0: `Active Mods`, active summary, selected count
  - row 1: `Select All`, `Uninstall Selected`, `Clear`
- Inactive panel:
  - row 0: `Inactive Mods`, `Add`, filter dropdown, `Refresh`
  - row 1: search field, selected count, `Select All`, `Install Selected`, `Clear`
- keep buttons compact and consistent with `ui_tokens.compact_button_height`
- ensure labels truncate/wrap gracefully instead of pushing buttons off-screen
- test at `Compact`, `Default`, and `Large` UI size settings

If controls still crop:

- first reduce button widths and move `Refresh` to secondary/right edge
- then consider default geometry bump to `1360x900`
- do not increase widget scaling as a substitute for layout fixes

Acceptance:

- no button clipping at default window size and default UI size
- no severe clipping at large UI size
- keyboard/mouse flow remains simple

### Slice 4 - Profile Entry Point

Goal:

Make profiles discoverable.

Implement:

- add a visible `Profiles` button in the Mods toolbar, near `Show Details`
- optionally add a smaller Dashboard quick action: `Profiles`
- do not add a full profile dropdown yet unless layout remains clean
- opening `Profiles` uses the existing profile dialog

Preferred wording:

- button: `Profiles`
- empty-state copy: `Save the current mod setup as a profile, then compare or apply it later.`

Acceptance:

- a user can find profiles without knowing the hidden dialog exists
- no toolbar clipping at default size

### Slice 5 - Profile Safety and Local Target Scope

Goal:

Make profiles useful for single-player vs friends/server setups without risky hosted automation.

Implement/verify:

- profile save captures active managed mods and their targets
- profile apply supports:
  - `Client`
  - `Local Server`
  - `Dedicated Server`
- profile apply previews before changing anything
- profile preview clearly shows:
  - `Will install`
  - `Will uninstall`
  - `Missing source archives`
  - target labels
- profile apply skips/defer hosted entries with clear wording
- do not store hosted credentials or secrets in profiles
- do not include server/world settings snapshots in the first UX pass unless already safe and clearly optional

Recommended first-pass behavior for hosted:

- if a profile contains hosted entries, show them under `Review separately`
- do not auto-upload/delete hosted files from profile apply in `v0.6.5`

Acceptance:

- user can create:
  - `Single Player` profile with many `Client` / `Client + Local Server` mods
  - `Friends Server` profile with fewer `Client + Dedicated Server` mods
- applying a profile cannot silently delete or upload hosted files
- missing archive sources block install for those entries and are clearly reported

### Slice 6 - Profile UX Copy

Goal:

Explain profiles in user terms.

Add small help text inside the profile dialog:

`Profiles save which managed mods are active and where they are installed. Use them for setups like Single Player, Friends Server, or Testing. Applying a profile previews installs and uninstalls before changing files.`

Add profile preview wording:

- `This profile changes local targets only. Hosted server changes must be reviewed separately.`
- only show that line when hosted entries are present or omitted

Acceptance:

- users understand that profiles switch mod setups
- users do not confuse app profiles with hosted connection profiles

## Tests

Add or update tests where practical:

- `Select All` inactive uses `_filtered_entries()` and respects search/filter/scope
- `Select All` active uses current scope and does not select hidden target rows
- `Select All` active includes unmanaged live bundles for current target
- hosted `Select All` selects currently loaded hosted inventory bundle IDs only
- profile save/compare/apply local-target behavior remains compatible
- profile apply skips or reports hosted entries instead of silently ignoring them
- profile store remains backward compatible

Run:

```powershell
python -m compileall windrose_deployer -q
python -m pytest -q
git diff --check
```

## Manual Smoke Checklist

1. Open Mods at default window size and default UI size.
2. Confirm Active Mods header/action row does not clip.
3. Confirm Inactive Mods header/action row does not clip.
4. Switch UI Size to `Large`; confirm controls remain usable.
5. In `Client` scope, click Active `Select All`; confirm only client rows are selected.
6. In `Dedicated Server` scope, click Active `Select All`; confirm only dedicated rows are selected.
7. In `All` scope, click Active `Select All`; confirm all local active rows are selected.
8. Click `Clear`; confirm active selection clears.
9. Search inactive mods; click Inactive `Select All`; confirm only matching inactive rows are selected.
10. Click `Install Selected`; confirm normal install target dialog/flow still works.
11. Click `Uninstall Selected`; confirm destructive confirmation appears and count is correct.
12. Open `Profiles` from Mods.
13. Save current setup as `Single Player`.
14. Change active mods.
15. Save another setup as `Friends Server`.
16. Compare each profile and confirm install/uninstall preview is understandable.
17. Apply a local-target profile and verify active/inactive lists update.
18. Verify hosted entries are not silently uploaded/deleted by profile apply.

## Cut Rules

If scope grows too much, cut in this order:

1. Dashboard profile shortcut
2. hosted profile entry reporting
3. default window size bump
4. profile settings snapshots

Do not cut:

- Active `Select All`
- Inactive `Select All`
- visible `Profiles` entry point
- preview before profile apply

## Release Notes Draft

- Added `Select All` to Active Mods and Inactive Mods, scoped to the current target/filter/search.
- Renamed inactive bulk install action to `Install Selected`.
- Made saved mod profiles easier to access from the Mods screen.
- Improved profile copy and preview flow for switching between setups like Single Player and Friends Server.
- Kept profile apply preview-first so installs/uninstalls are shown before files change.
