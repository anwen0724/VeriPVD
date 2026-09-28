from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FORBIDDEN_GROUP_KEYS = {
    "classification",
    "confidence",
    "reason",
    "prompt",
    "finding",
    "has_finding",
    "vulnerability_category",
}


@dataclass(frozen=True)
class StructuralEvidence:
    kind: str
    node_ids: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)
    statement_ids: list[str] = field(default_factory=list)
    member_target_ids: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "node_ids": sorted(set(self.node_ids)),
            "edge_ids": sorted(set(self.edge_ids)),
            "statement_ids": sorted(set(self.statement_ids)),
        }
        if self.member_target_ids:
            result["member_target_ids"] = sorted(set(self.member_target_ids))
        return result


@dataclass(frozen=True)
class PermissionTargetGroup:
    target_group_id: str
    representative_target_id: str
    members: list[dict[str, Any]]
    equivalence_evidence: list[StructuralEvidence] = field(default_factory=list)
    related_evidence: list[StructuralEvidence] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "target_group_id": self.target_group_id,
            "representative_target_id": self.representative_target_id,
            "members": list(self.members),
            "equivalence_evidence": [item.to_json_dict() for item in self.equivalence_evidence],
            "related_evidence": [item.to_json_dict() for item in self.related_evidence],
        }


@dataclass(frozen=True)
class PermissionTargetGroups:
    graph_id: str
    groups: list[PermissionTargetGroup]
    schema_version: str = "0.2"
    generation_mode: str = "algorithm"

    def to_json_dict(self) -> dict[str, Any]:
        result = {
            "graph_id": self.graph_id,
            "schema_version": self.schema_version,
            "generation_mode": self.generation_mode,
            "groups": [group.to_json_dict() for group in self.groups],
        }
        assert_no_forbidden_group_keys(result)
        return result


def assert_no_forbidden_group_keys(payload: Any) -> None:
    if isinstance(payload, dict):
        bad = FORBIDDEN_GROUP_KEYS.intersection(payload)
        if bad:
            raise ValueError(f"Target group artifact contains forbidden fields: {sorted(bad)}")
        for value in payload.values():
            assert_no_forbidden_group_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_forbidden_group_keys(item)
