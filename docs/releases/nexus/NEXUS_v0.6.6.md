Windrose Mod Manager v0.6.6

Short Nexus file changelog

- Added Restore Vanilla for Client, Local Server, and Dedicated Server.
- Restore Vanilla previews managed mods, unmanaged ~mods files, and known framework files before removing anything.
- Restore Vanilla backs up unmanaged files and framework files before deletion.
- Restore Vanilla does not touch saves, server settings, hosted files, inactive archives, or backup history.
- Added Select All for Active Mods and Inactive Mods, scoped to the current target/filter/search.
- Improved Profiles so creating a new profile and updating an existing profile are separate actions.
- Profile apply no longer removes extra active mods unless you explicitly enable that option.
- Hosted entries in mod Profiles remain review-only/deferred.

Sticky update

May 2:
v0.6.6 is live.

This update adds a safer cleanup workflow and includes the recent Select All / Profiles quality-of-life work.

What changed in v0.6.6
- New Restore Vanilla action for Client, Local Server, and Dedicated Server.
- Restore Vanilla lets you clean one local target without manually deleting files.
- The preview is split into:
  - Managed mods
  - Unmanaged ~mods files
  - Framework files
  - Not touched
- Framework cleanup is unchecked by default because it can remove UE4SS, RCON, and WindrosePlus files.
- Backups are created before unmanaged/framework files are removed.
- Saves, worlds, server settings, hosted files, inactive archives, and backup history are not touched.
- Added Select All for Active Mods and Inactive Mods.
- Select All respects the current target tab/filter/search instead of selecting unrelated rows.
- Profiles are easier to use now with separate New / Save as New / Update Selected actions.
- Applying a profile no longer removes extra active mods unless you explicitly enable that option.

Use Restore Vanilla when Dashboard says framework files are still present but Active Mods is empty. That usually means files exist on disk outside the manager manifest.

Hosted/remote Restore Vanilla is not included yet. For hosted servers, keep using normal hosted remove/upload actions for now.
