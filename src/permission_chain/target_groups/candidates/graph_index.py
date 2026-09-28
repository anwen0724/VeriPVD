from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


class RtlGraphIndex:
    def __init__(self, graph: dict[str, Any]):
        self.graph = graph
        self.graph_id = graph.get("graph_id", "")
        self.nodes = list(graph.get("nodes", []))
        self.edges = list(graph.get("edges", []))
        self.nodes_by_id = {node["id"]: node for node in self.nodes}
        self.edges_by_id = {edge["id"]: edge for edge in self.edges}
        self.signals_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.statements_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.modules_by_name: dict[str, dict[str, Any]] = {}
        self.incoming_edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.outgoing_edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for node in self.nodes:
            if node.get("type") == "Module":
                self.modules_by_name[node.get("name", "")] = node
            if node.get("type") == "Signal":
                self.signals_by_module[self.module_name_for_signal(node["id"])].append(node)
            if node.get("type") == "StmtSummary":
                self.statements_by_module[self._module_name_from_scope(node.get("scope"))].append(node)

        for edge in self.edges:
            self.outgoing_edges_by_node[edge.get("from")].append(edge)
            self.incoming_edges_by_node[edge.get("to")].append(edge)

    @classmethod
    def from_json_dict(cls, graph: dict[str, Any]) -> "RtlGraphIndex":
        return cls(graph)

    @classmethod
    def from_path(cls, path: str | Path) -> "RtlGraphIndex":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def node(self, node_id: str) -> dict[str, Any]:
        return self.nodes_by_id[node_id]

    def maybe_node(self, node_id: str) -> dict[str, Any] | None:
        return self.nodes_by_id.get(node_id)

    def signal_nodes(self) -> list[dict[str, Any]]:
        return [node for node in self.nodes if node.get("type") == "Signal"]

    def statement_nodes(self) -> list[dict[str, Any]]:
        return [node for node in self.nodes if node.get("type") == "StmtSummary"]

    def signal_written_by(self, signal_id: str) -> list[dict[str, Any]]:
        return [
            self.nodes_by_id[edge["from"]]
            for edge in self.incoming_edges_by_node.get(signal_id, [])
            if edge.get("type") == "writes" and edge.get("from") in self.nodes_by_id
        ]

    def signal_read_by(self, signal_id: str) -> list[dict[str, Any]]:
        return [
            self.nodes_by_id[edge["from"]]
            for edge in self.incoming_edges_by_node.get(signal_id, [])
            if edge.get("type") == "reads" and edge.get("from") in self.nodes_by_id
        ]

    def signal_connected_to(self, signal_id: str) -> list[dict[str, Any]]:
        connected: list[dict[str, Any]] = []
        for edge in self.incoming_edges_by_node.get(signal_id, []) + self.outgoing_edges_by_node.get(signal_id, []):
            if edge.get("type") != "connects":
                continue
            other_id = edge["from"] if edge.get("to") == signal_id else edge.get("to")
            other = self.nodes_by_id.get(other_id)
            if other:
                connected.append(other)
        return connected

    def incoming_edges(self, node_id: str, edge_type: str | None = None) -> list[dict[str, Any]]:
        edges = self.incoming_edges_by_node.get(node_id, [])
        if edge_type:
            return [edge for edge in edges if edge.get("type") == edge_type]
        return list(edges)

    def outgoing_edges(self, node_id: str, edge_type: str | None = None) -> list[dict[str, Any]]:
        edges = self.outgoing_edges_by_node.get(node_id, [])
        if edge_type:
            return [edge for edge in edges if edge.get("type") == edge_type]
        return list(edges)

    def statement_reads(self, statement_id: str) -> list[dict[str, Any]]:
        return [
            self.nodes_by_id[edge["to"]]
            for edge in self.outgoing_edges_by_node.get(statement_id, [])
            if edge.get("type") == "reads" and edge.get("to") in self.nodes_by_id
        ]

    def statement_writes(self, statement_id: str) -> list[dict[str, Any]]:
        return [
            self.nodes_by_id[edge["to"]]
            for edge in self.outgoing_edges_by_node.get(statement_id, [])
            if edge.get("type") == "writes" and edge.get("to") in self.nodes_by_id
        ]

    def edge_between(self, from_id: str, to_id: str, edge_type: str) -> dict[str, Any] | None:
        for edge in self.outgoing_edges_by_node.get(from_id, []):
            if edge.get("type") == edge_type and edge.get("to") == to_id:
                return edge
        return None

    def source_loc(self, node_id: str) -> dict[str, Any] | None:
        node = self.nodes_by_id.get(node_id)
        if not node:
            return None
        loc = node.get("loc")
        return dict(loc) if loc else None

    def module_name_for_signal(self, signal_id: str) -> str:
        node = self.nodes_by_id.get(signal_id)
        if node:
            return self._module_name_from_scope(node.get("scope"))
        raw = signal_id.removeprefix("signal:")
        return raw.rsplit(".", 1)[0] if "." in raw else ""

    def _module_name_from_scope(self, scope: str | None) -> str:
        if not scope:
            return ""
        return scope.removeprefix("module:")
