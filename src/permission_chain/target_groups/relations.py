from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .equivalence import EquivalenceResult, is_direct_port_binding
from .graph_index import TargetGroupGraphIndex


@dataclass(frozen=True)
class RelatedRelation:
    left_root: str
    right_root: str
    kind: str
    node_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    statement_ids: tuple[str, ...] = ()


def build_related_relations(
    index: TargetGroupGraphIndex,
    equivalence: EquivalenceResult,
) -> list[RelatedRelation]:
    candidate_roots = set(equivalence.candidate_roots)
    relations: list[RelatedRelation] = []
    signatures: dict[str, set[str]] = {root: set() for root in candidate_roots}

    for statement in index.statement_nodes():
        statement_id = str(statement["id"])
        read_nodes = index.signal_ids_read_by(statement_id)
        write_nodes = index.signal_ids_written_by(statement_id)
        read_roots = {equivalence.signal_root[node] for node in read_nodes if equivalence.signal_root.get(node) in candidate_roots}
        write_roots = {equivalence.signal_root[node] for node in write_nodes if equivalence.signal_root.get(node) in candidate_roots}
        involved = sorted(read_roots | write_roots)
        for root in involved:
            signatures[root].add(statement_id)
        if len(involved) < 2:
            continue
        statement_edges = tuple(index.statement_edge_ids(statement_id))
        kind_hint = str(statement.get("attrs", {}).get("kind", ""))
        for left, right in combinations(involved, 2):
            if (left in read_roots and right in write_roots) or (right in read_roots and left in write_roots):
                kind = "read_write_dependency"
            elif kind_hint in {"condition", "case_branch"} and left in read_roots and right in read_roots:
                kind = "shared_control_use"
            else:
                kind = "shared_statement"
            relations.append(
                RelatedRelation(
                    left,
                    right,
                    kind,
                    node_ids=tuple(sorted(set(read_nodes + write_nodes))),
                    edge_ids=statement_edges,
                    statement_ids=(statement_id,),
                )
            )

    by_signature: dict[tuple[str, ...], list[str]] = {}
    for root, statement_ids in signatures.items():
        signature = tuple(sorted(statement_ids))
        if signature:
            by_signature.setdefault(signature, []).append(root)
    for signature, roots in sorted(by_signature.items()):
        for left, right in combinations(sorted(roots), 2):
            relations.append(
                RelatedRelation(left, right, "identical_access_signature", statement_ids=signature)
            )

    for edge in index.connect_edges():
        if is_direct_port_binding(edge):
            continue
        src = str(edge.get("from", ""))
        dst = str(edge.get("to", ""))
        left = equivalence.signal_root.get(src)
        right = equivalence.signal_root.get(dst)
        if left is None or right is None or left == right or left not in candidate_roots or right not in candidate_roots:
            continue
        left, right = sorted((left, right))
        relations.append(
            RelatedRelation(left, right, "transformed_connect", node_ids=(src, dst), edge_ids=(str(edge.get("id", "")),))
        )

    return _dedupe_relations(relations)


def _dedupe_relations(relations: list[RelatedRelation]) -> list[RelatedRelation]:
    unique: dict[tuple[Any, ...], RelatedRelation] = {}
    for relation in relations:
        key = (
            relation.left_root,
            relation.right_root,
            relation.kind,
            relation.node_ids,
            relation.edge_ids,
            relation.statement_ids,
        )
        unique[key] = relation
    return [unique[key] for key in sorted(unique)]
