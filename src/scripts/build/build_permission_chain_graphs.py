from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from permission_chain.chain_graphs.config import PermissionChainGraphConfig
from permission_chain.chain_graphs.pipeline import build_permission_chain_graphs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build graph-only permission chain artifacts for one repo.")
    parser.add_argument("--graph", required=True)
    parser.add_argument("--focuses", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-chains-per-repo", type=int, default=1000)
    parser.add_argument("--max-required-nodes", type=int, default=600)
    parser.add_argument("--max-required-edges", type=int, default=1800)
    args = parser.parse_args(argv)

    summary = build_permission_chain_graphs(
        graph_path=args.graph,
        targets_path=args.focuses,
        repo_root=args.repo_root,
        output_dir=args.out,
        config=PermissionChainGraphConfig(
            max_chains_per_repo=args.max_chains_per_repo,
            max_required_nodes_per_chain=args.max_required_nodes,
            max_required_edges_per_chain=args.max_required_edges,
        ),
    )
    print(
        "[ok] {graph_id}: focuses={target_count} chains={chain_count} nodes={node_count} edges={edge_count} source_locations={source_location_count} invalid_locs={invalid_source_location_count}".format(
            **summary
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
