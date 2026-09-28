from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from permission_chain.target_groups import PermissionTargetGroupConfig, build_permission_target_groups


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic permission target groups for one RTL repo graph.")
    parser.add_argument("--graph", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-objects-per-group", type=int, default=6)
    args = parser.parse_args(argv)
    summary = build_permission_target_groups(
        graph_path=args.graph,
        repo_root=args.repo_root,
        output_dir=args.out,
        config=PermissionTargetGroupConfig(max_equivalence_objects_per_group=args.max_objects_per_group),
    )
    print(
        "[target-groups] graph={graph_id} raw={raw_candidate_count} equivalents={equivalence_object_count} "
        "groups={target_group_count} related_groups={related_group_count}".format(**summary),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
