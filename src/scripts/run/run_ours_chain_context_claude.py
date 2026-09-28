from __future__ import annotations

import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from runtime.ours_chain_context_batch_runner import OursChainContextBatchRunner


CONFIG = PROJECT_ROOT / "configs" / "ours_chain_context_claude.yaml"


def main() -> int:
    batch_dir = OursChainContextBatchRunner(project_root=PROJECT_ROOT).run_from_config(CONFIG)
    print(f"[ok] batch_dir={batch_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
