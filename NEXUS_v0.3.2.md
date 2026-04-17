# Nexus Release Copy - v0.3.2

Use this for the Nexus file changelog / update post.

---

Windrose Mod Manager v0.3.2

This is a follow-up hotfix to v0.3.1, mainly focused on hosted smoke-test fixes, dedicated-server wording clarity, and a small Settings UI cleanup.

What is fixed in v0.3.2

- The launch bar now clearly says **Launch Dedicated Server**
- Hosted Profiles in Settings expand and scroll properly
- Hosted world settings can now be saved even when the server-generated world file starts with a blank World Name
- World Name is now editable in the Server screen
- Hosted connection tests no longer fail just because the default `R5/Content/Paks/~mods` folder has not been created yet
- Hosted mod inventory now shows an empty state instead of an error for the missing default first-run `~mods` folder
- Explicit Mods Folder Override paths are still validated strictly, so a typo in a custom override is reported correctly

Why this matters

This hotfix makes the localhost / self-hosted smoke path much smoother without weakening validation for people who use custom hosted override paths.

Validation

- `python -m pytest -q` -> 107 passed

Download

Grab v0.3.2 from the main files section or from GitHub Releases.
