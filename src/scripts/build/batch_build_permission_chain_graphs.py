from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from permission_chain.chain_graphs.config import PermissionChainGraphConfig
from permission_chain.chain_graphs.pipeline import build_permission_chain_graphs
from scripts.build.batch_build_permission_target_groups import resolve_repo_root


DEFAULT_GRAPHS_ROOT = PROJECT_ROOT / "runs" / "ours" / "module1" / "rtl_structure_graphs"
DEFAULT_FOCUS_ROOT = PROJECT_ROOT / "runs" / "validation" / "all_retained_v3" / "module2" / "mechanism_focuses"
DEFAULT_INPUT_ROOT = PROJECT_ROOT / "datasets" / "agent_inputs"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "runs" / "validation" / "all_retained_v3" / "module2" / "chain_graphs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch build graph-only permission chains from mechanism focuses.")
    parser.add_argument("--graphs-root", default=str(DEFAULT_GRAPHS_ROOT))
    parser.add_argument("--focus-root", default=str(DEFAULT_FOCUS_ROOT))
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--scope", action="append", default=None)
    parser.add_argument("--max-required-nodes", type=int, default=600)
    parser.add_argument("--max-required-edges", type=int, default=1800)
    args = parser.parse_args(argv)
    selected = set(args.scope or [])
    focus_root = Path(args.focus_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    runs = []
    for focus_path in sorted(focus_root.rglob("permission_mechanism_focuses.json")):
        scope = focus_path.parent.name
        if selected and scope not in selected:
            continue
        relative_parent = focus_path.parent.relative_to(focus_root)
        graph_path = Path(args.graphs_root) / scope / "rtl_structure_graph.json"
        try:
            summary = build_permission_chain_graphs(
                graph_path,
                focus_path,
                resolve_repo_root(scope, Path(args.input_root)),
                out_root / relative_parent,
                PermissionChainGraphConfig(
                    max_chains_per_repo=1000,
                    max_required_nodes_per_chain=args.max_required_nodes,
                    max_required_edges_per_chain=args.max_required_edges,
                ),
            )
            runs.append({"scope": scope, "status": "ok", **summary})
            print(f"[ok] {scope}: focuses={summary['target_count']} chains={summary['chain_count']}", flush=True)
        except Exception as exc:
            runs.append({"scope": scope, "status": "failed", "error": str(exc)})
            print(f"[failed] {scope}: {exc}", flush=True)
    (out_root / "manifest.json").write_text(json.dumps({"runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if runs and all(item["status"] == "ok" for item in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
