from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .graph_index import MechanismFocusGraphIndex, StatementObjectAccess


CONTROL_ROLES = {"condition", "case_selector"}


class _UnionFind:
    def __init__(self, items: set[str]):
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        if left not in self.parent or right not in self.parent:
            return
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        keep, merge = sorted((left_root, right_root))
        self.parent[merge] = keep


@dataclass(frozen=True)
class FocusPartition:
    member_target_ids: tuple[str, ...]
    statement_ids: tuple[str, ...]
    equivalence_node_ids: tuple[str, ...]
    shared_member_target_ids: tuple[str, ...]


def decompose_target_group(
    group: dict[str, Any],
    index: MechanismFocusGraphIndex,
) -> tuple[list[FocusPartition], dict[str, Any]]:
    members = list(group.get("members", []) or [])
    target_by_id = {str(member.get("target_id", "")): member for member in members}
    target_by_node = {
        str(member.get("point", {}).get("node_id", "")): str(member.get("target_id", ""))
        for member in members
    }
    member_nodes = {node_id for node_id in target_by_node if node_id}
    all_equivalence_nodes = set(member_nodes)
    for evidence in group.get("equivalence_evidence", []) or []:
        all_equivalence_nodes.update(str(node_id) for node_id in evidence.get("node_ids", []) or [] if node_id)
    union_find = _UnionFind(all_equivalence_nodes)
    for evidence in group.get("equivalence_evidence", []) or []:
        nodes = sorted(str(node_id) for node_id in evidence.get("node_ids", []) or [] if node_id)
        for left, right in zip(nodes, nodes[1:]):
            union_find.union(left, right)

    canonical_by_union: dict[str, str] = {}
    for node_id in sorted(member_nodes):
        root = union_find.find(node_id)
        canonical_by_union[root] = min(canonical_by_union.get(root, node_id), node_id)
    object_by_signal: dict[str, str] = {}
    aliases_by_object: dict[str, set[str]] = defaultdict(set)
    for node_id in sorted(all_equivalence_nodes):
        root = union_find.find(node_id)
        object_id = canonical_by_union.get(root)
        if object_id:
            object_by_signal[node_id] = object_id
            aliases_by_object[object_id].add(node_id)
    objects = sorted(set(object_by_signal[node_id] for node_id in member_nodes))
    targets_by_object: dict[str, list[str]] = defaultdict(list)
    for node_id, target_id in target_by_node.items():
        targets_by_object[object_by_signal[node_id]].append(target_id)

    statement_ids = _group_statement_ids(group, index)
    accesses = {
        statement_id: index.statement_object_access(statement_id, object_by_signal)
        for statement_id in statement_ids
    }
    accesses = {statement_id: access for statement_id, access in accesses.items() if access.touched_objects}
    adjacency = _object_adjacency(objects, accesses.values(), group, targets_by_object)
    bridges = _shared_control_bridges(objects, accesses.values())
    components = _components_without(objects, adjacency, bridges)
    supporting = _component_support(components, bridges, accesses.values())

    diagnostic: dict[str, Any] = {
        "target_group_id": str(group.get("target_group_id", "")),
        "decision": "kept_whole",
        "equivalence_object_count": len(objects),
        "candidate_bridge_object_ids": sorted(bridges),
        "component_object_ids": [sorted(component) for component in components],
        "supporting_statement_ids": sorted(set().union(*supporting.values())) if supporting else [],
        "split_basis": "none",
        "fallback_reason": "",
    }
    if len(components) < 2 or not bridges:
        guard_partitions, guard_details = _guard_scope_partitions(
            objects,
            accesses,
            target_by_id,
            targets_by_object,
            aliases_by_object,
            adjacency,
        )
        if guard_partitions:
            diagnostic.update(guard_details)
            diagnostic["decision"] = "split"
            diagnostic["split_basis"] = "guard_scope_and_distinct_writes"
            diagnostic["fallback_reason"] = ""
            return guard_partitions, diagnostic
        diagnostic["fallback_reason"] = "no_verified_independent_components"
        return [_whole_group_partition(target_by_id, accesses, aliases_by_object)], diagnostic
    if any(not supporting.get(index_value) for index_value in range(len(components))):
        diagnostic["decision"] = "fallback"
        diagnostic["fallback_reason"] = "component_without_shared_control_branch_evidence"
        return [_whole_group_partition(target_by_id, accesses, aliases_by_object)], diagnostic

    partitions: list[FocusPartition] = []
    shared_target_ids = sorted(target_id for bridge in bridges for target_id in targets_by_object.get(bridge, []))
    shared_aliases = set().union(*(aliases_by_object.get(bridge, set()) for bridge in bridges))
    for component in sorted(components, key=lambda item: tuple(sorted(item))):
        included_objects = set(component) | bridges
        target_ids = sorted(target_id for object_id in included_objects for target_id in targets_by_object[object_id])
        focus_statements = set()
        for statement_id, access in accesses.items():
            if access.touched_objects & component:
                focus_statements.add(statement_id)
            elif access.writes & bridges:
                focus_statements.add(statement_id)
        equivalence_nodes = set(shared_aliases)
        for object_id in component:
            equivalence_nodes.update(aliases_by_object.get(object_id, set()))
        partitions.append(
            FocusPartition(
                member_target_ids=tuple(target_ids),
                statement_ids=tuple(sorted(focus_statements)),
                equivalence_node_ids=tuple(sorted(equivalence_nodes)),
                shared_member_target_ids=tuple(shared_target_ids),
            )
        )

    covered = set().union(*(set(partition.member_target_ids) for partition in partitions))
    if covered != set(target_by_id):
        diagnostic["decision"] = "fallback"
        diagnostic["fallback_reason"] = "member_conservation_failed"
        return [_whole_group_partition(target_by_id, accesses, aliases_by_object)], diagnostic
    diagnostic["decision"] = "split"
    diagnostic["split_basis"] = "target_object_components"
    diagnostic["fallback_reason"] = ""
    return partitions, diagnostic


