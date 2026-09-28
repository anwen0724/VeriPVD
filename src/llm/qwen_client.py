

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .env import get_env, load_project_env


@dataclass
class QwenClientConfig:


    model: str = "qwen-plus"
    temperature: float = 0.2
    max_tokens: int = 8192
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class QwenClient:


    def __init__(self, cfg: Optional[QwenClientConfig] = None) -> None:
        load_project_env()
        self.cfg = cfg or QwenClientConfig()
        from openai import OpenAI

        self.client = OpenAI(
            api_key=self.cfg.api_key or get_env("QWEN_API_KEY"),
            base_url=self.cfg.base_url or get_env("QWEN_BASE_URL"),
        )

    def generate(self, prompt: str) -> str:


        response = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        return response.choices[0].message.content or ""
