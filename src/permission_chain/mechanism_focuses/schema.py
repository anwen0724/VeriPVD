from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FORBIDDEN_FOCUS_KEYS = {
    "classification",
    "confidence",
    "reason",
    "prompt",
    "finding",
    "has_finding",
    "chain_type",
    "semantic_roles",
    "diagnostics",
}


@dataclass(frozen=True)
class PermissionMechanismFocus:
    focus_id: str
    source_target_group_id: str
    members: list[dict[str, Any]]
    focus_statement_ids: list[str] = field(default_factory=list)
    equivalence_node_ids: list[str] = field(default_factory=list)
    shared_member_target_ids: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "focus_id": self.focus_id,
            "source_target_group_id": self.source_target_group_id,
            "members": list(self.members),
            "focus_statement_ids": sorted(set(self.focus_statement_ids)),
            "equivalence_node_ids": sorted(set(self.equivalence_node_ids)),
            "shared_member_target_ids": sorted(set(self.shared_member_target_ids)),
        }


@dataclass(frozen=True)
class PermissionMechanismFocuses:
    graph_id: str
    focuses: list[PermissionMechanismFocus]
    schema_version: str = "0.1"

    def to_json_dict(self) -> dict[str, Any]:
        payload = {
            "graph_id": self.graph_id,
            "schema_version": self.schema_version,
            "focuses": [focus.to_json_dict() for focus in self.focuses],
        }
        assert_no_forbidden_focus_keys(payload)
        return payload


def assert_no_forbidden_focus_keys(payload: Any) -> None:
    if isinstance(payload, dict):
        bad = FORBIDDEN_FOCUS_KEYS.intersection(payload)
        if bad:
            raise ValueError(f"Mechanism focus artifact contains forbidden fields: {sorted(bad)}")
        for value in payload.values():
            assert_no_forbidden_focus_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_forbidden_focus_keys(item)
