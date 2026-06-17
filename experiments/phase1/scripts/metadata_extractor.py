"""Extract metadata for one feasibility-test function from aptos-framework.

For each function id (defined in functions.yaml), produces:

    feasibility/functions/<id>/
        spec.txt                # spec <fn> { ... } block extracted verbatim
        signature.txt           # function signature line(s), no body
        reference_body.txt      # ground-truth function body (oracle, not given to LLM)
        module_context.txt      # imports + constants + structs + sibling fn signatures
        meta.json               # source paths, line ranges, complexity tag

We deliberately do NOT extract referenced schemas, pragmas, or ghost-var
declarations recursively. The Zero-shot prompt sees only the spec block; +Ctx adds the
module_context. If a function's spec includes a schema (e.g., `include
InitializeInternalSchema<CoinType>`), the LLM either infers it from context
(+Ctx) or fails (Zero-shot) — that failure is itself a useful data point.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_SRC = Path(r"E:\src\aptos-framework\aptos-framework\sources")
FEASIBILITY_DIR = REPO_ROOT / "experiments" / "phase1"


@dataclass(frozen=True)
class FunctionSpec:
    id: str
    module: str
    function: str
    source_file: str
    spec_file: str
    complexity: str


def load_registry() -> list[FunctionSpec]:
    """Parse functions.yaml without a YAML library (single-file heuristic)."""
    text = (FEASIBILITY_DIR / "functions.yaml").read_text(encoding="utf-8")
    items: list[FunctionSpec] = []
    cur: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("functions:"):
            continue
        if line.startswith("  - id:"):
            if cur:
                items.append(_to_spec(cur))
                cur = {}
            cur["id"] = line.split(":", 1)[1].strip()
            continue
        m = re.match(r"^    ([a-z_]+):\s*(.+?)\s*$", line)
        if m:
            key, val = m.group(1), m.group(2)
            cur[key] = val.strip().strip('"')
    if cur:
        items.append(_to_spec(cur))
    return items


def _to_spec(d: dict[str, str]) -> FunctionSpec:
    return FunctionSpec(
        id=d["id"],
        module=d["module"],
        function=d["function"],
        source_file=d["source_file"],
        spec_file=d["spec_file"],
        complexity=d.get("complexity", "unknown"),
    )


def find_block_after(text: str, start_idx: int) -> tuple[int, int]:
    """Given text and index pointing at-or-before an opening '{', return
    (open_pos, close_pos) such that text[open_pos] == '{' and text[close_pos]
    == '}' is the matching closer. Strings and line comments are tracked so
    that braces inside them don't confuse the matcher."""
    n = len(text)
    i = start_idx
    while i < n and text[i] != "{":
        i += 1
    if i >= n:
        raise ValueError("opening { not found after start_idx")
    depth = 0
    open_pos = i
    while i < n:
        c = text[i]
        # line comment
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        # block comment
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        # double-quoted string (Move uses these for byte strings; rare in framework src)
        if c == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                elif text[j] == '"':
                    j += 1
                    break
                else:
                    j += 1
            i = j
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return open_pos, i
        i += 1
    raise ValueError("unbalanced braces while scanning forward from index")


def extract_spec_block(spec_text: str, fn_name: str) -> str:
    """Return `spec <fn_name> { ... }` (or with parameter list) from the spec
    file, including the leading 'spec' keyword and trailing close-brace."""
    pat = re.compile(rf"^\s*spec\s+{re.escape(fn_name)}\b[^{{]*", re.MULTILINE)
    m = pat.search(spec_text)
    if m is None:
        raise ValueError(f"spec block for {fn_name!r} not found")
    open_pos, close_pos = find_block_after(spec_text, m.end())
    block_start = m.start()
    return spec_text[block_start : close_pos + 1]


def extract_function(text: str, fn_name: str) -> tuple[str, str, tuple[int, int]]:
    """Return (signature, body, (signature_line, end_line)). Signature is
    everything from the function-decl keyword(s) up to and including the line
    that opens the body block. Body is the content between the matched braces
    (no surrounding braces). The returned line range is 1-based, inclusive."""
    pat = re.compile(
        rf"^[ \t]*(?:public(?:\s*\(\s*friend\s*\))?\s+|public\s+entry\s+|entry\s+)?fun\s+{re.escape(fn_name)}\b",
        re.MULTILINE,
    )
    m = pat.search(text)
    if m is None:
        raise ValueError(f"function {fn_name!r} not found")
    sig_start = m.start()
    open_pos, close_pos = find_block_after(text, m.end())
    signature = text[sig_start:open_pos].rstrip() + " {"
    body = text[open_pos + 1 : close_pos]
    start_line = text.count("\n", 0, sig_start) + 1
    end_line = text.count("\n", 0, close_pos) + 1
    return signature, body, (start_line, end_line)


_USE_RE = re.compile(r"^\s*use\s+[^;]+;", re.MULTILINE)
_CONST_RE = re.compile(r"^\s*const\s+[A-Z_][A-Z0-9_]*\s*:\s*[^=]+=\s*[^;]+;", re.MULTILINE)
_FRIEND_RE = re.compile(r"^\s*friend\s+[^;]+;", re.MULTILINE)


