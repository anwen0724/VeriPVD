from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm.langchain_models import LangChainModelConfig, create_chat_model
from permission_chain.target_screening import PermissionTargetScreeningConfig, run_permission_target_screening


@dataclass(frozen=True)
class PermissionTargetScreeningRunConfig:
    provider: str
    model: str
    model_id: str
    groups_path: str
    contexts_path: str
    output_dir: str
    temperature: float = 0.2
    max_tokens: int = 8192
    request_timeout: float | None = 600
    max_groups_per_batch: int = 6
    max_input_chars_per_batch: int = 60_000
    max_llm_attempts: int = 2


class PermissionTargetScreeningRunner:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[2]

    def run(self, config: PermissionTargetScreeningRunConfig) -> dict:
        chat_model = create_chat_model(
            LangChainModelConfig(
                provider=config.provider,
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                request_timeout=config.request_timeout,
            )
        )
        return run_permission_target_screening(
            groups_path=self._resolve(config.groups_path),
            contexts_path=self._resolve(config.contexts_path),
            output_dir=self._resolve(config.output_dir),
            chat_model=chat_model,
            provider=config.provider,
            model=config.model,
            model_id=config.model_id,
            config=PermissionTargetScreeningConfig(
                max_groups_per_batch=config.max_groups_per_batch,
                max_input_chars_per_batch=config.max_input_chars_per_batch,
                max_llm_attempts=config.max_llm_attempts,
            ),
        )

    def _resolve(self, path: str | Path) -> Path:
        value = Path(path)
        return value.resolve() if value.is_absolute() else (self.project_root / value).resolve()
