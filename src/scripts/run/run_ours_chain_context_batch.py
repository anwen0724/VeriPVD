from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from runtime.ours_chain_context_batch_runner import OursChainContextBatchRunner


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "ours_chain_context_deepseek.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ours chain-context batch from a YAML config.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="YAML batch config. Defaults to configs/ours_chain_context_deepseek.yaml.",
    )
    args = parser.parse_args(argv)

    batch_dir = OursChainContextBatchRunner(project_root=PROJECT_ROOT).run_from_config(args.config)
    print(f"[ok] batch_dir={batch_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
