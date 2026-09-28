from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vulnerability_analysis.source_contexts.config import PermissionChainContextConfig
from vulnerability_analysis.source_contexts.pipeline import build_permission_chain_contexts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build source contexts from mechanism-focused permission chains for one repo.")
    parser.add_argument("--chain-graphs", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-snippets-per-chain", type=int, default=120)
    args = parser.parse_args(argv)
    summary = build_permission_chain_contexts(
        chain_graphs_path=args.chain_graphs,
        repo_root=args.repo_root,
        output_dir=args.out,
        config=PermissionChainContextConfig(max_snippets_per_chain=args.max_snippets_per_chain),
    )
    print(
        "[ok] {graph_id}: chains={chain_count} snippets={snippet_count} invalid_snippets={invalid_snippet_count}".format(
            **summary
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
