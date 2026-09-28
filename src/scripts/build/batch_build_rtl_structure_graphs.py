from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rtl_structure_graph.builder import build_rtl_structure_graph
from rtl_structure_graph.writer import write_build_outputs


DEFAULT_INPUT_ROOT = PROJECT_ROOT / "datasets" / "agent_inputs"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "runs" / "ours" / "module1" / "rtl_structure_graphs"


@dataclass(frozen=True)
class InputScope:
    benchmark: str
    scope_name: str
    path: Path

    @property
    def scope_id(self) -> str:
        return f"{self.benchmark}__{self.scope_name}"


def discover_input_scopes(input_root: str | Path) -> list[InputScope]:
    root = Path(input_root)
    scopes: list[InputScope] = []
    if not root.exists():
        return scopes
    for benchmark_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for scope_dir in sorted(path for path in benchmark_dir.iterdir() if path.is_dir()):
            if _has_rtl_files(scope_dir):
                scopes.append(
                    InputScope(
                        benchmark=benchmark_dir.name,
                        scope_name=scope_dir.name,
                        path=scope_dir,
                    )
                )
    return scopes


def run_batch(
    input_root: str | Path = DEFAULT_INPUT_ROOT,
    out_root: str | Path = DEFAULT_OUT_ROOT,
    selected_scopes: list[str] | None = None,
) -> dict[str, Any]:
    scopes = discover_input_scopes(input_root)
    if selected_scopes:
        selected = set(selected_scopes)
        scopes = [
            scope
            for scope in scopes
            if scope.scope_id in selected or scope.scope_name in selected
        ]

    output_root = Path(out_root)
    output_root.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    for scope in scopes:
        scope_out = output_root / scope.scope_id
        result = build_rtl_structure_graph(scope.path, graph_id=scope.scope_id)
        graph_path, diagnostics_path = write_build_outputs(result.graph, result.diagnostics, scope_out)
        runs.append(
            {
                "scope_id": scope.scope_id,
                "benchmark": scope.benchmark,
                "scope_name": scope.scope_name,
                "input_path": str(scope.path),
                "output_dir": str(scope_out),
                "graph_path": str(graph_path),
                "diagnostics_path": str(diagnostics_path),
                "status": "success",
                "stats": result.diagnostics.stats,
                "warning_count": len(result.diagnostics.warnings),
            }
        )
        print(f"[ok] {scope.scope_id} -> {scope_out}", flush=True)

    manifest = {
        "input_root": str(Path(input_root)),
        "out_root": str(output_root),
        "total_scopes": len(runs),
        "runs": runs,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[manifest] {manifest_path}", flush=True)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch build module-1 RTL structure graphs.")
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT_ROOT),
        help="Root containing benchmark/scope RTL repo directories.",
    )
    parser.add_argument(
        "--out-root",
        default=str(DEFAULT_OUT_ROOT),
        help="Output root for per-scope graph directories.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=None,
        help="Optional scope_name or benchmark__scope_name. Repeat to select multiple scopes.",
    )
    args = parser.parse_args(argv)

    manifest = run_batch(args.input_root, args.out_root, args.scope)
    if manifest["total_scopes"] == 0:
        print("[warn] no input scopes found", flush=True)
    return 0


def _has_rtl_files(path: Path) -> bool:
    return any(
        file.is_file() and file.suffix.lower() in {".v", ".sv", ".vh"}
        for file in path.rglob("*")
    )


if __name__ == "__main__":
    raise SystemExit(main())
