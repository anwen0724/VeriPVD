from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .graph_index import TargetGroupGraphIndex
from .schema import StructuralEvidence


_BARE_SIGNAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class _UnionFind:
    def __init__(self, items: list[str]):
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            self.parent[right_root] = left_root
        else:
            self.parent[left_root] = right_root


@dataclass(frozen=True)
class EquivalenceResult:
    signal_root: dict[str, str]
    candidate_roots: dict[str, list[dict[str, Any]]]
    evidence_by_root: dict[str, list[StructuralEvidence]]
    direct_evidence_keys: set[tuple[str, str]]


def build_equivalence(
    index: TargetGroupGraphIndex,
    candidates: list[dict[str, Any]],
) -> EquivalenceResult:
    signal_ids = sorted(node["id"] for node in index.signal_nodes())
    union_find = _UnionFind(signal_ids)
    raw_evidence: list[StructuralEvidence] = []
    direct_keys: set[tuple[str, str]] = set()
    binding_counts = _formal_binding_counts(index)

    for edge in index.connect_edges():
        if not is_direct_port_binding(edge) or not _is_unambiguous_port_binding(edge, binding_counts):
            continue
        src = str(edge.get("from", ""))
        dst = str(edge.get("to", ""))
        if src not in union_find.parent or dst not in union_find.parent:
            continue
        union_find.union(src, dst)
        direct_keys.add(tuple(sorted((src, dst))))
        raw_evidence.append(
            StructuralEvidence(kind="direct_port_binding", node_ids=[src, dst], edge_ids=[str(edge.get("id", ""))])
        )

    for statement in index.statement_nodes():
        if str(statement.get("attrs", {}).get("kind", "")) != "continuous_assign":
            continue
        reads = index.signal_ids_read_by(statement["id"])
        writes = index.signal_ids_written_by(statement["id"])
        if len(reads) != 1 or len(writes) != 1:
            continue
        src, dst = reads[0], writes[0]
        if not _is_direct_continuous_assign(index, statement, src, dst):
            continue
        union_find.union(src, dst)
        direct_keys.add(tuple(sorted((src, dst))))
        raw_evidence.append(
            StructuralEvidence(
                kind="direct_continuous_assign",
                node_ids=[src, dst],
                edge_ids=index.statement_edge_ids(statement["id"]),
                statement_ids=[statement["id"]],
            )
        )

    signal_root = {signal_id: union_find.find(signal_id) for signal_id in signal_ids}
    candidate_roots: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        node_id = str(candidate.get("point", {}).get("node_id", ""))
        root = signal_root.get(node_id, node_id)
        candidate_roots.setdefault(root, []).append(candidate)
    for members in candidate_roots.values():
        members.sort(key=lambda item: str(item.get("target_id", "")))

    evidence_by_root: dict[str, list[StructuralEvidence]] = {}
    candidate_root_ids = set(candidate_roots)
    for evidence in raw_evidence:
        roots = {signal_root[node_id] for node_id in evidence.node_ids if node_id in signal_root}
        if len(roots) != 1:
            continue
        root = next(iter(roots))
        if root in candidate_root_ids:
            evidence_by_root.setdefault(root, []).append(evidence)
    return EquivalenceResult(signal_root, candidate_roots, evidence_by_root, direct_keys)


def is_direct_port_binding(edge: dict[str, Any]) -> bool:
    attrs = edge.get("attrs") or {}
    actual_expr = str(attrs.get("actual_expr", "")).strip()
    actual_base = str(attrs.get("actual_base_signal", "")).strip()
    return bool(actual_expr and actual_expr == actual_base and _BARE_SIGNAL.fullmatch(actual_expr))


def _formal_binding_counts(index: TargetGroupGraphIndex) -> dict[str, int]:
    instances_by_formal: dict[str, set[str]] = {}
    for edge in index.connect_edges():
        formal_node = _formal_port_node(edge)
        via_instance = str((edge.get("attrs") or {}).get("via_instance", ""))
        if formal_node and via_instance:
            instances_by_formal.setdefault(formal_node, set()).add(via_instance)
    return {node_id: len(instances) for node_id, instances in instances_by_formal.items()}


def _is_unambiguous_port_binding(edge: dict[str, Any], binding_counts: dict[str, int]) -> bool:
    formal_node = _formal_port_node(edge)
    return bool(formal_node and binding_counts.get(formal_node, 0) == 1)


def _formal_port_node(edge: dict[str, Any]) -> str:
    direction = str((edge.get("attrs") or {}).get("direction", ""))
    if direction == "parent_to_child":
        return str(edge.get("to", ""))
    if direction == "child_to_parent":
        return str(edge.get("from", ""))
    return ""


def _is_direct_continuous_assign(
    index: TargetGroupGraphIndex,
    statement: dict[str, Any],
    src: str,
    dst: str,
) -> bool:
    attrs = statement.get("attrs") or {}
    lhs = str(attrs.get("lhs_raw", "")).strip()
    rhs = str(attrs.get("rhs_raw", "")).strip()
    src_node = index.maybe_node(src) or {}
    dst_node = index.maybe_node(dst) or {}
    return bool(
        _BARE_SIGNAL.fullmatch(lhs)
        and _BARE_SIGNAL.fullmatch(rhs)
        and rhs == str(src_node.get("name", ""))
        and lhs == str(dst_node.get("name", ""))
    )
