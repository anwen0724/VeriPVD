

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import urlparse

from llm.env import get_first_env, load_project_env


ProviderName = Literal["gpt", "claude", "deepseek", "qwen", "gemini"]


@dataclass
class LangChainModelConfig:


    provider: ProviderName
    model: str
    temperature: float = 0.2
    max_tokens: int = 8192
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    request_timeout: float | None = 600


def create_chat_model(cfg: LangChainModelConfig):


    load_project_env()

    if cfg.provider == "gpt":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=cfg.api_key or get_first_env("V3_OPENAI_API_KEY", "OPENAI_API_KEY"),
            base_url=cfg.base_url or get_first_env("V3_OPENAI_BASE_URL", "OPENAI_BASE_URL"),
            timeout=cfg.request_timeout,
        )

    if cfg.provider == "claude":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=cfg.api_key or get_first_env("V3_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
            base_url=cfg.base_url or get_first_env("V3_ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL"),
            timeout=cfg.request_timeout,
        )

    if cfg.provider == "deepseek":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=cfg.api_key or get_first_env("V3_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
            base_url=cfg.base_url or get_first_env("V3_DEEPSEEK_BASE_URL", "DEEPSEEK_BASE_URL"),
            timeout=cfg.request_timeout,
        )

    if cfg.provider == "qwen":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=cfg.api_key or get_first_env("V3_QWEN_API_KEY", "QWEN_API_KEY"),
            base_url=cfg.base_url or get_first_env("V3_QWEN_BASE_URL", "QWEN_BASE_URL"),
            timeout=cfg.request_timeout,
        )

    if cfg.provider == "gemini":
        gemini_base_url = _normalize_openai_compatible_base_url(
            cfg.base_url or get_first_env("V3_GEMINI_BASE_URL", "GEMINI_BASE_URL")
        )
        gemini_api_key = cfg.api_key or get_first_env("V3_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")
        if gemini_base_url:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=gemini_api_key,
                base_url=gemini_base_url,
                timeout=cfg.request_timeout,
            )

        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=cfg.model,
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_tokens,
            api_key=gemini_api_key,
            timeout=cfg.request_timeout,
        )

    raise ValueError(f"Unsupported provider: {cfg.provider}")


def _normalize_openai_compatible_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    if parsed.scheme and parsed.netloc and parsed.path in {"", "/"}:
        return base_url.rstrip("/") + "/v1"
    return base_url
