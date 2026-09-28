from __future__ import annotations

import json
from pathlib import Path

from rtl_structure_graph.diagnostics import GraphDiagnostics
from rtl_structure_graph.models import RtlGraph


GRAPH_FILENAME = "rtl_structure_graph.json"
DIAGNOSTICS_FILENAME = "rtl_structure_graph_diagnostics.json"


def write_graph(graph: RtlGraph, output_dir: str | Path) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    graph_path = out_dir / GRAPH_FILENAME
    graph_path.write_text(
        json.dumps(graph.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return graph_path


def write_diagnostics(diagnostics: GraphDiagnostics, output_dir: str | Path) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_path = out_dir / DIAGNOSTICS_FILENAME
    diagnostics_path.write_text(
        json.dumps(diagnostics.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return diagnostics_path


def write_build_outputs(graph: RtlGraph, diagnostics: GraphDiagnostics, output_dir: str | Path) -> tuple[Path, Path]:
    return write_graph(graph, output_dir), write_diagnostics(diagnostics, output_dir)
