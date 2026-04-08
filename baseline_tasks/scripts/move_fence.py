"""Extract Move source from markdown fenced blocks in model output."""
from __future__ import annotations

import re


def extract_first_move_fence(text: str) -> str | None:
    """Return inner content of the first ```move ... ``` block (case-insensitive fence tag)."""
    m = re.search(r"```\s*move\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip("\n")
    m2 = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m2:
        return m2.group(1).strip("\n")
    return None


def ensure_trailing_newline(body: str) -> str:
    return body + ("\n" if not body.endswith("\n") else "")
