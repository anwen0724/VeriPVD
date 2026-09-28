from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_screening_outputs(
    output_dir: str | Path,
    screening_doc: dict[str, Any],
    retained_doc: dict[str, Any],
    diagnostics: dict[str, Any],
    raw_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / "permission_target_screening.json", screening_doc)
    _write_json(out / "retained_permission_target_groups.json", retained_doc)
    _write_json(out / "target_screening_diagnostics.json", diagnostics)
    _write_json(out / "run_metadata.json", metadata)
    with (out / "raw_llm_responses.jsonl").open("w", encoding="utf-8") as handle:
        for row in raw_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
