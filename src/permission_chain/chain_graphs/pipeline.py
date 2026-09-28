from __future__ import annotations

from pathlib import Path
from typing import Any

from .chain_search import build_chains
from .config import PermissionChainGraphConfig
from .diagnostics import PermissionChainGraphDiagnostics
from .graph_index import ChainGraphIndex
from .schema import PermissionChainGraphs
from .target_loader import load_targets
from .writer import write_chain_graph_outputs


def build_permission_chain_graphs(
    graph_path: str | Path,
    targets_path: str | Path,
    repo_root: str | Path,
    output_dir: str | Path,
    config: PermissionChainGraphConfig | None = None,
) -> dict[str, Any]:
    cfg = config or PermissionChainGraphConfig()
    graph_index = ChainGraphIndex.from_path(graph_path)
    targets_graph_id, targets = load_targets(targets_path)
    warnings: list[str] = []
    if targets_graph_id and targets_graph_id != graph_index.graph_id:
        warnings.append(f"Target graph_id {targets_graph_id} differs from graph_id {graph_index.graph_id}")
    chains, search_diagnostics = build_chains(targets, graph_index, cfg)
    invalid_locations = count_invalid_source_locations(chains, repo_root)
    chain_graphs = PermissionChainGraphs(graph_id=graph_index.graph_id, chains=chains, schema_version=cfg.schema_version)
    diagnostics = PermissionChainGraphDiagnostics.from_search(
        graph_id=graph_index.graph_id,
        target_count=len(targets),
        search_diagnostics=search_diagnostics,
        invalid_source_location_count=invalid_locations,
        warnings=warnings,
    )
    write_chain_graph_outputs(output_dir, chain_graphs, diagnostics)
    return {
        "graph_id": graph_index.graph_id,
        "target_count": len(targets),
        "chain_count": len(chains),
        "node_count": sum(len(chain.nodes) for chain in chains),
        "edge_count": sum(len(chain.edges) for chain in chains),
        "source_location_count": sum(len(chain.source_locations) for chain in chains),
        "invalid_source_location_count": invalid_locations,
        "output_dir": str(output_dir),
    }


def count_invalid_source_locations(chains, repo_root: str | Path) -> int:
    root = Path(repo_root)
    count = 0
    cache: dict[Path, int | None] = {}
    for chain in chains:
        for loc in chain.source_locations:
            path = root / loc.file
            if path not in cache:
                if path.exists():
                    cache[path] = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
                else:
                    cache[path] = None
            line_count = cache[path]
            if line_count is None or loc.line_start < 1 or loc.line_end < loc.line_start or loc.line_end > line_count:
                count += 1
    return count
