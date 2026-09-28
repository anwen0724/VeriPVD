from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from runtime import load_config, select_scope
from runtime import permission_chain, rtl_structure_graph, vulnerability_analysis


RUNNERS = {
    "rtl_structure_graph": rtl_structure_graph.run,
    "permission_chain": permission_chain.run,
    "vulnerability_analysis": vulnerability_analysis.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one VeriPVD module for one RTL input.")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--module", required=True, choices=RUNNERS)
    parser.add_argument("--scope")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    scope = select_scope(config, args.scope)
    result = RUNNERS[args.module](config, scope)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
