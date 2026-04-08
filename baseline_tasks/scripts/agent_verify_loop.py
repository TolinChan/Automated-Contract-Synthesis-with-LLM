#!/usr/bin/env python3
"""
Multi-round Spec -> Agent (OFOX API) -> Verifier (aptos move prove|test) -> feedback loop.

Usage:
  python agent_verify_loop.py --task t2_hello_blockchain
  python agent_verify_loop.py --task mbe_nft_marketplace --max-rounds 8 --timeout-sec 400
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from invoke_ofox_once import API_URL, DEFAULT_MODEL, load_api_key_from_dotenv
from loop_tasks import LOOP_TASKS, LoopTask, get_loop_task
from move_fence import ensure_trailing_newline, extract_first_move_fence

_DEFAULT_BOOGIE = Path(r"C:\Users\96247\.dotnet\tools\boogie.exe")
_DEFAULT_Z3 = Path(r"E:\tools\z3_extract\z3-4.13.0-x64-win\bin\z3.exe")

SYSTEM_PROMPT = """Follow the user instructions exactly. Output Move code in a markdown fence when asked.
You may receive multiple rounds of feedback from a verifier (aptos move prove or aptos move test). Each time, output the complete replacement file in a single ```move fenced block — no auto-fix is applied; the file must compile and pass verification."""


def build_initial_user_message(cfg: LoopTask) -> str:
    meta = cfg.meta_dir()
    prompt_path = meta / "PROMPT.txt"
    fail_path = meta / "fail.log"
    target = cfg.target_path()
    prompt_text = prompt_path.read_text(encoding="utf-8")
    fail_text = fail_path.read_text(encoding="utf-8") if fail_path.is_file() else "(no fail.log)"
    code_text = target.read_text(encoding="utf-8")
    return f"""{prompt_text}

--- fail.log ---
{fail_text}

--- source file ---
{code_text}
"""


def prover_env() -> dict[str, str]:
    env = os.environ.copy()
    if not env.get("BOOGIE_EXE") and _DEFAULT_BOOGIE.is_file():
        env["BOOGIE_EXE"] = str(_DEFAULT_BOOGIE)
    if not env.get("Z3_EXE") and _DEFAULT_Z3.is_file():
        env["Z3_EXE"] = str(_DEFAULT_Z3)
    return env


def run_verifier(cfg: LoopTask) -> tuple[int, str]:
    if cfg.verify == "test":
        cmd = ["aptos", "move", "test", "--package-dir", str(cfg.package_dir)]
        env = os.environ.copy()
    else:
        cmd = ["aptos", "move", "prove", "--package-dir", str(cfg.package_dir)]
        env = prover_env()
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    parts: list[str] = []
    if proc.stdout:
        parts.append(proc.stdout)
    if proc.stderr:
        parts.append(proc.stderr)
    return proc.returncode, "\n".join(parts).strip()


def truncate(s: str, max_chars: int) -> str:
    if max_chars <= 0 or len(s) <= max_chars:
        return s
    half = max_chars // 2
    return s[:half] + "\n\n...[truncated]...\n\n" + s[-half:]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def maybe_backup_target(target: Path) -> Path | None:
    bak = target.parent / (target.name + ".buggy_before_loop.bak")
    if bak.is_file():
        return None
    bak.write_bytes(target.read_bytes())
    return bak


def chat_completion(api_url: str, key: str, model: str, messages: list, timeout: int) -> str:
    body = {"model": model, "messages": messages}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key.strip()}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return str(payload["choices"][0]["message"]["content"])


def main() -> int:
    load_api_key_from_dotenv()
    parser = argparse.ArgumentParser(description="Multi-round Spec-Agent-Verifier loop via OFOX API.")
    parser.add_argument("--task", required=True, choices=sorted(LOOP_TASKS.keys()))
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=None,
        help="HTTP timeout per API call (default: 300 for mbe_*, else 120)",
    )
    parser.add_argument(
        "--max-feedback-chars",
        type=int,
        default=24000,
        help="Max verifier output chars sent back to the model (0 = no limit)",
    )
    parser.add_argument("--api-url", default=API_URL)
    args = parser.parse_args()

    key = os.environ.get("OFOX_API_KEY") or os.environ.get("OFOXAI_API_KEY")
    if not key or not key.strip():
        print(
            "Missing API key: add OFOX_API_KEY to project .env or set it in the environment.",
            file=sys.stderr,
        )
        return 1

    cfg = get_loop_task(args.task)
    meta = cfg.meta_dir()
    if not meta.is_dir():
        print(f"Task directory not found: {meta}", file=sys.stderr)
        return 1
    prompt_path = meta / "PROMPT.txt"
    if not prompt_path.is_file():
        print(f"Missing {prompt_path}", file=sys.stderr)
        return 1
    if not cfg.package_dir.is_dir():
        print(f"Package directory not found: {cfg.package_dir}", file=sys.stderr)
        return 1
    target = cfg.target_path()
    if not target.is_file():
        print(f"Target file not found: {target}", file=sys.stderr)
        return 1

    if args.timeout_sec is not None:
        timeout = args.timeout_sec
    else:
        timeout = 300 if args.task.startswith("mbe_") else 120

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = meta / "loop_runs" / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    initial_digest = sha256_file(target)
    backup_path = maybe_backup_target(target)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_initial_user_message(cfg)},
    ]

    model = args.model.strip()
    summary: dict = {
        "task": args.task,
        "model": model,
        "success": False,
        "rounds_used": 0,
        "package_dir": str(cfg.package_dir),
        "relative_file": cfg.relative_file,
        "verify": cfg.verify,
        "run_dir": str(run_dir),
        "initial_target_sha256": initial_digest,
        "backup_created": str(backup_path) if backup_path else None,
    }

    messages_jsonl = run_dir / "messages.jsonl"

    def append_jsonl(obj: dict) -> None:
        with messages_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    for round_idx in range(1, args.max_rounds + 1):
        append_jsonl({"event": "request_round_start", "round": round_idx, "num_messages": len(messages)})
        try:
            assistant_text = chat_completion(args.api_url, key, model, messages, timeout=timeout)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
            summary["error"] = f"http_{e.code}"
            (run_dir / "summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return 1
        except (urllib.error.URLError, KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            print(f"Request or parse error: {e}", file=sys.stderr)
            summary["error"] = str(e)
            (run_dir / "summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return 1

        (run_dir / f"round_{round_idx:02d}_assistant.txt").write_text(assistant_text, encoding="utf-8")
        messages.append({"role": "assistant", "content": assistant_text})
        append_jsonl(
            {
                "event": "assistant",
                "round": round_idx,
                "content_preview": assistant_text[:500],
            }
        )

        body = extract_first_move_fence(assistant_text)
        if body is None:
            feedback = (
                f"Round {round_idx}: Your last message had no parseable ```move fenced block. "
                "Reply with the complete file in one ```move code block."
            )
            messages.append({"role": "user", "content": feedback})
            append_jsonl({"event": "parse_miss", "round": round_idx})
            summary["rounds_used"] = round_idx
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(ensure_trailing_newline(body), encoding="utf-8")

        code, verifier_out = run_verifier(cfg)
        verifier_out = truncate(verifier_out, args.max_feedback_chars)
        (run_dir / f"round_{round_idx:02d}_verifier.log").write_text(
            f"exit_code={code}\n\n{verifier_out}",
            encoding="utf-8",
        )
        append_jsonl({"event": "verifier", "round": round_idx, "exit_code": code})

        if code == 0:
            summary["success"] = True
            summary["rounds_to_success"] = round_idx
            summary["rounds_used"] = round_idx
            summary["final_target_sha256"] = sha256_file(target)
            (run_dir / "summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"OK task={args.task!r} model={model!r} rounds={round_idx} run_dir={run_dir}")
            return 0

        feedback = (
            f"Round {round_idx}: verification failed (exit code {code}). "
            "Fix the code and output the full file again in a single ```move fenced block.\n\n"
            f"--- aptos stdout/stderr ---\n{verifier_out}"
        )
        messages.append({"role": "user", "content": feedback})
        summary["rounds_used"] = round_idx

    summary["success"] = False
    summary["reason"] = "max_rounds_exhausted"
    if target.is_file():
        summary["final_target_sha256"] = sha256_file(target)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"FAIL task={args.task!r} model={model!r} exhausted {args.max_rounds} rounds run_dir={run_dir}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
