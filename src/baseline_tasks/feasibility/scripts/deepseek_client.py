"""DeepSeek OpenAI-compatible chat completion client.

Endpoint: https://api.deepseek.com/chat/completions
Model:    deepseek-v4-pro (default; override via env DEEPSEEK_MODEL or argument)

Auth precedence (first non-empty wins):
    1. environment variable  DEEPSEEK_API_KEY
    2. <repo-root>/.env line DEEPSEEK_API_KEY=...
    3. <repo-root>/deepseekapi.txt (single line containing the key)

Public surface mirrors kimi_client.py:
    - chat(messages, *, temperature=0.2, max_tokens=4000, model=None) -> str
    - load_api_key() -> str | None
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_TIMEOUT_SEC = 300
DEFAULT_USER_AGENT = "codex-cli/1.0.0 (feasibility-test)"


def _project_root() -> Path:
    # .../src/baseline_tasks/feasibility/scripts/deepseek_client.py -> repo root
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
    """Return DeepSeek API key, or None if not configured anywhere."""
    val = os.environ.get("DEEPSEEK_API_KEY")
    if val and val.strip():
        return val.strip()
    root = _project_root()
    val = _read_env_file(root / ".env", "DEEPSEEK_API_KEY")
    if val:
        return val
    fallback = root / "deepseekapi.txt"
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
    """Call DeepSeek chat completion. Returns the assistant text content."""
    key = load_api_key()
    if not key:
        raise RuntimeError(
            "DeepSeek API key not found. Set DEEPSEEK_API_KEY env var, add it to .env, "
            "or place it in deepseekapi.txt at repo root."
        )

    model_name = (model or os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL).strip()
    body = {
        "model": model_name,
        "messages": list(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": bool(stream),
    }

    thinking = os.environ.get("DEEPSEEK_THINKING")
    if thinking:
        mode = thinking.strip().lower()
        if mode in ("enabled", "disabled"):
            body["thinking"] = {"type": mode}
    effort = os.environ.get("DEEPSEEK_REASONING_EFFORT")
    if effort:
        body["reasoning_effort"] = effort.strip()

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    last_err: Exception | None = None
    user_agent = (os.environ.get("DEEPSEEK_USER_AGENT") or DEFAULT_USER_AGENT).strip()
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
                raise RuntimeError(
                    "Empty content with finish_reason=length: "
                    f"increase max_tokens (currently {max_tokens})."
                )
            return text
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            last_err = RuntimeError(f"HTTP {e.code}: {err_body[:1000]}")
            if e.code not in (408, 429, 500, 502, 503, 504, 520, 524):
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
        if not line or line.startswith(":") or not line.startswith("data:"):
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
