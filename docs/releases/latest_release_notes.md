## Windrose Mod Manager v0.8.0

Windrose Mod Manager v0.8.0 focuses on archive intelligence, safer deployment planning, richer install metadata, and clearer install/sync review text.

### Highlights

- Added shared archive layout classification for standard pak archives, multi-pak bundles, multi-variant pak archives, UE4SS mods, UE4SS runtime/shim archives, config-only archives, mixed archives, and support-only archives.
- Local and hosted deployment planning now skip obvious support/metadata files such as readmes, manifests, icons, changelogs, and Thunderstore metadata.
- Config-only archives are blocked from normal mod install/upload and point users toward config workflows instead.
- Mixed archives can still deploy pak payloads, while config/support files are skipped or called out for review.
- Install records and deployment history now persist layout kind, target hint, selected variant, selected archive entries, installed archive entry paths, layout warnings, and archive hash where available.
- Diagnostics now include layout metadata without exposing secrets.
- Dashboard sync review details now use stored layout metadata when explaining selected variants/components and skipped support/config notes.
- Local install and hosted upload reviews now show layout kind, destination hint, selected entries/components, planned archive entries, and clearer warning/risk text.

### Notes

- Existing v0.7.1 behavior for selected variants, `All variants`, pak companions, UE4SS external/host-managed mode, and Review Sync Actions is preserved.
- Hosted active install tracking remains history-only in v0.8.0; hosted uploads do not yet create active hosted install records.
- Hosted uploads were smoke-tested with the real hosted planner/deploy path against a fake remote provider. Real provider behavior still depends on the host's SFTP/FTP access and paths.

### Validation

- `python -m compileall windrose_deployer -q`
- `python -m pytest -q` -> `285 passed`
- Source GUI smoke across Dashboard, Mods, Server, Activity, Settings, and Help
- Source archive/report smoke for standard pak, multi-variant pak, local install report, hosted upload report, and sync action detail
- Hosted upload smoke for standard pak, selected variant, `All variants`, mixed archive filtering, config-only blocking, and UE4SS external mode
- Packaged exe smoke launch confirmed v0.8.0 identity and startup

### SHA256

Release zip: `983798E2FFF8D31FBE8377CF0D3131352138732384CC589D665E2E452D6B707E`

### Full Changelog

https://github.com/Vercadi/windrose-mod-manager/compare/v0.7.1...v0.8.0
