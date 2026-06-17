"""Small provider switch for Phase 1 LLM calls."""
from __future__ import annotations

import os
from typing import Iterable

DEFAULT_PROVIDER = "kimi"


def normalize_provider(provider: str | None = None) -> str:
    return (provider or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()


def chat(
    messages: Iterable[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4000,
    timeout_sec: int = 300,
    retries: int = 3,
    stream: bool = True,
) -> str:
    return chat_with_metadata(
        messages,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        retries=retries,
        stream=stream,
    )["text"]


def chat_with_metadata(
    messages: Iterable[dict],
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4000,
    timeout_sec: int = 300,
    retries: int = 3,
    stream: bool = True,
) -> dict:
    provider_name = normalize_provider(provider)
    if provider_name == "kimi":
        import kimi_client

        meta = kimi_client.chat_with_metadata(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
            retries=retries,
            stream=stream,
        )
        meta["provider"] = provider_name
        return meta
    if provider_name == "deepseek":
        import deepseek_client

        meta = deepseek_client.chat_with_metadata(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
            retries=retries,
            stream=stream,
        )
        meta["provider"] = provider_name
        return meta
    raise ValueError(f"Unknown provider: {provider_name!r}. Expected 'kimi' or 'deepseek'.")
