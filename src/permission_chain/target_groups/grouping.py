from __future__ import annotations

from collections import defaultdict

from .config import PermissionTargetGroupConfig
from .equivalence import EquivalenceResult
from .relations import RelatedRelation
from .schema import PermissionTargetGroup, StructuralEvidence


HIGH_PRIORITY_ROLES = {
    "lock_state",
    "write_protection",
    "privilege_state",
    "auth_state",
    "debug_interface",
    "protected_data",
    "secret_state",
    "reset_sensitive_state",
}


def build_target_groups(
    equivalence: EquivalenceResult,
    relations: list[RelatedRelation],
    config: PermissionTargetGroupConfig,
) -> list[PermissionTargetGroup]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for relation in relations:
        adjacency[relation.left_root].add(relation.right_root)
        adjacency[relation.right_root].add(relation.left_root)

    ordered_roots = sorted(equivalence.candidate_roots, key=lambda root: _root_priority(root, equivalence))
    assigned: set[str] = set()
    grouped_roots: list[list[str]] = []
    for root in ordered_roots:
        if root in assigned:
            continue
        available_neighbors = sorted(
            (neighbor for neighbor in adjacency.get(root, set()) if neighbor not in assigned),
            key=lambda item: _root_priority(item, equivalence),
        )
        roots = [root, *available_neighbors[: max(0, config.max_equivalence_objects_per_group - 1)]]
        assigned.update(roots)
        grouped_roots.append(roots)

    result: list[PermissionTargetGroup] = []
    for sequence, roots in enumerate(grouped_roots, start=1):
        members = [member for root in roots for member in equivalence.candidate_roots[root]]
        members.sort(key=_member_priority)
        member_ids_by_root = {
            root: [str(member.get("target_id", "")) for member in equivalence.candidate_roots[root]] for root in roots
        }
        equivalence_evidence = [item for root in roots for item in equivalence.evidence_by_root.get(root, [])]
        related_evidence = []
        root_set = set(roots)
        for relation in relations:
            if relation.left_root not in root_set or relation.right_root not in root_set:
                continue
            related_evidence.append(
                StructuralEvidence(
                    kind=relation.kind,
                    node_ids=list(relation.node_ids),
                    edge_ids=list(relation.edge_ids),
                    statement_ids=list(relation.statement_ids),
                    member_target_ids=[
                        *member_ids_by_root[relation.left_root],
                        *member_ids_by_root[relation.right_root],
                    ],
                )
            )
        result.append(
            PermissionTargetGroup(
                target_group_id=f"TG-{sequence:04d}",
                representative_target_id=str(members[0].get("target_id", "")),
                members=members,
                equivalence_evidence=_dedupe_evidence(equivalence_evidence),
                related_evidence=_dedupe_evidence(related_evidence),
            )
        )
    return result


def _root_priority(root: str, equivalence: EquivalenceResult) -> tuple[int, str]:
    return min((_member_priority(member) for member in equivalence.candidate_roots[root]), default=(99, root))


def _member_priority(member: dict) -> tuple[int, str]:
    roles = set(member.get("point", {}).get("point_roles", []))
    score = 0
    if roles & HIGH_PRIORITY_ROLES:
        score -= 4
    if "control_like" in roles:
        score -= 2
    if "register" in roles:
        score -= 1
    return score, str(member.get("target_id", ""))


def _dedupe_evidence(items: list[StructuralEvidence]) -> list[StructuralEvidence]:
    unique = {}
    for item in items:
        payload = item.to_json_dict()
        key = (
            payload["kind"],
            tuple(payload["node_ids"]),
            tuple(payload["edge_ids"]),
            tuple(payload["statement_ids"]),
            tuple(payload.get("member_target_ids", [])),
        )
        unique[key] = item
    return [unique[key] for key in sorted(unique)]