def _guard_scope_partitions(
    objects: list[str],
    accesses: dict[str, StatementObjectAccess],
    target_by_id: dict[str, dict[str, Any]],
    targets_by_object: dict[str, list[str]],
    aliases_by_object: dict[str, set[str]],
    adjacency: dict[str, set[str]],
) -> tuple[list[FocusPartition] | None, dict[str, Any]]:
    best: tuple[str, list[set[str]], dict[str, set[str]]] | None = None
    for object_id in objects:
        statements_by_signature: dict[str, set[str]] = defaultdict(set)
        writes_by_signature: dict[str, set[str]] = defaultdict(set)
        objects_by_signature: dict[str, set[str]] = defaultdict(set)
        for statement_id, access in accesses.items():
            if not (access.read_roles.get(object_id, set()) & CONTROL_ROLES) or not access.raw_writes:
                continue
            signature = "|".join(access.guard_signature) if access.guard_signature else statement_id
            statements_by_signature[signature].add(statement_id)
            writes_by_signature[signature].update(access.raw_writes)
            objects_by_signature[signature].update(access.touched_objects - {object_id})
        branches = _merge_guard_signatures(
            writes_by_signature,
            objects_by_signature,
            adjacency,
            object_id,
        )
        if len(branches) < 2:
            continue
        if best is None or len(branches) > len(best[1]) or (len(branches) == len(best[1]) and object_id < best[0]):
            best = (object_id, branches, statements_by_signature)
    if best is None:
        return None, {}

    bridge, signature_branches, statements_by_signature = best
    bridge_targets = sorted(targets_by_object[bridge])
    bridge_aliases = set(aliases_by_object.get(bridge, set()))
    partitions: list[FocusPartition] = []
    covered_targets: set[str] = set(bridge_targets)
    supporting_statements: set[str] = set()
    component_labels: list[list[str]] = []
    for signatures in sorted(signature_branches, key=lambda item: tuple(sorted(item))):
        branch_statement_ids = set().union(*(statements_by_signature[signature] for signature in signatures))
        supporting_statements.update(branch_statement_ids)
        branch_objects = {bridge}
        for statement_id in branch_statement_ids:
            branch_objects.update(accesses[statement_id].touched_objects)
        private_objects = branch_objects - {bridge}
        target_ids = sorted(
            set(bridge_targets)
            | {target_id for object_id in private_objects for target_id in targets_by_object.get(object_id, [])}
        )
        for statement_id, access in accesses.items():
            if access.writes & private_objects or access.writes & {bridge}:
                branch_statement_ids.add(statement_id)
        equivalence_nodes = set(bridge_aliases)
        for object_id in private_objects:
            equivalence_nodes.update(aliases_by_object.get(object_id, set()))
        partitions.append(
            FocusPartition(
                member_target_ids=tuple(target_ids),
                statement_ids=tuple(sorted(branch_statement_ids)),
                equivalence_node_ids=tuple(sorted(equivalence_nodes)),
                shared_member_target_ids=tuple(bridge_targets),
            )
        )
        covered_targets.update(target_ids)
        component_labels.append(sorted(signatures))

    uncovered = set(target_by_id) - covered_targets
    if uncovered:
        uncovered_objects = {
            object_id
            for object_id, target_ids in targets_by_object.items()
            if set(target_ids) & uncovered
        }
        residual_statements = {
            statement_id
            for statement_id, access in accesses.items()
            if access.touched_objects & uncovered_objects or access.writes & {bridge}
        }
        residual_nodes = set(bridge_aliases)
        for object_id in uncovered_objects:
            residual_nodes.update(aliases_by_object.get(object_id, set()))
        partitions.append(
            FocusPartition(
                member_target_ids=tuple(sorted(uncovered | set(bridge_targets))),
                statement_ids=tuple(sorted(residual_statements)),
                equivalence_node_ids=tuple(sorted(residual_nodes)),
                shared_member_target_ids=tuple(bridge_targets),
            )
        )
        component_labels.append(["residual"])

    if len(partitions) < 2:
        return None, {}
    return partitions, {
        "candidate_bridge_object_ids": [bridge],
        "component_object_ids": component_labels,
        "supporting_statement_ids": sorted(supporting_statements),
    }


