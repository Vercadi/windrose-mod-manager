from pathlib import Path
from types import SimpleNamespace

from windrose_deployer.core.manifest_store import ManifestStore
from windrose_deployer.core.profile_service import ProfileComparison
from windrose_deployer.models.mod_install import ModInstall
from windrose_deployer.models.profile import ProfileEntry
from windrose_deployer.ui.tabs.mods_tab import ModsTab
from windrose_deployer.utils.naming import generate_mod_id


def _mod(name: str, archive: str, targets: list[str]) -> ModInstall:
    return ModInstall(
        mod_id=generate_mod_id(),
        display_name=name,
        source_archive=archive,
        targets=targets,
        installed_files=[f"C:/mods/{name}.pak"],
    )


def _var(value: str):
    return SimpleNamespace(get=lambda: value)


def test_inactive_select_all_respects_current_filter_search_and_existing_files(tmp_path):
    stack = tmp_path / "MoreStacks.zip"
    mining = tmp_path / "Mining.zip"
    missing = tmp_path / "StackMissing.zip"
    stack.write_text("zip", encoding="utf-8")
    mining.write_text("zip", encoding="utf-8")

    tab = object.__new__(ModsTab)
    tab.app = SimpleNamespace(manifest=ManifestStore(tmp_path / "data"))
    tab._library = [
        {"path": str(stack), "name": "More Stacks", "ext": ".zip"},
        {"path": str(mining), "name": "Mining", "ext": ".zip"},
        {"path": str(missing), "name": "Stack Missing", "ext": ".zip"},
    ]
    tab._search_var = _var("stack")
    tab._filter_var = _var("Available Archives")
    tab._scope_var = _var("all")
    tab._selected_archive_paths = set()
    refreshes = []
    results = []
    tab._refresh_library_ui = lambda refresh_applied=False: refreshes.append(refresh_applied)
    tab._set_result = lambda text, *, level="info": results.append((text, level))

    ModsTab._select_all_inactive_archives(tab)

    assert tab._selected_archive_paths == {str(stack)}
    assert refreshes == [False]
    assert results == [("Selected 1 inactive mod(s) in the current list.", "info")]


def test_active_select_all_respects_current_target_scope_and_live_bundles(tmp_path):
    manifest = ManifestStore(tmp_path / "data")
    client = _mod("ClientOnly", "client.zip", ["client"])
    server = _mod("ServerOnly", "server.zip", ["server"])
    dedicated = _mod("DedicatedOnly", "dedicated.zip", ["dedicated_server"])
    for mod in (client, server, dedicated):
        manifest.add_mod(mod)

    tab = object.__new__(ModsTab)
    tab.app = SimpleNamespace(manifest=manifest)
    tab._scope_var = _var("client")
    tab._selected_mod_ids = set()
    tab._selected_live_files = set()
    tab._live_file_bundle_members = {"client-live": [Path("Manual_P.pak")]}
    refreshes = []
    results = []
    tab._refresh_applied_ui = lambda: refreshes.append("active")
    tab._set_result = lambda text, *, level="info": results.append((text, level))

    ModsTab._select_all_active_mods(tab)

    assert tab._selected_mod_ids == {client.mod_id}
    assert tab._selected_live_files == {"client-live"}
    assert refreshes == ["active"]
    assert results == [("Selected 2 active item(s) in the current target.", "info")]


def test_hosted_select_all_uses_current_loaded_hosted_inventory():
    tab = object.__new__(ModsTab)
    tab._scope_var = _var("hosted")
    tab._selected_mod_ids = {"stale-local"}
    tab._selected_live_files = set()
    tab._live_file_bundle_members = {
        "hosted::/mods/A.pak": ["/mods/A.pak"],
        "hosted::/mods/B.pak": ["/mods/B.pak"],
    }
    tab._last_hosted_inventory_profile_name = "Hosted Smoke"
    tab._last_hosted_inventory_files = ["/mods/A.pak", "/mods/B.pak"]
    tab._last_hosted_inventory_error = None
    renders = []
    results = []
    tab._render_hosted_inventory = lambda name, files, error=None: renders.append((name, files, error))
    tab._set_result = lambda text, *, level="info": results.append((text, level))

    ModsTab._select_all_active_mods(tab)

    assert tab._selected_mod_ids == set()
    assert tab._selected_live_files == {"hosted::/mods/A.pak", "hosted::/mods/B.pak"}
    assert renders == [("Hosted Smoke", ["/mods/A.pak", "/mods/B.pak"], None)]
    assert results == [("Selected 2 active item(s) in the current target.", "info")]


