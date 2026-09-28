from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rtl_structure_graph.builder import build_rtl_structure_graph
from rtl_structure_graph.writer import write_build_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build module-1 RTL structure graph.")
    parser.add_argument("--repo", required=True, help="Input RTL repo path.")
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument("--graph-id", default=None, help="Optional graph id.")
    args = parser.parse_args(argv)

    result = build_rtl_structure_graph(Path(args.repo), graph_id=args.graph_id)
    graph_path, diagnostics_path = write_build_outputs(result.graph, result.diagnostics, Path(args.out))
    print(f"graph: {graph_path}")
    print(f"diagnostics: {diagnostics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