def extract_module_block(text: str) -> tuple[str, int, int]:
    """Find `module ... { ... }` and return (module_body, body_start, body_end)
    where module_body excludes the surrounding braces."""
    m = re.search(r"^\s*module\s+[^{]+", text, re.MULTILINE)
    if m is None:
        raise ValueError("module declaration not found")
    open_pos, close_pos = find_block_after(text, m.end())
    return text[open_pos + 1 : close_pos], open_pos + 1, close_pos


def extract_struct_decls(module_body: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(
        r"^\s*(?:public\s+)?struct\s+\w+(?:<[^>]+>)?(?:\s+has\s+[^{]+)?",
        module_body,
        re.MULTILINE,
    ):
        try:
            open_pos, close_pos = find_block_after(module_body, m.end())
        except ValueError:
            # No body? (declared with semicolon — shouldn't happen for Move structs but be safe)
            continue
        out.append(module_body[m.start() : close_pos + 1].strip())
    return out


def extract_sibling_signatures(module_body: str, target_fn: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(
        r"^[ \t]*(?:#\[[^\]]+\]\s*)*"  # optional attribute lines
        r"(?:public(?:\s*\(\s*friend\s*\))?\s+|public\s+entry\s+|entry\s+)?"
        r"fun\s+(\w+)",
        module_body,
        re.MULTILINE,
    ):
        name = m.group(1)
        if name == target_fn:
            continue
        try:
            open_pos, _ = find_block_after(module_body, m.end())
        except ValueError:
            continue
        out.append(module_body[m.start() : open_pos].rstrip() + ";")
    return out


def build_module_context(source_text: str, target_fn: str, spec_text: str | None = None) -> str:
    module_body, _, _ = extract_module_block(source_text)
    parts: list[str] = []

    uses = [m.group(0).strip() for m in _USE_RE.finditer(module_body)]
    if uses:
        parts.append("// === imports ===")
        parts.extend(uses)

    friends = [m.group(0).strip() for m in _FRIEND_RE.finditer(module_body)]
    if friends:
        parts.append("\n// === friends ===")
        parts.extend(friends)

    consts = [m.group(0).strip() for m in _CONST_RE.finditer(module_body)]
    if consts:
        parts.append("\n// === constants ===")
        parts.extend(consts)

    structs = extract_struct_decls(module_body)
    if structs:
        parts.append("\n// === structs ===")
        parts.extend(structs)

    siblings = extract_sibling_signatures(module_body, target_fn)
    if siblings:
        parts.append("\n// === sibling function signatures (bodies omitted) ===")
        parts.extend(siblings)

    if spec_text:
        spec_decls = extract_spec_module_level(spec_text)
        if spec_decls:
            parts.append("\n// === module-level spec declarations (from .spec.move) ===")
            parts.extend(spec_decls)

    return "\n".join(parts) + "\n"


_GLOBAL_GHOST_RE = re.compile(
    r"^\s*global\s+\w+\s*:\s*[^;]+;",
    re.MULTILINE,
)


def extract_spec_module_level(spec_text: str) -> list[str]:
    """Pull module-level spec declarations out of a .spec.move file. We focus
    on `global ghost_xxx: T;` ghost-var declarations because the codegen LLM
    needs to know which module-level ghost vars exist in order to update them
    via `spec { update ghost_xxx = ...; };` from within the function body.

    We do NOT pull `schema` blocks (they would balloon the context); siblings'
    spec blocks; or pragmas. Only the `global` lines, kept in source order."""
    return [m.group(0).strip() for m in _GLOBAL_GHOST_RE.finditer(spec_text)]


def main() -> int:
    p = argparse.ArgumentParser(description="Extract spec/signature/context for feasibility-test functions.")
    p.add_argument("--id", help="Single function id; omit to process all functions in the registry.")
    args = p.parse_args()

    registry = load_registry()
    selected = [f for f in registry if args.id is None or f.id == args.id]
    if not selected:
        print(f"No matching function id: {args.id!r}", file=sys.stderr)
        return 1

    for fn in selected:
        src = (FRAMEWORK_SRC / fn.source_file).read_text(encoding="utf-8")
        spec = (FRAMEWORK_SRC / fn.spec_file).read_text(encoding="utf-8")

        spec_block = extract_spec_block(spec, fn.function)
        signature, body, (start_line, end_line) = extract_function(src, fn.function)
        context = build_module_context(src, fn.function, spec_text=spec)

        out_dir = FEASIBILITY_DIR / "functions" / fn.id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "spec.txt").write_text(spec_block + "\n", encoding="utf-8")
        (out_dir / "signature.txt").write_text(signature + "\n", encoding="utf-8")
        (out_dir / "reference_body.txt").write_text(body, encoding="utf-8")
        (out_dir / "module_context.txt").write_text(context, encoding="utf-8")
        meta = {
            "id": fn.id,
            "module": fn.module,
            "function": fn.function,
            "source_file": fn.source_file,
            "spec_file": fn.spec_file,
            "complexity": fn.complexity,
            "source_line_range": [start_line, end_line],
            "body_chars": len(body),
            "body_lines": body.count("\n") + 1,
            "spec_chars": len(spec_block),
            "module_context_chars": len(context),
        }
        (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        print(
            f"{fn.id}: spec={len(spec_block)}c body={len(body)}c "
            f"context={len(context)}c lines={start_line}-{end_line}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
