"""Extract a function body from an LLM response.

Two markers are accepted, in priority order:
  1. <<<BODY ... BODY>>>   (preferred; the prompts request this)
  2. The first ```move ... ```  fenced block (legacy fallback)

If the LLM returned an entire function ("public fun foo(...) { BODY }"), we
strip the wrapping signature so the result is just the inside-of-braces text.
"""
from __future__ import annotations

import re

_BODY_MARKER_RE = re.compile(r"<<<BODY\s*\n?(.*?)\n?BODY>>>", re.DOTALL)
_MOVE_FENCE_RE = re.compile(r"```\s*move\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_GENERIC_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.DOTALL)
_FUN_OPEN_RE = re.compile(
    r"(?:public(?:\s*\(\s*friend\s*\))?\s+|public\s+entry\s+|entry\s+)?"
    r"fun\s+\w+[^{]*\{",
    re.DOTALL,
)


def extract_body(response: str) -> str | None:
    """Return the function body (no surrounding braces or signature), or None
    if no candidate code block is found. Whitespace is preserved exactly so
    the caller can splice it verbatim."""
    if not response:
        return None

    m = _BODY_MARKER_RE.search(response)
    if m is not None:
        return m.group(1).rstrip("\n")

    m = _MOVE_FENCE_RE.search(response)
    if m is None:
        m = _GENERIC_FENCE_RE.search(response)
    if m is None:
        return None
    block = m.group(1)

    # If the fenced block contains a full function, strip the signature/braces.
    fn_match = _FUN_OPEN_RE.search(block)
    if fn_match:
        depth = 0
        i = fn_match.end() - 1  # at the opening '{'
        body_start = -1
        for j, ch in enumerate(block[i:], start=i):
            if ch == "{":
                if depth == 0:
                    body_start = j + 1
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return block[body_start:j].rstrip("\n")
        return None

    return block.rstrip("\n")
