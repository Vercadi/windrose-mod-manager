from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ServerConfig:
    """Model for ServerDescription.json."""
    version: int = 0
    deployment_id: str = ""
    persistent_server_id: str = ""
    invite_code: str = ""
    is_password_protected: bool = False
    password: str = ""
    server_name: str = ""
    world_island_id: str = ""
    max_player_count: int = 8
    p2p_proxy_address: str = ""
    _raw: dict = field(default_factory=dict, repr=False)

    def to_json_dict(self) -> dict[str, Any]:
        """Build the JSON structure that matches ServerDescription.json."""
        out = dict(self._raw) if self._raw else {}
        out["Version"] = self.version
        out["DeploymentId"] = self.deployment_id
        persistent = out.get("ServerDescription_Persistent", {})
        persistent["PersistentServerId"] = self.persistent_server_id
        persistent["InviteCode"] = self.invite_code
        persistent["IsPasswordProtected"] = self.is_password_protected
        persistent["Password"] = self.password
        persistent["ServerName"] = self.server_name
        persistent["WorldIslandId"] = self.world_island_id
        persistent["MaxPlayerCount"] = self.max_player_count
        persistent["P2pProxyAddress"] = self.p2p_proxy_address
        out["ServerDescription_Persistent"] = persistent
        return out

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> ServerConfig:
        p = d.get("ServerDescription_Persistent", {})
        return cls(
            version=d.get("Version", 0),
            deployment_id=d.get("DeploymentId", ""),
            persistent_server_id=p.get("PersistentServerId", ""),
            invite_code=p.get("InviteCode", ""),
            is_password_protected=p.get("IsPasswordProtected", False),
            password=p.get("Password", ""),
            server_name=p.get("ServerName", ""),
            world_island_id=p.get("WorldIslandId", ""),
            max_player_count=p.get("MaxPlayerCount", 8),
            p2p_proxy_address=p.get("P2pProxyAddress", ""),
            _raw=d,
        )

    def validate(self) -> list[str]:
        """Return a list of validation error strings (empty == valid)."""
        errors: list[str] = []
        if len(self.invite_code) < 6:
            errors.append("InviteCode must be at least 6 characters.")
        if self.max_player_count < 1:
            errors.append("MaxPlayerCount must be a positive integer.")
        if not self.p2p_proxy_address.strip():
            errors.append("P2pProxyAddress must not be empty.")
        if not self.server_name.strip():
            errors.append("ServerName must not be empty.")
        return errors
