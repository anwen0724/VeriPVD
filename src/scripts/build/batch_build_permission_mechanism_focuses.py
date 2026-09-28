from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from permission_chain.mechanism_focuses import build_permission_mechanism_focuses


DEFAULT_GRAPHS_ROOT = PROJECT_ROOT / "runs" / "ours" / "module1" / "rtl_structure_graphs"
DEFAULT_GROUPS_ROOT = PROJECT_ROOT / "runs" / "ours" / "module2" / "target_groups"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "runs" / "validation" / "all_retained_v3" / "module2" / "mechanism_focuses"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch build mechanism focuses from retained or all target groups.")
    parser.add_argument("--graphs-root", default=str(DEFAULT_GRAPHS_ROOT))
    parser.add_argument("--groups-root", default=str(DEFAULT_GROUPS_ROOT))
    parser.add_argument("--groups-filename", default="permission_target_groups.json")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--scope", action="append", default=None)
    args = parser.parse_args(argv)
    selected = set(args.scope or [])
    groups_root = Path(args.groups_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    runs = []
    for groups_path in sorted(groups_root.rglob(args.groups_filename)):
        scope = groups_path.parent.name
        if selected and scope not in selected:
            continue
        graph_path = Path(args.graphs_root) / scope / "rtl_structure_graph.json"
        relative_parent = groups_path.parent.relative_to(groups_root)
        try:
            summary = build_permission_mechanism_focuses(graph_path, groups_path, out_root / relative_parent)
            runs.append({"scope": scope, "status": "ok", **summary})
            print(
                f"[ok] {scope}: groups={summary['target_group_count']} focuses={summary['focus_count']} "
                f"split={summary['split_target_group_count']}",
                flush=True,
            )
        except Exception as exc:
            runs.append({"scope": scope, "status": "failed", "error": str(exc)})
            print(f"[failed] {scope}: {exc}", flush=True)
    (out_root / "manifest.json").write_text(json.dumps({"runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if runs and all(item["status"] == "ok" for item in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
