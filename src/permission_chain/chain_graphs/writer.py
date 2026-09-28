from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .diagnostics import PermissionChainGraphDiagnostics
from .schema import PermissionChainGraphs, assert_no_forbidden_formal_keys


def write_chain_graph_outputs(
    output_dir: str | Path,
    chain_graphs: PermissionChainGraphs,
    diagnostics: PermissionChainGraphDiagnostics,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    formal = chain_graphs.to_json_dict()
    assert_no_forbidden_formal_keys(formal)
    _write_json(out / "permission_chain_graphs.json", formal)
    _write_json(out / "permission_chain_graph_diagnostics.json", diagnostics.to_json_dict())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
