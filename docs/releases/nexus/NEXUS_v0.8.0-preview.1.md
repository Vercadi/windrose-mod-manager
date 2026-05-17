Windrose Mod Manager v0.8.0-preview.1

Short Nexus file changelog

- Added smarter archive layout detection for pak bundles, pak variants, UE4SS mods/runtimes, config-only archives, and mixed archives.
- Normal installs now skip obvious support files such as readmes, manifests, icons, changelogs, and Thunderstore metadata.
- Config-only archives are blocked from normal mod install/upload instead of being written as loose mod files.
- Mixed archives now show clearer review notes and avoid deploying config/support files through the normal mod path.
- Install history now stores layout kind, selected variant/components, installed archive entries, warnings, and archive hash where available.
- Diagnostics now include layout metadata while still redacting secrets.
- Install, hosted upload, and sync reviews now show clearer layout, selection, destination, and risk details.

Sticky update

v0.8.0-preview.1 is available for testing.

This preview is focused on archive intelligence and safer deployment planning. The manager now understands more archive shapes before writing files, remembers what was selected, and explains install/sync actions more clearly.

What changed in v0.8.0-preview.1
- Archives are classified as standard pak, multi-pak bundle, multi-variant pak, UE4SS mod, UE4SS runtime/shim, config-only, mixed, or support-only.
- Pak companions (`.pak`, `.utoc`, `.ucas`) still stay together.
- Selected variants and `All variants` behavior from v0.7.1 are preserved.
- Readme/manifest/icon/changelog/Thunderstore metadata files are skipped by normal deployment planning.
- Config-only archives are not installed as mods; use config workflows or manual config editing for those.
- Mixed archives keep pak payloads deployable but call out skipped config/support files.
- Dashboard sync review now explains layout, variant/component selection, and skipped support/config notes.
- Copy Diagnostics now includes the latest layout metadata for support reports.

UE4SS / hosted note
- The host-managed UE4SS path is unchanged.
- If UE4SS is managed by your host/provider or installed manually, mark it external/host-managed and install UE4SS mods without replacing that runtime.
- Hosted uploads still do not create remote backups automatically.

Preview note
- This is a preview build. Use it if you want to test the new archive intelligence before the final v0.8.0 release.

Release zip SHA256

`0AFB74732161040D7D975E01F330B61E342318BF91532BC99B143B885D8FB137`
