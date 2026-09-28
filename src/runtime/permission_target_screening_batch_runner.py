from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from permission_chain.target_screening.decision_merger import RETENTION_POLICY
from runtime.permission_target_screening_runner import (
    PermissionTargetScreeningRunConfig,
    PermissionTargetScreeningRunner,
)


@dataclass(frozen=True)
class ScreeningModelConfig:
    model_id: str
    provider: str
    model: str


@dataclass(frozen=True)
class ScreeningBatchConfig:
    batch_id: str
    groups_root: str
    output_root: str
    models: list[ScreeningModelConfig]
    scopes: list[str]
    temperature: float = 0.2
    max_tokens: int = 8192
    request_timeout: float | None = 600
    max_groups_per_batch: int = 6
    max_input_chars_per_batch: int = 60_000
    max_llm_attempts: int = 2


class PermissionTargetScreeningBatchRunner:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[2]
        self.single = PermissionTargetScreeningRunner(self.project_root)

    def run_from_config(self, config_path: str | Path) -> Path:
        resolved = self._resolve(config_path)
        return self.run(self.load_config(resolved), resolved)

    def load_config(self, config_path: str | Path) -> ScreeningBatchConfig:
        raw = yaml.safe_load(self._resolve(config_path).read_text(encoding="utf-8"))
        return ScreeningBatchConfig(
            batch_id=str(raw["batch_id"]),
            groups_root=str(raw.get("groups_root", "runs/validation/legacy_pilots/module2_v2/target_groups")),
            output_root=str(raw.get("output_root", "runs/validation/legacy_pilots/module2_v2/screening")),
            models=[ScreeningModelConfig(str(item["model_id"]), str(item["provider"]), str(item["model"])) for item in raw["models"]],
            scopes=[str(item) for item in raw["scopes"]],
            temperature=float(raw.get("temperature", 0.2)),
            max_tokens=int(raw.get("max_tokens", 8192)),
            request_timeout=float(raw["request_timeout"]) if raw.get("request_timeout") is not None else None,
            max_groups_per_batch=int(raw.get("max_groups_per_batch", 6)),
            max_input_chars_per_batch=int(raw.get("max_input_chars_per_batch", 60_000)),
            max_llm_attempts=int(raw.get("max_llm_attempts", 2)),
        )

    def run(self, config: ScreeningBatchConfig, source_config: Path | None = None) -> Path:
        batch_dir = self._resolve(config.output_root) / config.batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        status_path = batch_dir / "batch_status.jsonl"
        successful = {
            str(row.get("run_id"))
            for row in _read_jsonl(status_path)
            if row.get("status") == "success" and row.get("retention_policy") == RETENTION_POLICY
        }
        rows = []
        total = len(config.models) * len(config.scopes)
        current = 0
        for model in config.models:
            for scope in config.scopes:
                current += 1
                run_id = f"{config.batch_id}__{model.model_id}__{scope}"
                if run_id in successful:
                    print(f"[target-screening-batch][{current}/{total}] SKIP model={model.model_id} scope={scope}", flush=True)
                    continue
                groups_dir = self._resolve(config.groups_root) / scope
                output_dir = self._resolve(config.output_root) / model.model_id / scope
                print(f"[target-screening-batch][{current}/{total}] START model={model.model_id} scope={scope}", flush=True)
                try:
                    summary = self.single.run(
                        PermissionTargetScreeningRunConfig(
                            provider=model.provider,
                            model=model.model,
                            model_id=model.model_id,
                            groups_path=str(groups_dir / "permission_target_groups.json"),
                            contexts_path=str(groups_dir / "permission_target_group_contexts.json"),
                            output_dir=str(output_dir),
                            temperature=config.temperature,
                            max_tokens=config.max_tokens,
                            request_timeout=config.request_timeout,
                            max_groups_per_batch=config.max_groups_per_batch,
                            max_input_chars_per_batch=config.max_input_chars_per_batch,
                            max_llm_attempts=config.max_llm_attempts,
                        )
                    )
                    run_status = "success" if summary["failed_batch_count"] == 0 else "partial"
                    row = {"run_id": run_id, "status": run_status, "model_id": model.model_id, "scope": scope, **summary}
                    print(
                        f"[target-screening-batch][{current}/{total}] {run_status.upper()} "
                        f"model={model.model_id} scope={scope} "
                        f"retained={summary['retained_group_count']}/{summary['input_group_count']} "
                        f"failed_batches={summary['failed_batch_count']}",
                        flush=True,
                    )
                except Exception as exc:
                    row = {"run_id": run_id, "status": "failed", "model_id": model.model_id, "scope": scope, "error": str(exc)}
                    print(f"[target-screening-batch][{current}/{total}] FAIL model={model.model_id} scope={scope}: {exc}", flush=True)
                row["completed_at"] = datetime.now().astimezone().isoformat()
                _append_jsonl(status_path, row)
                rows.append(row)
        manifest = {
            "batch_id": config.batch_id,
            "source_config": str(source_config) if source_config else None,
            "models": [model.__dict__ for model in config.models],
            "scopes": config.scopes,
            "runs": [*_read_jsonl(status_path)],
        }
        (batch_dir / "batch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return batch_dir

    def _resolve(self, path: str | Path) -> Path:
        value = Path(path)
        return value.resolve() if value.is_absolute() else (self.project_root / value).resolve()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
