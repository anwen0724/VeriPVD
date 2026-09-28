from __future__ import annotations

from typing import Any

from .candidates.graph_index import RtlGraphIndex


class TargetGroupGraphIndex(RtlGraphIndex):
    def signal_ids_read_by(self, statement_id: str) -> list[str]:
        return sorted(node["id"] for node in self.statement_reads(statement_id) if node.get("type") == "Signal")

    def signal_ids_written_by(self, statement_id: str) -> list[str]:
        return sorted(node["id"] for node in self.statement_writes(statement_id) if node.get("type") == "Signal")

    def statement_edge_ids(self, statement_id: str) -> list[str]:
        return sorted(
            str(edge["id"])
            for edge in self.outgoing_edges(statement_id)
            if edge.get("type") in {"reads", "writes"} and edge.get("id")
        )

    def connect_edges(self) -> list[dict[str, Any]]:
        return sorted(
            (edge for edge in self.edges if edge.get("type") == "connects"),
            key=lambda edge: str(edge.get("id", "")),
        )

    def adjacent_relation_edges(self, node_id: str) -> list[dict[str, Any]]:
        edges = self.incoming_edges(node_id) + self.outgoing_edges(node_id)
        unique = {str(edge.get("id")): edge for edge in edges if edge.get("type") in {"reads", "writes", "connects"}}
        return [unique[key] for key in sorted(unique)]

    def formal_node_summary(self, node_id: str) -> dict[str, Any] | None:
        node = self.maybe_node(node_id)
        if node is None:
            return None
        return {
            "node_id": node_id,
            "kind": str(node.get("type", "")),
            "name": str(node.get("name", "")),
            "module": self._module_name_from_scope(node.get("scope")),
            "loc": dict(node.get("loc") or {}),
        }

    def formal_edge_summary(self, edge: dict[str, Any]) -> dict[str, Any]:
        return {
            "edge_id": str(edge.get("id", "")),
            "kind": str(edge.get("type", "")),
            "src": str(edge.get("from", "")),
            "dst": str(edge.get("to", "")),
            "attrs": dict(edge.get("attrs") or {}),
        }
