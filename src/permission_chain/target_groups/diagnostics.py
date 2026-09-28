from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .equivalence import EquivalenceResult
from .relations import RelatedRelation
from .schema import PermissionTargetGroup


@dataclass
class TargetGroupDiagnostics:
    graph_id: str
    raw_candidate_count: int
    equivalence_object_count: int
    equivalence_merge_count: int
    target_group_count: int
    related_group_count: int
    singleton_group_count: int
    candidate_conservation_ok: bool
    duplicate_member_count: int
    missing_member_count: int
    relation_count: int
    relation_kind_distribution: dict[str, int] = field(default_factory=dict)
    group_size_distribution: dict[str, int] = field(default_factory=dict)
    per_group: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_group_diagnostics(
    graph_id: str,
    candidates: list[dict[str, Any]],
    equivalence: EquivalenceResult,
    relations: list[RelatedRelation],
    groups: list[PermissionTargetGroup],
) -> TargetGroupDiagnostics:
    original_ids = [str(item.get("target_id", "")) for item in candidates]
    grouped_ids = [str(item.get("target_id", "")) for group in groups for item in group.members]
    duplicate_count = len(grouped_ids) - len(set(grouped_ids))
    missing = sorted(set(original_ids) - set(grouped_ids))
    relation_distribution: dict[str, int] = {}
    for relation in relations:
        relation_distribution[relation.kind] = relation_distribution.get(relation.kind, 0) + 1
    size_distribution: dict[str, int] = {}
    for group in groups:
        key = str(len(group.members))
        size_distribution[key] = size_distribution.get(key, 0) + 1
    return TargetGroupDiagnostics(
        graph_id=graph_id,
        raw_candidate_count=len(candidates),
        equivalence_object_count=len(equivalence.candidate_roots),
        equivalence_merge_count=len(candidates) - len(equivalence.candidate_roots),
        target_group_count=len(groups),
        related_group_count=sum(1 for group in groups if group.related_evidence),
        singleton_group_count=sum(1 for group in groups if len(group.members) == 1),
        candidate_conservation_ok=not missing and duplicate_count == 0 and set(original_ids) == set(grouped_ids),
        duplicate_member_count=duplicate_count,
        missing_member_count=len(missing),
        relation_count=len(relations),
        relation_kind_distribution=dict(sorted(relation_distribution.items())),
        group_size_distribution=dict(sorted(size_distribution.items(), key=lambda item: int(item[0]))),
        per_group=[
            {
                "target_group_id": group.target_group_id,
                "member_count": len(group.members),
                "member_target_ids": [str(member.get("target_id", "")) for member in group.members],
                "equivalence_evidence": [item.to_json_dict() for item in group.equivalence_evidence],
                "related_evidence": [item.to_json_dict() for item in group.related_evidence],
            }
            for group in groups
        ],
        warnings=[f"Missing candidate ids: {missing[:10]}"] if missing else [],
    )
