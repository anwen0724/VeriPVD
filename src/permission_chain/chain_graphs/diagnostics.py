from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .chain_search import ChainSearchDiagnostics


@dataclass
class PermissionChainGraphDiagnostics:
    graph_id: str
    target_count: int = 0
    chain_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    source_location_count: int = 0
    missing_seed_node_count: int = 0
    truncated_chain_count: int = 0
    incomplete_chain_count: int = 0
    invalid_source_location_count: int = 0
    warnings: list[str] = field(default_factory=list)
    per_chain: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_search(
        cls,
        graph_id: str,
        target_count: int,
        search_diagnostics: list[ChainSearchDiagnostics],
        invalid_source_location_count: int = 0,
        warnings: list[str] | None = None,
    ) -> "PermissionChainGraphDiagnostics":
        return cls(
            graph_id=graph_id,
            target_count=target_count,
            chain_count=len(search_diagnostics),
            node_count=sum(item.visited_node_count for item in search_diagnostics),
            edge_count=sum(item.visited_edge_count for item in search_diagnostics),
            source_location_count=sum(item.source_location_count for item in search_diagnostics),
            missing_seed_node_count=sum(len(item.missing_seed_nodes) for item in search_diagnostics),
            truncated_chain_count=sum(1 for item in search_diagnostics if item.truncated_nodes or item.truncated_edges),
            incomplete_chain_count=sum(1 for item in search_diagnostics if item.incomplete),
            invalid_source_location_count=invalid_source_location_count,
            warnings=list(warnings or []),
            per_chain=[asdict(item) for item in search_diagnostics],
        )

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)
