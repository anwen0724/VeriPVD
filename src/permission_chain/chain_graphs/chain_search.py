from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .config import PermissionChainGraphConfig
from .graph_index import ChainGraphIndex
from .schema import ChainSourceLocation, PermissionChain
from .target_loader import (
    focus_member_node_ids,
    is_mechanism_focus,
    seed_node_ids,
    seed_record_id,
    shared_focus_node_ids,
    target_refs,
)


@dataclass
class ChainSearchDiagnostics:
    chain_id: str
    seed_target_id: str
    seed_node_count: int
    visited_node_count: int
    visited_edge_count: int
    source_location_count: int
    truncated_nodes: bool = False
    truncated_edges: bool = False
    missing_seed_nodes: list[str] = field(default_factory=list)
    construction_mode: str = "bounded_search"
    required_node_count: int = 0
    required_edge_count: int = 0
    missing_required_node_ids: list[str] = field(default_factory=list)
    missing_required_edge_ids: list[str] = field(default_factory=list)
    incomplete: bool = False


def build_chains(
    targets: list[dict[str, Any]],
    graph_index: ChainGraphIndex,
    config: PermissionChainGraphConfig,
) -> tuple[list[PermissionChain], list[ChainSearchDiagnostics]]:
    chains: list[PermissionChain] = []
    diagnostics: list[ChainSearchDiagnostics] = []
    for index, target in enumerate(targets[: config.max_chains_per_repo], start=1):
        chain_id = f"CHAIN-{index:04d}"
        chain, diag = build_chain_for_target(chain_id, target, graph_index, config)
        chains.append(chain)
        diagnostics.append(diag)
    return chains, diagnostics


def build_chain_for_target(
    chain_id: str,
    target: dict[str, Any],
    graph_index: ChainGraphIndex,
    config: PermissionChainGraphConfig,
) -> tuple[PermissionChain, ChainSearchDiagnostics]:
    seeds = seed_node_ids(target, include_access_nodes=config.include_target_access_nodes)
    seed_set = set(seeds)
    missing = [node_id for node_id in seeds if graph_index.maybe_node(node_id) is None]
    focus_mode = is_mechanism_focus(target)
    if focus_mode:
        visited_nodes, visited_edges = _focus_required_closure(target, graph_index)
    else:
        visited_nodes, visited_edges = _bounded_search(seeds, graph_index, config)
    formal_nodes = [node for node_id in sorted(visited_nodes) if (node := graph_index.formal_node(node_id)) is not None]
    formal_edges = [edge for edge_id in sorted(visited_edges) if (edge := graph_index.formal_edge(edge_id)) is not None]
    required_node_ids = {node.node_id for node in formal_nodes}
    required_edge_ids = {edge.edge_id for edge in formal_edges}
    node_budget = config.max_required_nodes_per_chain if focus_mode else config.max_nodes_per_chain
    edge_budget = config.max_required_edges_per_chain if focus_mode else config.max_edges_per_chain
    truncated_nodes = len(formal_nodes) > node_budget
    truncated_edges = len(formal_edges) > edge_budget



    valid_seed_count = sum(node.node_id in seed_set for node in formal_nodes)
    node_limit = max(node_budget, valid_seed_count)
    formal_nodes = _rank_nodes(formal_nodes, seed_set)[:node_limit]
    kept_node_ids = {node.node_id for node in formal_nodes}
    formal_edges = [
        edge
        for edge in _rank_edges(formal_edges, seed_set)
        if edge.src in kept_node_ids and edge.dst in kept_node_ids
    ][:edge_budget]
    emitted_node_ids = {node.node_id for node in formal_nodes}
    emitted_edge_ids = {edge.edge_id for edge in formal_edges}
    missing_required_nodes = sorted(required_node_ids - emitted_node_ids)
    missing_required_edges = sorted(required_edge_ids - emitted_edge_ids)
    locations = _source_locations(formal_nodes, formal_edges, graph_index)
    chain = PermissionChain(
        chain_id=chain_id,
        seed_targets=target_refs(target),
        nodes=formal_nodes,
        edges=formal_edges,
        source_locations=locations,
    )
    diag = ChainSearchDiagnostics(
        chain_id=chain_id,
        seed_target_id=seed_record_id(target),
        seed_node_count=len(seeds),
        visited_node_count=len(formal_nodes),
        visited_edge_count=len(formal_edges),
        source_location_count=len(locations),
        truncated_nodes=truncated_nodes,
        truncated_edges=truncated_edges,
        missing_seed_nodes=missing,
        construction_mode="mechanism_closure" if focus_mode else "bounded_search",
        required_node_count=len(required_node_ids),
        required_edge_count=len(required_edge_ids),
        missing_required_node_ids=missing_required_nodes,
        missing_required_edge_ids=missing_required_edges,
        incomplete=bool(missing or missing_required_nodes or missing_required_edges),
    )
    return chain, diag