def test_profile_plan_applies_local_targets_and_reviews_hosted_targets():
    tab = object.__new__(ModsTab)
    hosted_mod = _mod("HostedOnly", "hosted.zip", ["hosted"])
    dedicated_mod = _mod("DedicatedOnly", "dedicated.zip", ["dedicated_server"])
    comparison = ProfileComparison(
        to_install=[
            ProfileEntry(display_name="ClientOnly", source_archive="client.zip", targets=["client"]),
            ProfileEntry(display_name="HostedOnly", source_archive="hosted.zip", targets=["hosted"]),
            ProfileEntry(display_name="Mixed", source_archive="mixed.zip", targets=["client", "hosted"]),
        ],
        to_uninstall=[hosted_mod, dedicated_mod],
    )

    plan = ModsTab._profile_local_plan(tab, comparison)

    assert [(entry.display_name, targets) for entry, targets in plan["to_install"]] == [
        ("ClientOnly", ["client"]),
        ("Mixed", ["client"]),
    ]
    assert [entry.display_name for entry in plan["review_install"]] == ["HostedOnly", "Mixed"]
    assert [mod.display_name for mod in plan["to_uninstall"]] == ["DedicatedOnly"]
    assert [mod.display_name for mod in plan["review_uninstall"]] == ["HostedOnly"]

    preview = ModsTab._profile_preview_text(tab, SimpleNamespace(name="Smoke"), comparison)
    assert "Review separately" in preview
    assert "Hosted or unsupported profile entries are not auto-applied" in preview


def _profile_apply_harness(monkeypatch):
    tab = object.__new__(ModsTab)
    hosted_mod = _mod("HostedOnly", "hosted.zip", ["hosted"])
    dedicated_mod = _mod("DedicatedOnly", "dedicated.zip", ["dedicated_server"])
    comparison = ProfileComparison(
        to_install=[
            ProfileEntry(display_name="ClientOnly", source_archive="client.zip", targets=["client"]),
            ProfileEntry(display_name="HostedOnly", source_archive="hosted.zip", targets=["hosted"]),
        ],
        to_uninstall=[hosted_mod, dedicated_mod],
    )
    installed_plans = []
    uninstalled = []
    added_mods = []
    records = []
    results = []
    refreshed = []

    class _Manifest:
        def list_mods(self):
            return []

        def add_mod(self, mod):
            added_mods.append(mod)

        def add_record(self, record):
            records.append(record)

        def remove_mod(self, mod_id):
            records.append(("removed", mod_id))

    class _Installer:
        def install(self, plan):
            installed_plans.append(plan)
            return _mod("ClientOnly", "client.zip", ["client"]), ("installed", plan)

        def uninstall(self, mod):
            uninstalled.append(mod.display_name)
            return ("uninstalled", mod.mod_id)

    monkeypatch.setattr("windrose_deployer.ui.tabs.mods_tab.inspect_archive", lambda _path: object())
    tab.app = SimpleNamespace(
        profile_service=SimpleNamespace(compare=lambda _profile, _mods: comparison),
        manifest=_Manifest(),
        installer=_Installer(),
        confirm_action=lambda *_args: True,
        refresh_installed_tab=lambda: refreshed.append("installed"),
        refresh_backups_tab=lambda: refreshed.append("backups"),
    )
    tab._prepare_install_target = lambda _info, _name, target, _variant, _selected=None: (target.value, None)
    tab.refresh_view = lambda: refreshed.append("mods")
    tab._set_result = lambda text, *, level="info": results.append((text, level))
    return tab, installed_plans, uninstalled, added_mods, refreshed, results


def test_apply_profile_keeps_extra_mods_unless_removal_enabled(monkeypatch):
    tab, installed_plans, uninstalled, added_mods, refreshed, results = _profile_apply_harness(monkeypatch)

    ModsTab._apply_profile(tab, SimpleNamespace(name="Smoke", entries=[object()]))

    assert installed_plans == ["client"]
    assert uninstalled == []
    assert [mod.display_name for mod in added_mods] == ["ClientOnly"]
    assert refreshed == ["installed", "backups", "mods"]
    assert results == [("Applied profile installs. Installed 1, removed 0. 2 extra active item(s) were left installed.", "warning")]


def test_apply_profile_can_remove_extra_local_mods_when_explicitly_enabled(monkeypatch):
    tab, installed_plans, uninstalled, added_mods, refreshed, results = _profile_apply_harness(monkeypatch)

    ModsTab._apply_profile(tab, SimpleNamespace(name="Smoke", entries=[object()]), remove_extra_mods=True)

    assert installed_plans == ["client"]
    assert uninstalled == ["DedicatedOnly"]
    assert [mod.display_name for mod in added_mods] == ["ClientOnly"]
    assert refreshed == ["installed", "backups", "mods"]
    assert results == [("Applied local profile changes. Installed 1, removed 1. 2 hosted/unsupported item(s) need review.", "warning")]
