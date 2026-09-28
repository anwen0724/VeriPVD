from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from runtime import load_config
from runtime import permission_chain, rtl_structure_graph, vulnerability_analysis


RUNNERS = {
    "rtl_structure_graph": rtl_structure_graph.run,
    "permission_chain": permission_chain.run,
    "vulnerability_analysis": vulnerability_analysis.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one VeriPVD module for all configured RTL inputs.")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--module", required=True, choices=RUNNERS)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    batch = config.get("batch", {})
    analysis = config.get("vulnerability_analysis", {}).get("analysis", {})
    repetitions = int(analysis.get("repetitions", 1)) if args.module == "vulnerability_analysis" else 1
    workers = int(batch.get("max_concurrent_runs", 1))
    if repetitions < 1 or workers < 1:
        raise ValueError("repetitions and max_concurrent_runs must be positive")
    def run_scope(scope: dict) -> object:
        runner = RUNNERS[args.module]
        if args.module == "vulnerability_analysis" and repetitions > 1:
            return [runner(config, scope, repetition) for repetition in range(1, repetitions + 1)]
        return runner(config, scope)

    errors = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(run_scope, scope): scope["scope_id"] for scope in config["inputs"]}
        for future in as_completed(pending):
            scope_id = pending[future]
            try:
                result = future.result()
                print(json.dumps({"batch_id": batch.get("batch_id", ""), "scope_id": scope_id, "result": result}, ensure_ascii=False))
            except Exception as exc:
                errors.append((scope_id, str(exc)))
                print(json.dumps({"batch_id": batch.get("batch_id", ""), "scope_id": scope_id, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
