from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import PermissionTargetScreeningConfig
from .decision_merger import RETENTION_POLICY, merge_screening_decisions
from .llm_runner import invoke_screening_batch
from prompts.target_screening import build_screening_prompt, make_batches
from .writer import write_screening_outputs


def run_permission_target_screening(
    groups_path: str | Path,
    contexts_path: str | Path,
    output_dir: str | Path,
    chat_model: Any,
    provider: str,
    model: str,
    model_id: str,
    config: PermissionTargetScreeningConfig | None = None,
) -> dict[str, Any]:
    cfg = config or PermissionTargetScreeningConfig()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_path / "screening_batch_checkpoint.jsonl"
    groups_doc = json.loads(Path(groups_path).read_text(encoding="utf-8"))
    contexts_doc = json.loads(Path(contexts_path).read_text(encoding="utf-8"))
    if groups_doc.get("graph_id") != contexts_doc.get("graph_id"):
        raise ValueError("Target groups and contexts graph_id differ")
    expected_ids = {str(group.get("target_group_id", "")) for group in groups_doc.get("groups", []) or []}
    context_ids = {str(group.get("target_group_id", "")) for group in contexts_doc.get("groups", []) or []}
    if expected_ids != context_ids:
        raise ValueError("Target groups and context target_group_id sets differ")

    batches = make_batches(list(contexts_doc.get("groups", [])), cfg)
    raw_decisions: list[dict[str, Any]] = []
    checkpoint_rows = _read_jsonl(checkpoint_path)
    successful_checkpoints = _successful_checkpoints(checkpoint_rows)
    current_signatures: set[str] = set()
    per_batch: list[dict[str, Any]] = []
    started_at = _now_iso()
    started = time.monotonic()
    for index, batch in enumerate(batches, start=1):
        group_ids = [str(group.get("target_group_id", "")) for group in batch]
        prompt = build_screening_prompt(batch)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        signature = _batch_signature(group_ids, prompt_hash)
        current_signatures.add(signature)
        checkpoint = successful_checkpoints.get(signature)
        if checkpoint is not None:
            decisions = list(checkpoint.get("decisions", []))
            raw_decisions.extend(decisions)
            batch_row = {
                **_checkpoint_diagnostics(checkpoint),
                "batch_index": index,
                "target_group_ids": group_ids,
                "prompt_hash": prompt_hash,
                "prompt_chars": len(prompt),
                "decision_count": len(decisions),
                "reused_from_checkpoint": True,
            }
            per_batch.append(batch_row)
            print(
                f"[target-screening][{index}/{len(batches)}] SKIP graph={groups_doc.get('graph_id')} "
                f"groups={len(batch)} checkpoint=success decisions={len(decisions)}",
                flush=True,
            )
            continue
        print(
            f"[target-screening][{index}/{len(batches)}] START graph={groups_doc.get('graph_id')} "
            f"groups={len(batch)} chars={len(prompt)}",
            flush=True,
        )
        decisions, diagnostics, raw_text = invoke_screening_batch(
            chat_model,
            prompt,
            max_attempts=cfg.max_llm_attempts,
        )
        raw_decisions.extend(decisions)
        batch_row = {
            "batch_index": index,
            "target_group_ids": group_ids,
            "prompt_hash": prompt_hash,
            "batch_signature": signature,
            "prompt_chars": len(prompt),
            "decision_count": len(decisions),
            "decisions": decisions,
            "raw_response": raw_text,
            "reused_from_checkpoint": False,
            **diagnostics,
        }
        per_batch.append(batch_row)
        _append_jsonl(checkpoint_path, batch_row)
        checkpoint_rows.append(batch_row)
        print(
            f"[target-screening][{index}/{len(batches)}] {diagnostics['status'].upper()} "
            f"decisions={len(decisions)} seconds={diagnostics['elapsed_seconds']:.1f} "
            f"tokens={diagnostics['total_tokens']}",
            flush=True,
        )

    screening_doc, retained_doc, merge_diagnostics = merge_screening_decisions(groups_doc, raw_decisions)
    screening_doc.update({"provider": provider, "model": model, "model_id": model_id})
    relevant_history = [row for row in checkpoint_rows if row.get("batch_signature") in current_signatures]
    raw_rows = [_raw_response_row(row) for row in relevant_history]
    diagnostics = {
        "graph_id": groups_doc.get("graph_id", ""),
        "provider": provider,
        "model": model,
        "model_id": model_id,
        "batch_count": len(batches),
        "llm_call_count": sum(int(item.get("llm_calls", 0)) for item in relevant_history),
        "current_run_llm_call_count": sum(
            int(item.get("llm_calls", 0)) for item in per_batch if not item.get("reused_from_checkpoint")
        ),
        "reused_batch_count": sum(1 for item in per_batch if item.get("reused_from_checkpoint")),
        "successful_batch_count": sum(1 for item in per_batch if item["status"] == "ok"),
        "failed_batch_count": sum(1 for item in per_batch if item["status"] != "ok"),
        "input_tokens": sum(int(item.get("input_tokens", 0)) for item in relevant_history),
        "output_tokens": sum(int(item.get("output_tokens", 0)) for item in relevant_history),
        "total_tokens": sum(int(item.get("total_tokens", 0)) for item in relevant_history),
        "runtime_seconds": time.monotonic() - started,
        "cumulative_llm_runtime_seconds": sum(float(item.get("elapsed_seconds", 0.0)) for item in relevant_history),
        **merge_diagnostics,
        "per_batch": per_batch,
    }
    metadata = {
        "graph_id": groups_doc.get("graph_id", ""),
        "provider": provider,
        "model": model,
        "model_id": model_id,
        "groups_path": str(groups_path),
        "contexts_path": str(contexts_path),
        "output_dir": str(output_dir),
        "started_at": started_at,
        "completed_at": _now_iso(),
        "retention_policy": RETENTION_POLICY,
        "config": cfg.__dict__,
    }
    write_screening_outputs(output_dir, screening_doc, retained_doc, diagnostics, raw_rows, metadata)
    return {
        "graph_id": groups_doc.get("graph_id", ""),
        "input_group_count": merge_diagnostics["input_group_count"],
        "retained_group_count": merge_diagnostics["retained_group_count"],
        "excluded_group_count": merge_diagnostics["excluded_group_count"],
        "fallback_group_count": merge_diagnostics["fallback_group_count"],
        "batch_count": len(batches),
        "llm_call_count": diagnostics["llm_call_count"],
        "current_run_llm_call_count": diagnostics["current_run_llm_call_count"],
        "reused_batch_count": diagnostics["reused_batch_count"],
        "successful_batch_count": diagnostics["successful_batch_count"],
        "failed_batch_count": diagnostics["failed_batch_count"],
        "total_tokens": diagnostics["total_tokens"],
        "runtime_seconds": diagnostics["runtime_seconds"],
        "retention_policy": RETENTION_POLICY,
        "output_dir": str(output_dir),
    }


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _batch_signature(group_ids: list[str], prompt_hash: str) -> str:
    payload = json.dumps({"target_group_ids": group_ids, "prompt_hash": prompt_hash}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _successful_checkpoints(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    successful: dict[str, dict[str, Any]] = {}
    for row in rows:
        signature = str(row.get("batch_signature", ""))
        if signature and row.get("status") == "ok":
            successful[signature] = row
    return successful


def _checkpoint_diagnostics(row: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "batch_index",
        "target_group_ids",
        "prompt_hash",
        "batch_signature",
        "prompt_chars",
        "decision_count",
        "decisions",
        "raw_response",
        "reused_from_checkpoint",
    }
    return {key: value for key, value in row.items() if key not in excluded}


def _raw_response_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_index": row.get("batch_index"),
        "target_group_ids": row.get("target_group_ids", []),
        "prompt_hash": row.get("prompt_hash", ""),
        "status": row.get("status", ""),
        "attempts": row.get("attempts", []),
        "raw_response": row.get("raw_response", ""),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
