Windrose Mod Manager v0.7.1

Short Nexus file changelog

- Added archive summaries and install/upload review text before writes.
- Added Copy Diagnostics with the latest install review included and secrets redacted.
- Added an All variants option for detected multi-pak variant archives.
- Fixed selected bundle/component installs so sync preserves the exact client setup.
- Fixed Review Sync Actions so selected client mods can sync directly to Local Server or Dedicated Server.
- Fixed duplicate active manifest rows created by repeated installs of the same target/source/variant/files.
- Improved hosted upload review wording for external/host-managed UE4SS.

Sticky update

v0.7.1 is live.

This is a focused trust and sync patch on top of v0.7.0. The main change is that the manager now explains what it found in an archive, previews what it will install, and handles variant/component sync more directly.

What changed in v0.7.1
- Mods now show an Archive Summary for selected archives.
- Installs show a review before writing files.
- Hosted uploads show a clearer upload review.
- Diagnostics now include the latest install/upload review, with passwords and private-key paths redacted.
- Multi-variant pak archives now offer All variants when the archive is really a bundle rather than one exclusive choice.
- Variant installs keep matching `.pak`, `.utoc`, and `.ucas` files together.
- Review Sync Actions now applies selected client installs directly to Local Server or Dedicated Server, including selected variants and selected bundle components.
- Duplicate active rows from repeated same-target installs are cleaned from the manager manifest.

UE4SS / hosted note
- The host-managed UE4SS path from v0.7.0 is still supported.
- If UE4SS is managed by your host/provider or installed manually, mark it external/host-managed and install UE4SS mods without replacing that runtime.

Recommended sync flow
1. Open Dashboard.
2. Pick Local Server or Dedicated Server as the compare target.
3. Click Run Compare.
4. Click Review Sync Actions.
5. Leave the actions you want checked and click Apply Selected.

Known follow-up
- Hosted sync with selected bundle components is still conservative. Use hosted upload review for those cases.

Release zip SHA256

`A62F3C6A167368C3065A856FA1F887F6B935A405588E08910AD4ECCEF23A947D`
