#!/usr/bin/env python3
"""
One-shot chat completion via OfoxAI OpenAI-compatible API (no key in repo).

API key (pick one):
  - Project root `.env`: lines `OFOX_API_KEY=...` or `OFOXAI_API_KEY=...` (auto-loaded; not committed)
  - Or set the same variables in the shell environment (takes precedence over .env)

Model name is chosen in this file (DEFAULT_MODEL) or via `--model`; it is NOT read from .env.

Usage:
  python invoke_ofox_once.py --task-id t0_plus1
  python invoke_ofox_once.py --mbe-task mbe_nft_marketplace
  python invoke_ofox_once.py --task-id t0_plus1 --model anthropic/claude-3-5-sonnet-latest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.ofox.ai/v1/chat/completions"

# Edit this default, or pass --model on the command line (OFOX does not read model from .env).
DEFAULT_MODEL = "openai/gpt-4o-mini"

CODE_FILES = {
    "t0_plus1": "prove.move",
    "t1_aborts": "prove.move",
    "t2_hello_blockchain": "hello_blockchain_test.move",
}

# move-by-examples baseline: buggy source read from E:\ package (see apply_and_check_mbe.py)
MBE_TASKS = {
    "mbe_nft_marketplace": Path(r"E:\src\move-poc\baseline\mbe_nft_marketplace\sources\marketplace.move"),
    "mbe_fa_vesting": Path(r"E:\src\move-poc\baseline\mbe_fa_vesting\tests\vesting_tests.move"),
    "mbe_advanced_todo": Path(r"E:\src\move-poc\baseline\mbe_advanced_todo\sources\advanced_todo_list.move"),
}


def project_root() -> Path:
    # .../src/baseline_tasks/scripts/invoke_ofox_once.py -> repo root
    return Path(__file__).resolve().parent.parent.parent.parent


def load_api_key_from_dotenv() -> None:
    """Set OFOX_API_KEY / OFOXAI_API_KEY from repo .env if not already in the environment."""
    env_path = project_root() / ".env"
    if not env_path.is_file():
        return
    allowed_keys = frozenset({"OFOX_API_KEY", "OFOXAI_API_KEY"})
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key not in allowed_keys:
            continue
        if key in os.environ and os.environ[key].strip():
            continue
        if val:
            os.environ[key] = val


def main() -> int:
    load_api_key_from_dotenv()

    parser = argparse.ArgumentParser(description="Call OFOX chat completions for a baseline task.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--task-id",
        choices=list(CODE_FILES.keys()),
        help="Small baseline (t0/t1/t2): code copy lives under baseline_tasks/<id>/",
    )
    g.add_argument(
        "--mbe-task",
        choices=list(MBE_TASKS.keys()),
        help="move-by-examples baseline: code read from E:\\\\src\\\\move-poc\\\\baseline\\\\...",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OFOX model id (default: {DEFAULT_MODEL!r})",
    )
    args = parser.parse_args()

    key = os.environ.get("OFOX_API_KEY") or os.environ.get("OFOXAI_API_KEY")
    if not key or not key.strip():
        print(
            "Missing API key: add OFOX_API_KEY to project .env or set it in the environment.",
            file=sys.stderr,
        )
        return 1

    model = args.model.strip()

    scripts_dir = Path(__file__).resolve().parent
    baseline_tasks_root = scripts_dir.parent

    if args.mbe_task:
        task_slug = args.mbe_task
        code_path = MBE_TASKS[args.mbe_task]
    else:
        task_slug = args.task_id
        code_name = CODE_FILES[args.task_id]
        code_path = baseline_tasks_root / args.task_id / code_name

    task_dir = baseline_tasks_root / task_slug
    if not task_dir.is_dir():
        print(f"Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    prompt_path = task_dir / "PROMPT.txt"
    fail_path = task_dir / "fail.log"

    if not prompt_path.is_file():
        print(f"Missing {prompt_path}", file=sys.stderr)
        return 1
    if not code_path.is_file():
        print(f"Missing {code_path}", file=sys.stderr)
        return 1

    prompt_text = prompt_path.read_text(encoding="utf-8")
    fail_text = fail_path.read_text(encoding="utf-8") if fail_path.is_file() else "(no fail.log)"
    code_text = code_path.read_text(encoding="utf-8")

    user_body = f"""{prompt_text}

--- fail.log ---
{fail_text}

--- source file ---
{code_text}
"""

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Follow the user instructions exactly. Output Move code in a markdown fence when asked.",
            },
            {"role": "user", "content": user_body},
        ],
    }

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key.strip()}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )

    try:
        timeout = 300 if args.mbe_task else 120
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1

    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(f"Unexpected response: {json.dumps(payload, ensure_ascii=False)[:2000]}", file=sys.stderr)
        return 1

    out_file = task_dir / "model_response.txt"
    out_file.write_text(text, encoding="utf-8")
    print(f"model={model!r}")
    print(f"Wrote {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
