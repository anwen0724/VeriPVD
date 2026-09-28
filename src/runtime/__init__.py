from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = resolve_path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config must be a YAML mapping")
    if not raw.get("output_dir"):
        raise ValueError("output_dir is required")
    inputs = raw.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("inputs must be a non-empty list")
    seen = set()
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("Each input must be a mapping")
        scope_id = str(item.get("scope_id", ""))
        if not scope_id or scope_id in {".", ".."} or "/" in scope_id or "\\" in scope_id:
            raise ValueError(f"Invalid scope_id: {scope_id!r}")
        if scope_id in seen:
            raise ValueError(f"Duplicate scope_id: {scope_id}")
        if not item.get("rtl_dir"):
            raise ValueError(f"rtl_dir is required for {scope_id}")
        seen.add(scope_id)
    return raw


def select_scope(config: dict[str, Any], scope_id: str | None) -> dict[str, Any]:
    inputs = config["inputs"]
    if scope_id is None:
        if len(inputs) != 1:
            raise ValueError("--scope is required when config contains multiple inputs")
        return inputs[0]
    for item in inputs:
        if item["scope_id"] == scope_id:
            return item
    raise ValueError(f"Unknown scope_id: {scope_id}")


def scope_paths(config: dict[str, Any], scope: dict[str, Any]) -> tuple[Path, Path]:
    repo = resolve_path(scope["rtl_dir"])
    if not repo.is_dir():
        raise NotADirectoryError(f"RTL directory does not exist: {repo}")
    output = resolve_path(config["output_dir"]) / scope["scope_id"]
    return repo, output


def model_settings(config: dict[str, Any]) -> dict[str, str]:
    raw = config.get("llm")
    if not isinstance(raw, dict) or not raw.get("provider") or not raw.get("model"):
        raise ValueError("llm.provider and llm.model are required for model stages")
    return {"provider": str(raw["provider"]), "model": str(raw["model"])}


def ensure_model_output(output: Path, model: dict[str, str], checkpoint_name: str) -> None:
    metadata_path = output / "run_metadata.json"
    checkpoint_path = output / checkpoint_name
    if metadata_path.is_file():
        import json

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        previous = (metadata.get("provider"), metadata.get("model"))
        current = (model["provider"], model["model"])
        if previous != current:
            raise ValueError(f"Output contains results from model {previous}; choose a new output_dir")
    elif checkpoint_path.exists():
        raise ValueError(f"Output has a checkpoint without model metadata: {checkpoint_path}")
