from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .schema import ChainEdge, ChainLoc, ChainNode


class ChainGraphIndex:
    def __init__(self, graph: dict[str, Any]):
        self.graph = graph
        self.graph_id = str(graph.get("graph_id", ""))
        self.nodes = list(graph.get("nodes", []))
        self.edges = list(graph.get("edges", []))
        self.nodes_by_id = {node["id"]: node for node in self.nodes if "id" in node}
        self.edges_by_id = {edge["id"]: edge for edge in self.edges if "id" in edge}
        self.incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in self.edges:
            src = edge.get("from")
            dst = edge.get("to")
            if src:
                self.outgoing[src].append(edge)
            if dst:
                self.incoming[dst].append(edge)

    @classmethod
    def from_path(cls, path: str | Path) -> "ChainGraphIndex":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def maybe_node(self, node_id: str) -> dict[str, Any] | None:
        return self.nodes_by_id.get(node_id)

    def maybe_edge(self, edge_id: str) -> dict[str, Any] | None:
        return self.edges_by_id.get(edge_id)

    def adjacent_edges(self, node_id: str) -> list[dict[str, Any]]:
        return self.incoming.get(node_id, []) + self.outgoing.get(node_id, [])

    def node_module(self, node: dict[str, Any]) -> str:
        scope = node.get("scope")
        if isinstance(scope, str) and scope.startswith("module:"):
            return scope.removeprefix("module:")
        node_id = str(node.get("id", ""))
        if node_id.startswith("signal:") and "." in node_id:
            return node_id.removeprefix("signal:").rsplit(".", 1)[0]
        if node_id.startswith("stmt:"):
            parts = node_id.split(":")
            return parts[1] if len(parts) > 1 else ""
        if node_id.startswith("instance:") and "." in node_id:
            return node_id.removeprefix("instance:").rsplit(".", 1)[0]
        if node.get("type") == "Module":
            return str(node.get("name", ""))
        return ""

    def source_loc(self, node_id: str) -> ChainLoc | None:
        node = self.maybe_node(node_id)
        if not node:
            return None
        return loc_from_dict(node.get("loc"))

    def additional_source_locs(self, node_id: str) -> list[ChainLoc]:
        node = self.maybe_node(node_id) or {}
        result = []
        for loc in (node.get("attrs") or {}).get("control_locs", []) or []:
            parsed = loc_from_dict(loc)
            if parsed is not None:
                result.append(parsed)
        return result

    def formal_node(self, node_id: str) -> ChainNode | None:
        node = self.maybe_node(node_id)
        if not node:
            return None
        return ChainNode(
            node_id=node_id,
            kind=str(node.get("type", "")),
            name=str(node.get("name", node_id)),
            module=self.node_module(node),
            loc=loc_from_dict(node.get("loc")),
        )

    def formal_edge(self, edge_id: str) -> ChainEdge | None:
        edge = self.maybe_edge(edge_id)
        if not edge:
            return None
        return ChainEdge(
            edge_id=edge_id,
            src=str(edge.get("from", "")),
            dst=str(edge.get("to", "")),
            kind=str(edge.get("type", "")),
        )

    def edge_instance_node_ids(self, edge: dict[str, Any]) -> list[str]:
        attrs = edge.get("attrs") or {}
        instance_id = attrs.get("via_instance")
        if instance_id and instance_id in self.nodes_by_id:
            return [instance_id]
        return []


def loc_from_dict(loc: Any) -> ChainLoc | None:
    if not isinstance(loc, dict):
        return None
    try:
        return ChainLoc(
            file=str(loc.get("file", "")),
            line_start=int(loc.get("line_start")),
            line_end=int(loc.get("line_end")),
        )
    except (TypeError, ValueError):
        return None
