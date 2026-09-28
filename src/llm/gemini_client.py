

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from .env import get_first_env, load_project_env


@dataclass
class GeminiClientConfig:


    model: str = "gemini-2.5-pro"
    temperature: float = 0.2
    max_tokens: int = 8192
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class GeminiClient:


    def __init__(self, cfg: Optional[GeminiClientConfig] = None) -> None:
        load_project_env()
        self.cfg = cfg or GeminiClientConfig()
        api_key = self.cfg.api_key or get_first_env("V3_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")
        base_url = _normalize_openai_compatible_base_url(
            self.cfg.base_url or get_first_env("V3_GEMINI_BASE_URL", "GEMINI_BASE_URL")
        )

        if base_url:
            from openai import OpenAI

            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self._client_mode = "openai_compatible"
        else:
            from google import genai

            self.client = genai.Client(api_key=api_key)
            self._client_mode = "google_genai"

    def generate(self, prompt: str) -> str:


        if self._client_mode == "openai_compatible":
            response = self.client.chat.completions.create(
                model=self.cfg.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.cfg.temperature,
                max_tokens=self.cfg.max_tokens,
            )
            return response.choices[0].message.content or ""

        config: object
        try:
            from google.genai import types as genai_types

            config = genai_types.GenerateContentConfig(
                temperature=self.cfg.temperature,
                max_output_tokens=self.cfg.max_tokens,
            )
        except ImportError:
            config = {
                "temperature": self.cfg.temperature,
                "max_output_tokens": self.cfg.max_tokens,
            }
        response = self.client.models.generate_content(
            model=self.cfg.model,
            contents=prompt,
            config=config,
        )
        return getattr(response, "text", "") or ""


def _normalize_openai_compatible_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    if parsed.scheme and parsed.netloc and parsed.path in {"", "/"}:
        return base_url.rstrip("/") + "/v1"
    return base_url
