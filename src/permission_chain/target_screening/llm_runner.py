from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage

from vulnerability_analysis.chain_context_analysis.llm_runner import _extract_token_usage, _message_content_to_text

from .schema import ScreeningBatchResponse


def invoke_screening_batch(
    chat_model: Any,
    prompt: str,
    max_attempts: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    started = time.monotonic()
    diagnostics: dict[str, Any] = {
        "status": "not_started",
        "failure_stage": "",
        "error": "",
        "started_at": _now_iso(),
        "completed_at": "",
        "elapsed_seconds": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "token_usage_source": "unavailable",
        "llm_calls": 0,
        "attempts": [],
    }
    content = ""
    for attempt in range(1, max_attempts + 1):
        attempt_started = time.monotonic()
        attempt_diag: dict[str, Any] = {
            "attempt": attempt,
            "status": "not_started",
            "failure_stage": "",
            "error": "",
        }
        diagnostics["llm_calls"] += 1
        try:
            raw = chat_model.invoke([HumanMessage(content=prompt + "\nReturn only JSON. Do not use Markdown fences.")])
        except Exception as exc:
            attempt_diag.update(status="failed", failure_stage="api_call", error=str(exc))
            _finish_attempt(attempt_diag, attempt_started)
            diagnostics["attempts"].append(attempt_diag)
            continue
        content = _message_content_to_text(getattr(raw, "content", raw))
        usage = _extract_token_usage(raw, prompt, content)
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            diagnostics[key] += int(usage.get(key, 0) or 0)
        diagnostics["token_usage_source"] = usage.get("token_usage_source", "unavailable")
        attempt_diag.update(usage)
        try:
            payload = _extract_json_object(content)
        except Exception as exc:
            attempt_diag.update(status="failed", failure_stage="json_extract", error=str(exc))
            _finish_attempt(attempt_diag, attempt_started)
            diagnostics["attempts"].append(attempt_diag)
            continue
        try:
            response = ScreeningBatchResponse.model_validate(payload)
        except Exception as exc:
            attempt_diag.update(status="failed", failure_stage="schema_validate", error=str(exc))
            _finish_attempt(attempt_diag, attempt_started)
            diagnostics["attempts"].append(attempt_diag)
            continue
        attempt_diag["status"] = "ok"
        _finish_attempt(attempt_diag, attempt_started)
        diagnostics["attempts"].append(attempt_diag)
        diagnostics.update(status="ok", failure_stage="", error="")
        diagnostics["completed_at"] = _now_iso()
        diagnostics["elapsed_seconds"] = time.monotonic() - started
        return [decision.model_dump() for decision in response.decisions], diagnostics, content
    last = diagnostics["attempts"][-1]
    diagnostics.update(
        status="failed",
        failure_stage=last.get("failure_stage", ""),
        error=last.get("error", ""),
    )
    diagnostics["completed_at"] = _now_iso()
    diagnostics["elapsed_seconds"] = time.monotonic() - started
    return [], diagnostics, content


def _finish_attempt(attempt: dict[str, Any], started: float) -> None:
    attempt["completed_at"] = _now_iso()
    attempt["elapsed_seconds"] = time.monotonic() - started


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()
