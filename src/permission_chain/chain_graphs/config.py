from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionChainGraphConfig:
    schema_version: str = "0.1"
    max_chains_per_repo: int = 200
    max_nodes_per_chain: int = 80
    max_edges_per_chain: int = 120
    max_depth: int = 4
    max_frontier_per_depth: int = 96
    include_target_access_nodes: bool = True
    include_instance_nodes_from_connects: bool = True
    max_required_nodes_per_chain: int = 600
    max_required_edges_per_chain: int = 1800