def _focus_required_closure(
    focus: dict[str, Any],
    graph_index: ChainGraphIndex,
) -> tuple[set[str], set[str]]:
    nodes: set[str] = set()
    edges: set[str] = set()
    pending_statements: set[str] = {
        str(item) for item in focus.get("focus_statement_ids", []) or [] if graph_index.maybe_node(str(item))
    }
    member_signals = focus_member_node_ids(focus)
    shared_signals = shared_focus_node_ids(focus)
    private_signals = member_signals - shared_signals
    nodes.update(member_signals)
    nodes.update(
        str(item)
        for item in focus.get("equivalence_node_ids", []) or []
        if graph_index.maybe_node(str(item))
    )




    for signal_id in sorted(private_signals):
        pending_statements.update(_adjacent_statement_ids(signal_id, graph_index, include_reads=True))
    for signal_id in sorted(shared_signals):
        pending_statements.update(_adjacent_statement_ids(signal_id, graph_index, include_reads=False))

    backward_signals: deque[str] = deque()
    processed_statements: set[str] = set()
    processed_backward_signals: set[str] = set()
    while pending_statements or backward_signals:
        while pending_statements:
            statement_id = min(pending_statements)
            pending_statements.remove(statement_id)
            if statement_id in processed_statements:
                continue
            processed_statements.add(statement_id)
            nodes.add(statement_id)
            for edge in graph_index.adjacent_edges(statement_id):
                if edge.get("from") != statement_id or edge.get("type") not in {"reads", "writes"}:
                    continue
                edge_id = str(edge.get("id", ""))
                signal_id = str(edge.get("to", ""))
                if edge_id:
                    edges.add(edge_id)
                if graph_index.maybe_node(signal_id):
                    nodes.add(signal_id)
                if edge.get("type") == "reads":
                    backward_signals.append(signal_id)
        while backward_signals:
            signal_id = backward_signals.popleft()
            if signal_id in processed_backward_signals:
                continue
            processed_backward_signals.add(signal_id)
            for statement_id in _adjacent_statement_ids(signal_id, graph_index, include_reads=False):
                if statement_id not in processed_statements:
                    pending_statements.add(statement_id)

    _add_connect_closure(nodes, edges, graph_index)
    return nodes, edges


def _adjacent_statement_ids(
    signal_id: str,
    graph_index: ChainGraphIndex,
    *,
    include_reads: bool,
) -> set[str]:
    result = set()
    for edge in graph_index.adjacent_edges(signal_id):
        edge_type = edge.get("type")
        if edge.get("to") != signal_id or edge_type not in {"reads", "writes"}:
            continue
        if edge_type == "reads" and not include_reads:
            continue
        statement_id = str(edge.get("from", ""))
        node = graph_index.maybe_node(statement_id)
        if node and node.get("type") == "StmtSummary":
            result.add(statement_id)
    return result


def _add_connect_closure(
    nodes: set[str],
    edges: set[str],
    graph_index: ChainGraphIndex,
) -> None:
    queue = deque(
        node_id
        for node_id in sorted(nodes)
        if (graph_index.maybe_node(node_id) or {}).get("type") == "Signal"
    )
    processed: set[str] = set()
    while queue:
        signal_id = queue.popleft()
        if signal_id in processed:
            continue
        processed.add(signal_id)
        for edge in graph_index.adjacent_edges(signal_id):
            if edge.get("type") != "connects":
                continue
            edge_id = str(edge.get("id", ""))
            other_id = str(edge.get("from") if edge.get("to") == signal_id else edge.get("to"))
            if edge_id:
                edges.add(edge_id)
            if graph_index.maybe_node(other_id) and other_id not in nodes:
                nodes.add(other_id)
                queue.append(other_id)
            for instance_id in graph_index.edge_instance_node_ids(edge):
                nodes.add(instance_id)


