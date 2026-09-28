from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceLoc:
    file: str
    line_start: int
    line_end: int

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


@dataclass(frozen=True)
class GraphNode:
    id: str
    type: str
    scope: str | None
    name: str
    loc: SourceLoc
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "scope": self.scope,
            "name": self.name,
            "loc": self.loc.to_json_dict(),
            "attrs": self.attrs,
        }


@dataclass(frozen=True)
class GraphEdge:
    id: str
    type: str
    from_id: str
    to_id: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "from": self.from_id,
            "to": self.to_id,
            "attrs": self.attrs,
        }


@dataclass
class RtlGraph:
    graph_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        if not any(existing.id == node.id for existing in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        if not any(existing.id == edge.id for existing in self.edges):
            self.edges.append(edge)

    def get_node(self, node_id: str) -> GraphNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def replace_node(self, node: GraphNode) -> None:
        self.nodes = [node if existing.id == node.id else existing for existing in self.nodes]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [node.to_json_dict() for node in self.nodes],
            "edges": [edge.to_json_dict() for edge in self.edges],
        }
