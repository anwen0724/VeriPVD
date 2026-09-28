

from __future__ import annotations

import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from runtime.ours_chain_context_runner import OursChainContextRunConfig, OursChainContextRunRecord, OursChainContextRunner


@dataclass(frozen=True)
class BatchModelConfig:


    model_id: str
    provider: str
    model: str


@dataclass(frozen=True)
class BatchInputScopeConfig:


    scope_id: str
    path: str
    context_path: str | None = None


@dataclass(frozen=True)
class OursChainContextBatchConfig:


    batch_id: str
    method_name: str
    context_root: str
    output_root: str
    repetitions: int
    temperature: float
    max_tokens: int
    models: list[BatchModelConfig]
    input_scopes: list[BatchInputScopeConfig]
    max_chains: int | None = None
    request_timeout: float | None = 600
    require_violation_evidence: bool = True
    analysis_mode: str = "evidence_constrained"
    max_llm_attempts: int = 2
    max_concurrent_runs: int = 1


class OursChainContextBatchRunner:


    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else _default_project_root()
        self.single_runner = OursChainContextRunner(project_root=self.project_root)

    def run_from_config(self, config_path: str | Path) -> Path:
        resolved_config_path = self._resolve_path(config_path)
        config = self.load_config(resolved_config_path)
        return self.run(config, source_config_path=resolved_config_path)

    def run(self, config: OursChainContextBatchConfig, source_config_path: Path | None = None) -> Path:
        self._validate_config(config)
        if config.max_concurrent_runs > 1:
            return self._run_parallel(config, source_config_path)
        batch_dir = self._resolve_path(config.output_root) / config.batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = batch_dir / "batch_manifest.json"
        status_path = batch_dir / "batch_status.jsonl"
        config_copy_path = batch_dir / "batch_config.yaml"
        existing_status_rows = _load_status_rows(status_path)
        successful_run_ids = {
            str(row.get("run_id"))
            for row in existing_status_rows
            if row.get("batch_id") == config.batch_id and row.get("status") == "success"
        }

        if source_config_path:
            shutil.copyfile(source_config_path, config_copy_path)
        else:
            config_copy_path.write_text(
                yaml.safe_dump(_batch_config_to_dict(config), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        manifest = {
            "batch_id": config.batch_id,
            "method_name": config.method_name,
            "context_root": str(self._resolve_path(config.context_root)),
            "output_root": str(self._resolve_path(config.output_root)),
            "repetitions": config.repetitions,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "max_chains": config.max_chains,
            "request_timeout": config.request_timeout,
            "require_violation_evidence": config.require_violation_evidence,
            "analysis_mode": config.analysis_mode,
            "max_llm_attempts": config.max_llm_attempts,
            "max_concurrent_runs": config.max_concurrent_runs,
            "models": [model.__dict__ for model in config.models],
            "input_scopes": [scope.__dict__ for scope in config.input_scopes],
            "started_at": _now_iso(),
            "runs": existing_status_rows.copy(),
        }

        total_runs = len(config.models) * len(config.input_scopes) * config.repetitions
        current_run = 0
        success_count = 0
        failed_count = 0
        partial_count = 0
        skipped_count = 0

        print(
            f"[ours-chain-context] batch_id={config.batch_id} total_runs={total_runs} "
            f"models={len(config.models)} scopes={len(config.input_scopes)} "
            f"repetitions={config.repetitions}",
            flush=True,
        )

        for model_cfg in config.models:
            for scope_cfg in config.input_scopes:
                for rep in range(1, config.repetitions + 1):
                    current_run += 1
                    run_id = f"rep_{rep}"
                    full_run_id = f"{config.batch_id}__{model_cfg.model_id}__{scope_cfg.scope_id}__{run_id}"
                    if full_run_id in successful_run_ids:
                        skipped_count += 1
                        print(
                            f"[ours-chain-context][{current_run}/{total_runs}] SKIP "
                            f"model={model_cfg.model_id} scope={scope_cfg.scope_id} rep={rep}",
                            flush=True,
                        )
                        continue

                    context_path = self._context_path(config, scope_cfg)
                    repo_path = self._resolve_path(scope_cfg.path)
                    run_output_dir = (
                        Path(config.output_root)
                        / config.batch_id
                        / "models"
                        / model_cfg.model_id
                        / scope_cfg.scope_id
                    )
                    run_config = OursChainContextRunConfig(
                        run_id=run_id,
                        provider=model_cfg.provider,
                        model=model_cfg.model,
                        context_path=str(context_path),
                        repo_path=str(repo_path),
                        output_dir=str(run_output_dir),
                        temperature=config.temperature,
                        max_tokens=config.max_tokens,
                        max_chains=config.max_chains,
                        request_timeout=config.request_timeout,
                        require_violation_evidence=config.require_violation_evidence,
                        analysis_mode=config.analysis_mode,
                        method_name=config.method_name,
                        max_llm_attempts=config.max_llm_attempts,
                    )

                    started_at = _now_iso()
                    run_started = time.monotonic()
                    print(
                        f"[ours-chain-context][{current_run}/{total_runs}] START "
                        f"model={model_cfg.model_id} provider={model_cfg.provider} "
                        f"scope={scope_cfg.scope_id} rep={rep}",
                        flush=True,
                    )
                    try:
                        record = self.single_runner.run(run_config)
                        elapsed_seconds = time.monotonic() - run_started
                        status = _success_status(
                            config=config,
                            model_cfg=model_cfg,
                            scope_cfg=scope_cfg,
                            rep=rep,
                            full_run_id=full_run_id,
                            context_path=context_path,
                            repo_path=repo_path,
                            record=record,
                            started_at=started_at,
                            elapsed_seconds=elapsed_seconds,
                        )
                        if record.failed_chain_count:
                            partial_count += 1
                        else:
                            success_count += 1
                        print(
                            f"[ours-chain-context][{current_run}/{total_runs}] {status['status'].upper()} "
                            f"model={model_cfg.model_id} scope={scope_cfg.scope_id} "
                            f"rep={rep} seconds={elapsed_seconds:.1f} "
                            f"failed_chains={record.failed_chain_count} tokens={record.total_tokens}",
                            flush=True,
                        )
                    except Exception as exc:
                        elapsed_seconds = time.monotonic() - run_started
                        status = _failed_status(
                            config=config,
                            model_cfg=model_cfg,
                            scope_cfg=scope_cfg,
                            rep=rep,
                            full_run_id=full_run_id,
                            context_path=context_path,
                            repo_path=repo_path,
                            run_output_dir=self._resolve_path(run_output_dir) / run_id,
                            started_at=started_at,
                            elapsed_seconds=elapsed_seconds,
                            error=str(exc),
                        )
                        failed_count += 1
                        print(
                            f"[ours-chain-context][{current_run}/{total_runs}] FAIL "
                            f"model={model_cfg.model_id} scope={scope_cfg.scope_id} "
                            f"rep={rep} seconds={elapsed_seconds:.1f}",
                            flush=True,
                        )
                        print(f"[ours-chain-context][{current_run}/{total_runs}] error={exc}", flush=True)

                    _append_jsonl(status_path, status)
                    manifest["runs"].append(status)

        manifest["completed_at"] = _now_iso()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[ours-chain-context] batch completed: success={success_count} "
            f"partial={partial_count} failed={failed_count} skipped={skipped_count} total={total_runs}",
            flush=True,
        )
        print(f"[ours-chain-context] status_file={status_path}", flush=True)
        return batch_dir

    def load_config(self, config_path: str | Path) -> OursChainContextBatchConfig:
        path = self._resolve_path(config_path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Batch config must be a YAML mapping")

        return OursChainContextBatchConfig(
            batch_id=str(raw["batch_id"]),
            method_name=str(raw["method_name"]),
            context_root=str(raw.get("context_root", "runs/validation/previous_chain_context_1049/module3/contexts_1748")),
            output_root=str(raw.get("output_root", "runs/validation/previous_chain_context_1049/findings")),
            repetitions=int(raw.get("repetitions", 1)),
            temperature=float(raw.get("temperature", 0.2)),
            max_tokens=int(raw.get("max_tokens", 8192)),
            max_chains=_optional_int(raw.get("max_chains")),
            request_timeout=_optional_float(raw.get("request_timeout", 600)),
            require_violation_evidence=bool(raw.get("require_violation_evidence", True)),
            analysis_mode=str(raw.get("analysis_mode", "evidence_constrained")),
            max_llm_attempts=int(raw.get("max_llm_attempts", 2)),
            max_concurrent_runs=int(raw.get("max_concurrent_runs", 1)),
            models=[
                BatchModelConfig(
                    model_id=str(item["model_id"]),
                    provider=str(item["provider"]),
                    model=str(item["model"]),
                )
                for item in raw["models"]
            ],
            input_scopes=[
                BatchInputScopeConfig(
                    scope_id=str(item["scope_id"]),
                    path=str(item["path"]),
                    context_path=str(item["context_path"]) if item.get("context_path") else None,
                )
                for item in raw["input_scopes"]
            ],
        )

    def _run_parallel(
        self,
        config: OursChainContextBatchConfig,
        source_config_path: Path | None,
    ) -> Path:
        batch_dir = self._resolve_path(config.output_root) / config.batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = batch_dir / "batch_manifest.json"
        status_path = batch_dir / "batch_status.jsonl"
        config_copy_path = batch_dir / "batch_config.yaml"
        existing_status_rows = _load_status_rows(status_path)
        successful_run_ids = {
            str(row.get("run_id"))
            for row in existing_status_rows
            if row.get("batch_id") == config.batch_id and row.get("status") == "success"
        }
        if source_config_path:
            shutil.copyfile(source_config_path, config_copy_path)
        else:
            config_copy_path.write_text(
                yaml.safe_dump(_batch_config_to_dict(config), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        manifest = {
            "batch_id": config.batch_id,
            "method_name": config.method_name,
            "context_root": str(self._resolve_path(config.context_root)),
            "output_root": str(self._resolve_path(config.output_root)),
            "repetitions": config.repetitions,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "max_chains": config.max_chains,
            "request_timeout": config.request_timeout,
            "require_violation_evidence": config.require_violation_evidence,
            "analysis_mode": config.analysis_mode,
            "max_llm_attempts": config.max_llm_attempts,
            "max_concurrent_runs": config.max_concurrent_runs,
            "models": [model.__dict__ for model in config.models],
            "input_scopes": [scope.__dict__ for scope in config.input_scopes],
            "started_at": _now_iso(),
            "runs": existing_status_rows.copy(),
        }
        jobs: list[tuple[int, BatchModelConfig, BatchInputScopeConfig, int, str]] = []
        total_runs = len(config.models) * len(config.input_scopes) * config.repetitions
        skipped_count = 0
        sequence = 0
        for model_cfg in config.models:
            for scope_cfg in config.input_scopes:
                for rep in range(1, config.repetitions + 1):
                    sequence += 1
                    full_run_id = f"{config.batch_id}__{model_cfg.model_id}__{scope_cfg.scope_id}__rep_{rep}"
                    if full_run_id in successful_run_ids:
                        skipped_count += 1
                        print(
                            f"[ours-chain-context][{sequence}/{total_runs}] SKIP "
                            f"model={model_cfg.model_id} scope={scope_cfg.scope_id} rep={rep}",
                            flush=True,
                        )
                        continue
                    jobs.append((sequence, model_cfg, scope_cfg, rep, full_run_id))
        print(
            f"[ours-chain-context] batch_id={config.batch_id} total_runs={total_runs} "
            f"pending={len(jobs)} concurrent={config.max_concurrent_runs}",
            flush=True,
        )
        success_count = 0
        partial_count = 0
        failed_count = 0
        with ThreadPoolExecutor(max_workers=config.max_concurrent_runs) as executor:
            futures = {
                executor.submit(
                    self._run_parallel_job,
                    config,
                    sequence_no,
                    total_runs,
                    model_cfg,
                    scope_cfg,
                    rep,
                    full_run_id,
                ): (sequence_no, scope_cfg.scope_id)
                for sequence_no, model_cfg, scope_cfg, rep, full_run_id in jobs
            }
            for future in as_completed(futures):
                sequence_no, scope_id = futures[future]
                try:
                    status = future.result()
                except Exception as exc:
                    status = {
                        "batch_id": config.batch_id,
                        "run_id": f"{config.batch_id}__unknown__{scope_id}__unknown",
                        "scope_id": scope_id,
                        "status": "failed",
                        "completed_at": _now_iso(),
                        "error": str(exc),
                    }
                    print(f"[ours-chain-context][{sequence_no}/{total_runs}] FAIL scope={scope_id}: {exc}", flush=True)
                if status["status"] == "success":
                    success_count += 1
                elif status["status"] == "partial":
                    partial_count += 1
                else:
                    failed_count += 1
                _append_jsonl(status_path, status)
                manifest["runs"].append(status)
        manifest["completed_at"] = _now_iso()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[ours-chain-context] batch completed: success={success_count} partial={partial_count} "
            f"failed={failed_count} skipped={skipped_count} total={total_runs}",
            flush=True,
        )
        print(f"[ours-chain-context] status_file={status_path}", flush=True)
        return batch_dir

    def _run_parallel_job(
        self,
        config: OursChainContextBatchConfig,
        sequence_no: int,
        total_runs: int,
        model_cfg: BatchModelConfig,
        scope_cfg: BatchInputScopeConfig,
        rep: int,
        full_run_id: str,
    ) -> dict[str, Any]:
        context_path = self._context_path(config, scope_cfg)
        repo_path = self._resolve_path(scope_cfg.path)
        run_output_dir = Path(config.output_root) / config.batch_id / "models" / model_cfg.model_id / scope_cfg.scope_id
        run_config = OursChainContextRunConfig(
            run_id=f"rep_{rep}",
            provider=model_cfg.provider,
            model=model_cfg.model,
            context_path=str(context_path),
            repo_path=str(repo_path),
            output_dir=str(run_output_dir),
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_chains=config.max_chains,
            request_timeout=config.request_timeout,
            require_violation_evidence=config.require_violation_evidence,
            analysis_mode=config.analysis_mode,
            method_name=config.method_name,
            max_llm_attempts=config.max_llm_attempts,
        )
        started_at = _now_iso()
        run_started = time.monotonic()
        print(
            f"[ours-chain-context][{sequence_no}/{total_runs}] START model={model_cfg.model_id} "
            f"provider={model_cfg.provider} scope={scope_cfg.scope_id} rep={rep}",
            flush=True,
        )
        try:
            record = self.single_runner.run(run_config)
            elapsed_seconds = time.monotonic() - run_started
            status = _success_status(
                config=config,
                model_cfg=model_cfg,
                scope_cfg=scope_cfg,
                rep=rep,
                full_run_id=full_run_id,
                context_path=context_path,
                repo_path=repo_path,
                record=record,
                started_at=started_at,
                elapsed_seconds=elapsed_seconds,
            )
            print(
                f"[ours-chain-context][{sequence_no}/{total_runs}] {status['status'].upper()} "
                f"model={model_cfg.model_id} scope={scope_cfg.scope_id} rep={rep} "
                f"seconds={elapsed_seconds:.1f} failed_chains={record.failed_chain_count} tokens={record.total_tokens}",
                flush=True,
            )
            return status
        except Exception as exc:
            elapsed_seconds = time.monotonic() - run_started
            print(
                f"[ours-chain-context][{sequence_no}/{total_runs}] FAIL model={model_cfg.model_id} "
                f"scope={scope_cfg.scope_id} rep={rep} seconds={elapsed_seconds:.1f} error={exc}",
                flush=True,
            )
            return _failed_status(
                config=config,
                model_cfg=model_cfg,
                scope_cfg=scope_cfg,
                rep=rep,
                full_run_id=full_run_id,
                context_path=context_path,
                repo_path=repo_path,
                run_output_dir=self._resolve_path(run_output_dir) / f"rep_{rep}",
                started_at=started_at,
                elapsed_seconds=elapsed_seconds,
                error=str(exc),
            )

    def _validate_config(self, config: OursChainContextBatchConfig) -> None:
        if not config.batch_id:
            raise ValueError("batch_id is required")
        allowed_methods = {
            "ours_chain_context",
            "rq2_without_target_organization",
            "rq2_without_cross_module_chain",
            "rq2_without_evidence_constraint",
        }
        if config.method_name not in allowed_methods:
            raise ValueError(f"Unsupported method_name: {config.method_name}")
        if config.analysis_mode not in {"evidence_constrained", "without_evidence_constraint"}:
            raise ValueError(f"Unsupported analysis_mode: {config.analysis_mode}")
        if config.analysis_mode == "without_evidence_constraint" and config.require_violation_evidence:
            raise ValueError("without_evidence_constraint requires require_violation_evidence=false")
        if config.repetitions < 1:
            raise ValueError("repetitions must be >= 1")
        if config.max_llm_attempts < 1:
            raise ValueError("max_llm_attempts must be >= 1")
        if config.max_concurrent_runs < 1:
            raise ValueError("max_concurrent_runs must be >= 1")
        if not config.models:
            raise ValueError("models must not be empty")
        if not config.input_scopes:
            raise ValueError("input_scopes must not be empty")
        for scope in config.input_scopes:
            repo_path = self._resolve_path(scope.path)
            if not repo_path.exists():
                raise FileNotFoundError(f"Input scope does not exist: {scope.scope_id}: {repo_path}")
            if not repo_path.is_dir():
                raise NotADirectoryError(f"Input scope is not a directory: {scope.scope_id}: {repo_path}")
            context_path = self._context_path(config, scope)
            if not context_path.exists():
                raise FileNotFoundError(f"Context file does not exist: {scope.scope_id}: {context_path}")

    def _context_path(self, config: OursChainContextBatchConfig, scope: BatchInputScopeConfig) -> Path:
        if scope.context_path:
            return self._resolve_path(scope.context_path)
        return self._resolve_path(config.context_root) / scope.scope_id / "permission_chain_contexts.json"

    def _resolve_path(self, path: str | Path) -> Path:
        raw = Path(path)
        if raw.is_absolute():
            return raw.resolve()
        return (self.project_root / raw).resolve()


def _success_status(
    *,
    config: OursChainContextBatchConfig,
    model_cfg: BatchModelConfig,
    scope_cfg: BatchInputScopeConfig,
    rep: int,
    full_run_id: str,
    context_path: Path,
    repo_path: Path,
    record: OursChainContextRunRecord,
    started_at: str,
    elapsed_seconds: float,
) -> dict[str, Any]:
    return {
        "batch_id": config.batch_id,
        "run_id": full_run_id,
        "model_id": model_cfg.model_id,
        "provider": model_cfg.provider,
        "model": model_cfg.model,
        "scope_id": scope_cfg.scope_id,
        "repetition": rep,
        "status": "partial" if record.failed_chain_count else "success",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "elapsed_seconds": elapsed_seconds,
        "context_path": str(context_path),
        "repo_path": str(repo_path),
        "run_dir": record.run_dir,
        "final_answer_path": record.final_answer_path,
        "final_findings_path": record.final_findings_path,
        "diagnostics_path": record.diagnostics_path,
        "failed_chain_count": record.failed_chain_count,
        "successful_chain_count": record.successful_chain_count,
        "llm_call_count": record.llm_call_count,
        "total_tokens": record.total_tokens,
        "error": None,
    }


def _failed_status(
    *,
    config: OursChainContextBatchConfig,
    model_cfg: BatchModelConfig,
    scope_cfg: BatchInputScopeConfig,
    rep: int,
    full_run_id: str,
    context_path: Path,
    repo_path: Path,
    run_output_dir: Path,
    started_at: str,
    elapsed_seconds: float,
    error: str,
) -> dict[str, Any]:
    return {
        "batch_id": config.batch_id,
        "run_id": full_run_id,
        "model_id": model_cfg.model_id,
        "provider": model_cfg.provider,
        "model": model_cfg.model,
        "scope_id": scope_cfg.scope_id,
        "repetition": rep,
        "status": "failed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "elapsed_seconds": elapsed_seconds,
        "context_path": str(context_path),
        "repo_path": str(repo_path),
        "run_dir": str(run_output_dir),
        "error": error,
    }


def _batch_config_to_dict(config: OursChainContextBatchConfig) -> dict[str, Any]:
    return {
        "batch_id": config.batch_id,
        "method_name": config.method_name,
        "context_root": config.context_root,
        "output_root": config.output_root,
        "repetitions": config.repetitions,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "max_chains": config.max_chains,
        "request_timeout": config.request_timeout,
        "require_violation_evidence": config.require_violation_evidence,
        "analysis_mode": config.analysis_mode,
        "max_llm_attempts": config.max_llm_attempts,
        "max_concurrent_runs": config.max_concurrent_runs,
        "models": [model.__dict__ for model in config.models],
        "input_scopes": [scope.__dict__ for scope in config.input_scopes],
    }


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_status_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]
