from __future__ import annotations

from typing import Any

from rtl_structure_graph.builder import build_rtl_structure_graph
from rtl_structure_graph.writer import write_build_outputs
from runtime import scope_paths


def run(config: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    repo, output = scope_paths(config, scope)
    options = config.get("rtl_structure_graph", {})
    graph_id = options.get("graph_id") or scope["scope_id"]
    result = build_rtl_structure_graph(repo, graph_id=str(graph_id))
    graph_path, diagnostics_path = write_build_outputs(
        result.graph, result.diagnostics, output / "rtl_structure_graph"
    )
    return {
        "scope_id": scope["scope_id"],
        "graph_path": str(graph_path),
        "diagnostics_path": str(diagnostics_path),
        "stats": result.diagnostics.stats,
    }
