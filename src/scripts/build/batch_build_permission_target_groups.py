from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from permission_chain.target_groups import PermissionTargetGroupConfig, build_permission_target_groups


DEFAULT_GRAPHS_ROOT = PROJECT_ROOT / "runs" / "ours" / "module1" / "rtl_structure_graphs"
DEFAULT_INPUT_ROOT = PROJECT_ROOT / "datasets" / "agent_inputs"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "runs" / "ours" / "module2" / "target_groups"


def run_batch(
    graphs_root: str | Path = DEFAULT_GRAPHS_ROOT,
    input_root: str | Path = DEFAULT_INPUT_ROOT,
    out_root: str | Path = DEFAULT_OUT_ROOT,
    selected_scopes: list[str] | None = None,
    config: PermissionTargetGroupConfig | None = None,
) -> dict[str, Any]:
    graphs = Path(graphs_root)
    inputs = Path(input_root)
    output = Path(out_root)
    output.mkdir(parents=True, exist_ok=True)
    selected = set(selected_scopes or [])
    cfg = config or PermissionTargetGroupConfig()
    runs: list[dict[str, Any]] = []
    for graph_path in sorted(graphs.glob("*/rtl_structure_graph.json")):
        scope = graph_path.parent.name
        if selected and scope not in selected:
            continue
        repo_root = resolve_repo_root(scope, inputs)
        try:
            summary = build_permission_target_groups(graph_path, repo_root, output / scope, cfg)
            runs.append({"scope": scope, "status": "ok", "graph_path": str(graph_path), "repo_root": str(repo_root), **summary})
            print(
                f"[ok] {scope}: raw={summary['raw_candidate_count']} "
                f"equivalents={summary['equivalence_object_count']} groups={summary['target_group_count']}",
                flush=True,
            )
        except Exception as exc:
            runs.append({"scope": scope, "status": "failed", "graph_path": str(graph_path), "repo_root": str(repo_root), "error": str(exc)})
            print(f"[failed] {scope}: {exc}", flush=True)
    manifest = {
        "graphs_root": str(graphs),
        "input_root": str(inputs),
        "out_root": str(output),
        "total_scopes": len(runs),
        "successful_scopes": sum(1 for item in runs if item["status"] == "ok"),
        "failed_scopes": sum(1 for item in runs if item["status"] == "failed"),
        "runs": runs,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def resolve_repo_root(scope: str, input_root: Path) -> Path:
    if "__" not in scope:
        raise ValueError(f"Cannot resolve repo root for scope: {scope}")
    benchmark, scope_name = scope.split("__", 1)
    return input_root / benchmark / scope_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch build deterministic permission target groups.")
    parser.add_argument("--graphs-root", default=str(DEFAULT_GRAPHS_ROOT))
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--scope", action="append", default=None)
    parser.add_argument("--max-objects-per-group", type=int, default=6)
    args = parser.parse_args(argv)
    manifest = run_batch(
        graphs_root=args.graphs_root,
        input_root=args.input_root,
        out_root=args.out_root,
        selected_scopes=args.scope,
        config=PermissionTargetGroupConfig(max_equivalence_objects_per_group=args.max_objects_per_group),
    )
    return 1 if manifest["failed_scopes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
