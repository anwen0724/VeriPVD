from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vulnerability_analysis.source_contexts.config import PermissionChainContextConfig
from vulnerability_analysis.source_contexts.pipeline import build_permission_chain_contexts
from scripts.build.batch_build_permission_target_groups import resolve_repo_root


DEFAULT_CHAIN_ROOT = PROJECT_ROOT / "runs" / "validation" / "all_retained_v3" / "module2" / "chain_graphs"
DEFAULT_INPUT_ROOT = PROJECT_ROOT / "datasets" / "agent_inputs"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "runs" / "validation" / "all_retained_v3" / "module3" / "chain_contexts"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch build source contexts from mechanism-focused permission chains.")
    parser.add_argument("--chain-root", default=str(DEFAULT_CHAIN_ROOT))
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--scope", action="append", default=None)
    parser.add_argument("--max-snippets-per-chain", type=int, default=120)
    args = parser.parse_args(argv)
    selected = set(args.scope or [])
    chain_root = Path(args.chain_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    runs = []
    for chain_path in sorted(chain_root.rglob("permission_chain_graphs.json")):
        scope = chain_path.parent.name
        if selected and scope not in selected:
            continue
        relative_parent = chain_path.parent.relative_to(chain_root)
        try:
            summary = build_permission_chain_contexts(
                chain_path,
                resolve_repo_root(scope, Path(args.input_root)),
                out_root / relative_parent,
                PermissionChainContextConfig(max_snippets_per_chain=args.max_snippets_per_chain),
            )
            runs.append({"scope": scope, "status": "ok", **summary})
            print(f"[ok] {scope}: chains={summary['chain_count']} snippets={summary['snippet_count']}", flush=True)
        except Exception as exc:
            runs.append({"scope": scope, "status": "failed", "error": str(exc)})
            print(f"[failed] {scope}: {exc}", flush=True)
    (out_root / "manifest.json").write_text(json.dumps({"runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if runs and all(item["status"] == "ok" for item in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
