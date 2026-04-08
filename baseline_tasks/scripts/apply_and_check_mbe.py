#!/usr/bin/env python3
"""
Mechanically apply the first ```move fenced block from an agent response file
to a configured MBE task file, then run `aptos move test`. No auto-fix of syntax.

Usage:
  python apply_and_check_mbe.py --task mbe_nft_marketplace --response path/to/model_response.txt
  python apply_and_check_mbe.py --task mbe_fa_vesting   # default: <task_dir>/model_response.txt
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from move_fence import ensure_trailing_newline, extract_first_move_fence

# Repo: baseline_tasks/scripts -> project root for .env (optional)
SCRIPTS_DIR = Path(__file__).resolve().parent
BASELINE_TASKS = SCRIPTS_DIR.parent

MBE_TASKS: dict[str, dict[str, str]] = {
    "mbe_nft_marketplace": {
        "package_dir": r"E:\src\move-poc\baseline\mbe_nft_marketplace",
        "relative_file": "sources/marketplace.move",
    },
    "mbe_fa_vesting": {
        "package_dir": r"E:\src\move-poc\baseline\mbe_fa_vesting",
        "relative_file": "tests/vesting_tests.move",
    },
    "mbe_advanced_todo": {
        "package_dir": r"E:\src\move-poc\baseline\mbe_advanced_todo",
        "relative_file": "sources/advanced_todo_list.move",
    },
}


def main() -> int:
    p = argparse.ArgumentParser(description="Apply agent Move output and run aptos move test.")
    p.add_argument("--task", required=True, choices=list(MBE_TASKS.keys()))
    p.add_argument(
        "--response",
        default=None,
        help="File containing agent output (default: <baseline_tasks>/<task>/model_response.txt)",
    )
    args = p.parse_args()

    cfg = MBE_TASKS[args.task]
    pkg = Path(cfg["package_dir"])
    rel = Path(cfg["relative_file"])
    target = pkg / rel

    task_meta = BASELINE_TASKS / args.task
    resp_path = Path(args.response) if args.response else (task_meta / "model_response.txt")
    if not resp_path.is_file():
        print(f"Missing response file: {resp_path}", file=sys.stderr)
        return 2

    raw = resp_path.read_text(encoding="utf-8")
    body = extract_first_move_fence(raw)
    if body is None:
        print("parse_stage: no ```move fenced block found", file=sys.stderr)
        return 3

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(ensure_trailing_newline(body), encoding="utf-8")

    env = os.environ.copy()
    proc = subprocess.run(
        ["aptos", "move", "test", "--package-dir", str(pkg)],
        env=env,
    )
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