def _bounded_search(
    seeds: list[str],
    graph_index: ChainGraphIndex,
    config: PermissionChainGraphConfig,
) -> tuple[set[str], set[str]]:
    visited_nodes: set[str] = set()
    visited_edges: set[str] = set()
    queue = deque((node_id, 0) for node_id in seeds if graph_index.maybe_node(node_id))
    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited_nodes:
            continue
        visited_nodes.add(node_id)
        if depth >= config.max_depth:
            continue
        adjacent = _rank_raw_edges(graph_index.adjacent_edges(node_id))[: config.max_frontier_per_depth]
        for edge in adjacent:
            edge_id = edge.get("id")
            src = edge.get("from")
            dst = edge.get("to")
            if edge_id:
                visited_edges.add(str(edge_id))
            for next_id in [src, dst, *graph_index.edge_instance_node_ids(edge)]:
                if next_id and next_id not in visited_nodes and graph_index.maybe_node(str(next_id)):
                    queue.append((str(next_id), depth + 1))
    return visited_nodes, visited_edges


def _rank_raw_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(edge: dict[str, Any]) -> tuple[int, str]:
        weight = {"connects": 0, "writes": 1, "reads": 2}.get(str(edge.get("type")), 3)
        return (weight, str(edge.get("id", "")))

    return sorted(edges, key=key)


def _rank_nodes(nodes, seed_node_ids: set[str] | None = None):
    seed_node_ids = seed_node_ids or set()

    def key(node):
        weight = {"Signal": 0, "StmtSummary": 1, "Instance": 2, "Module": 3}.get(node.kind, 4)
        return (0 if node.node_id in seed_node_ids else 1, weight, node.module, node.node_id)

    return sorted(nodes, key=key)


def _rank_edges(edges, seed_node_ids: set[str] | None = None):
    seed_node_ids = seed_node_ids or set()

    def key(edge):
        weight = {"connects": 0, "writes": 1, "reads": 2}.get(edge.kind, 3)
        touches_seed = edge.src in seed_node_ids or edge.dst in seed_node_ids
        return (0 if touches_seed else 1, weight, edge.edge_id)

    return sorted(edges, key=key)


def _source_locations(nodes, edges, graph_index: ChainGraphIndex) -> list[ChainSourceLocation]:
    by_key: dict[tuple[str, int, int], dict[str, set[str]]] = {}
    for node in nodes:
        if node.loc is not None:
            key = (node.loc.file, node.loc.line_start, node.loc.line_end)
            by_key.setdefault(key, {"nodes": set(), "edges": set()})["nodes"].add(node.node_id)
        for extra_loc in graph_index.additional_source_locs(node.node_id):
            key = (extra_loc.file, extra_loc.line_start, extra_loc.line_end)
            by_key.setdefault(key, {"nodes": set(), "edges": set()})["nodes"].add(node.node_id)
    for edge in edges:
        raw_edge = graph_index.maybe_edge(edge.edge_id)
        if not raw_edge:
            continue
        for node_id in graph_index.edge_instance_node_ids(raw_edge):
            loc = graph_index.source_loc(node_id)
            if loc is None:
                continue
            key = (loc.file, loc.line_start, loc.line_end)
            by_key.setdefault(key, {"nodes": set(), "edges": set()})["edges"].add(edge.edge_id)
    locations = []
    for index, (key, refs) in enumerate(sorted(by_key.items()), start=1):
        file, line_start, line_end = key
        locations.append(
            ChainSourceLocation(
                loc_id=f"LOC-{index:04d}",
                file=file,
                line_start=line_start,
                line_end=line_end,
                node_ids=sorted(refs["nodes"]),
                edge_ids=sorted(refs["edges"]),
            )
        )
    return locations
