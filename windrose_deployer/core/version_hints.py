from __future__ import annotations

import re
from pathlib import Path

from ..models.metadata import ModMetadata
from ..models.mod_install import ModInstall

_VERSION_RE = re.compile(r"(?:^|[-_ .])v?\d+(?:[._-]\d+)+(?:$|[-_ .])", re.IGNORECASE)
_TRAILING_ID_RE = re.compile(r"[-_]\d{6,}$")


def _family_key(name: str) -> str:
    value = (name or "").strip().lower()
    value = _VERSION_RE.sub(" ", value)
    value = _TRAILING_ID_RE.sub("", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def possible_update_hint_for_archive(entry: dict, mods: list[ModInstall]) -> str:
    metadata = ModMetadata.from_dict(entry.get("metadata"))
    entry_path = str(entry.get("path", "") or "")
    entry_name = str(entry.get("name", "") or Path(entry_path).stem)
    entry_key = _family_key(metadata.source_label or entry_name)

    for mod in mods:
        if mod.source_archive == entry_path:
            continue
        mod_meta = mod.metadata
        if metadata.nexus_mod_id and mod_meta.nexus_mod_id and metadata.nexus_mod_id == mod_meta.nexus_mod_id:
            if metadata.version_tag and mod_meta.version_tag and metadata.version_tag != mod_meta.version_tag:
                return (
                    "Possible update available: imported version "
                    f"{metadata.version_tag} differs from installed {mod_meta.version_tag}."
                )
            return "Newer imported archive may supersede an installed version."

        mod_key = _family_key(mod_meta.source_label or mod.display_name or Path(mod.source_archive).stem)
        if entry_key and mod_key and entry_key == mod_key:
            return "Newer imported archive may supersede an installed version."

    return ""
