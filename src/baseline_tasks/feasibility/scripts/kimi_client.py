"""Kimi Code OpenAI-compatible chat completion client.

Endpoint: https://api.kimi.com/coding/v1/chat/completions
Model:    kimi-for-coding (default; override via env KIMI_MODEL or argument)

Auth precedence (first non-empty wins):
    1. environment variable  KIMI_API_KEY
    2. <repo-root>/.env line KIMI_API_KEY=...
    3. <repo-root>/kimiapi.txt (single line containing the key)

Public surface:
    - chat(messages, *, temperature=0.2, max_tokens=2000, model=None) -> str
    - load_api_key() -> str | None    (thin helper for scripts that want to fail early)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

API_URL = "https://api.kimi.com/coding/v1/chat/completions"
DEFAULT_MODEL = "kimi-for-coding"
DEFAULT_TIMEOUT_SEC = 300
# Kimi For Coding gates access by User-Agent: only approved coding-agent IDs
# (kimi-cli, claude-cli, kilo-code, ...) are accepted. These scripts run as
# part of a Claude Code workflow, so we identify accordingly. Override via
# env KIMI_USER_AGENT if running from a different agent context.
DEFAULT_USER_AGENT = "claude-cli/2.0.0 (feasibility-test)"


def _project_root() -> Path:
    # .../src/baseline_tasks/feasibility/scripts/kimi_client.py -> repo root
    return Path(__file__).resolve().parents[4]


def _read_env_file(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'") or None
    return None


def load_api_key() -> str | None:
    """Return Kimi API key, or None if not configured anywhere."""
    val = os.environ.get("KIMI_API_KEY")
    if val and val.strip():
        return val.strip()
    root = _project_root()
    val = _read_env_file(root / ".env", "KIMI_API_KEY")
    if val:
        return val
    fallback = root / "kimiapi.txt"
    if fallback.is_file():
        try:
            text = fallback.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text:
            return text.splitlines()[0].strip()
    return None


def chat(
    messages: Iterable[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int = 4000,
    model: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    retries: int = 3,
    stream: bool = True,
) -> str:
    """Call Kimi chat completion. Returns the assistant text content.

    Note: kimi-for-coding is a reasoning model. The visible answer comes after
    a hidden reasoning phase that consumes tokens. Set `max_tokens` generously
    (>= 4000 for short answers, 8000+ for code generation) so the model has
    room to finish reasoning AND produce the answer. If `finish_reason` is
    "length", the answer was truncated mid-reasoning and `content` may be ''.

    Streaming is on by default. Long-running prompts (e.g. complex code synth)
    can otherwise hit nginx 504 gateway timeouts on the non-streaming endpoint.

    Raises RuntimeError on any failure. `messages` is the OpenAI-style
    [{"role": "system"|"user"|"assistant", "content": "..."}, ...] list.
    """
    key = load_api_key()
    if not key:
        raise RuntimeError(
            "Kimi API key not found. Set KIMI_API_KEY env var, add it to .env, "
            "or place it in kimiapi.txt at repo root."
        )

    model_name = (model or os.environ.get("KIMI_MODEL") or DEFAULT_MODEL).strip()

    body = {
        "model": model_name,
        "messages": list(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": bool(stream),
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    last_err: Exception | None = None
    user_agent = (os.environ.get("KIMI_USER_AGENT") or DEFAULT_USER_AGENT).strip()
    for attempt in range(max(1, retries + 1)):
        req = urllib.request.Request(
            API_URL,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": user_agent,
                "Accept": "text/event-stream" if stream else "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if stream:
                    text, finish = _read_stream(resp)
                else:
                    payload = json.loads(resp.read().decode("utf-8"))
                    choice = payload["choices"][0]
                    text = choice["message"]["content"]
                    finish = choice.get("finish_reason")
            if not isinstance(text, str):
                raise RuntimeError(f"Unexpected content type: {type(text)!r}")
            if finish == "length" and not text.strip():
                # Reasoning model ran out of tokens before producing the answer.
                raise RuntimeError(
                    "Empty content with finish_reason=length: "
                    "kimi-for-coding ran out of tokens during reasoning. "
                    f"Increase max_tokens (currently {max_tokens})."
                )
            return text
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            last_err = RuntimeError(f"HTTP {e.code}: {err_body[:1000]}")
            # Retry on transient gateway/server errors (502/503/504/520/524).
            if e.code not in (502, 503, 504, 520, 524, 408, 429):
                raise last_err
        except urllib.error.URLError as e:
            last_err = RuntimeError(f"URL error: {e}")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            last_err = RuntimeError(f"Unexpected response shape: {e}")
        if attempt < retries:
            time.sleep(5 + attempt * 5)
    assert last_err is not None
    raise last_err


def _read_stream(resp) -> tuple[str, str | None]:
    """Parse OpenAI-compatible SSE chunks; return (content, finish_reason)."""
    parts: list[str] = []
    finish: str | None = None
    for raw in resp:
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        body = line[len("data:"):].strip()
        if body == "[DONE]":
            break
        try:
            chunk = json.loads(body)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content")
        if isinstance(piece, str) and piece:
            parts.append(piece)
        fr = choices[0].get("finish_reason")
        if fr:
            finish = fr
    return "".join(parts), finish
