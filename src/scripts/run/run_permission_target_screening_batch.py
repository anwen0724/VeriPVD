from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from runtime.permission_target_screening_batch_runner import PermissionTargetScreeningBatchRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run real LLM permission target-group screening.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    output = PermissionTargetScreeningBatchRunner(PROJECT_ROOT).run_from_config(args.config)
    print(f"[target-screening-batch] output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