def _merge_guard_signatures(
    writes_by_signature: dict[str, set[str]],
    objects_by_signature: dict[str, set[str]],
    adjacency: dict[str, set[str]],
    bridge: str,
) -> list[set[str]]:
    remaining = set(writes_by_signature)
    result: list[set[str]] = []
    while remaining:
        start = min(remaining)
        component = {start}
        changed = True
        while changed:
            changed = False
            writes = set().union(*(writes_by_signature[signature] for signature in component))
            component_objects = set().union(*(objects_by_signature[signature] for signature in component))
            joined = set()
            for signature in remaining - component:
                linked_objects = any(
                    right in adjacency.get(left, set()) - {bridge}
                    for left in component_objects
                    for right in objects_by_signature[signature]
                )
                if writes & writes_by_signature[signature] or linked_objects:
                    joined.add(signature)
            if joined:
                component.update(joined)
                changed = True
        remaining -= component
        result.append(component)
    return sorted(result, key=lambda item: tuple(sorted(item)))


def _group_statement_ids(group: dict[str, Any], index: MechanismFocusGraphIndex) -> list[str]:
    result: set[str] = set()
    for member in group.get("members", []) or []:
        for access in member.get("accesses", []) or []:
            node_id = str(access.get("node_id", ""))
            if index.is_statement(node_id):
                result.add(node_id)
    for key in ("equivalence_evidence", "related_evidence"):
        for evidence in group.get(key, []) or []:
            result.update(str(item) for item in evidence.get("statement_ids", []) or [] if index.is_statement(str(item)))
    return sorted(result)


def _object_adjacency(
    objects: list[str],
    accesses: Any,
    group: dict[str, Any],
    targets_by_object: dict[str, list[str]],
) -> dict[str, set[str]]:
    adjacency = {object_id: set() for object_id in objects}
    for access in accesses:
        for left, right in combinations(sorted(access.touched_objects), 2):
            adjacency[left].add(right)
            adjacency[right].add(left)
    object_by_target = {
        target_id: object_id for object_id, target_ids in targets_by_object.items() for target_id in target_ids
    }
    for evidence in group.get("related_evidence", []) or []:
        if evidence.get("kind") != "transformed_connect":
            continue
        related = sorted(
            {object_by_target[target_id] for target_id in evidence.get("member_target_ids", []) or [] if target_id in object_by_target}
        )
        for left, right in combinations(related, 2):
            adjacency[left].add(right)
            adjacency[right].add(left)
    return adjacency


def _shared_control_bridges(objects: list[str], accesses: Any) -> set[str]:
    signatures_by_object: dict[str, list[frozenset[str]]] = defaultdict(list)
    for access in accesses:
        for object_id, roles in access.read_roles.items():
            if not roles & CONTROL_ROLES:
                continue
            effects = (access.writes | access.touched_objects) - {object_id}
            if effects:
                signatures_by_object[object_id].append(frozenset(effects))
    bridges = set()
    for object_id in objects:
        signatures = signatures_by_object.get(object_id, [])
        if any(left.isdisjoint(right) for left, right in combinations(signatures, 2)):
            bridges.add(object_id)
    return bridges


def _components_without(
    objects: list[str],
    adjacency: dict[str, set[str]],
    removed: set[str],
) -> list[set[str]]:
    remaining = set(objects) - removed
    result: list[set[str]] = []
    while remaining:
        start = min(remaining)
        component: set[str] = set()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current in component or current in removed:
                continue
            component.add(current)
            queue.extend(sorted(adjacency.get(current, set()) - removed - component))
        remaining -= component
        result.append(component)
    return sorted(result, key=lambda item: tuple(sorted(item)))


def _component_support(
    components: list[set[str]],
    bridges: set[str],
    accesses: Any,
) -> dict[int, set[str]]:
    result: dict[int, set[str]] = defaultdict(set)
    for access in accesses:
        controlling_bridges = {
            object_id
            for object_id, roles in access.read_roles.items()
            if object_id in bridges and roles & CONTROL_ROLES
        }
        if not controlling_bridges:
            continue
        for index, component in enumerate(components):
            if access.touched_objects & component:
                result[index].add(access.statement_id)
    return result


def _whole_group_partition(
    target_by_id: dict[str, dict[str, Any]],
    accesses: dict[str, StatementObjectAccess],
    aliases_by_object: dict[str, set[str]],
) -> FocusPartition:
    return FocusPartition(
        member_target_ids=tuple(sorted(target_by_id)),
        statement_ids=tuple(sorted(accesses)),
        equivalence_node_ids=tuple(sorted(set().union(*aliases_by_object.values()) if aliases_by_object else set())),
        shared_member_target_ids=(),
    )
