# Nexus Release Copy - v0.3.1

Use this for the Nexus file changelog / update post.

---

Windrose Mod Manager v0.3.1

This is a hotfix for dedicated server compatibility, hosted path setup, and a few reliability issues reported right after v0.3.0.

What is fixed in v0.3.1

- Detects the standalone Steam **Windrose Dedicated Server** install properly
- Uses the dedicated server install for local `ServerDescription.json` and world-save paths
- Reconciles older saved paths when the manager can detect the correct dedicated-server install automatically
- Improves hosted setup guidance when SFTP opens directly inside the server folder
- Apply and Restart no longer continues after a failed save
- Client/server sync compare no longer drops installs that share the same display name
- Recovery timeline no longer double-list config saves
- Settings save no longer locks the derived local server save path as a manual override

Why this matters

The biggest fix here is support for the standalone dedicated server app from Steam. If you are running a separate dedicated server machine with **Windrose Dedicated Server**, this update is the one you want.

Hosted server note

Hosted support still requires SFTP/SSH access from your provider. If your login already lands inside the server folder, you can use `.` as the Server Folder or leave it blank and use the override fields.

Validation

- `python -m pytest -q` -> 101 passed

Download

Grab v0.3.1 from the main files section or from GitHub Releases.
