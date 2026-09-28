from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from permission_chain.mechanism_focuses import build_permission_mechanism_focuses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build mechanism analysis focuses for one RTL target-group artifact.")
    parser.add_argument("--graph", required=True)
    parser.add_argument("--groups", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    summary = build_permission_mechanism_focuses(args.graph, args.groups, args.out)
    print(
        "[mechanism-focuses] graph={graph_id} groups={target_group_count} focuses={focus_count} split={split_target_group_count}".format(
            **summary
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
