#!/usr/bin/env python3
"""
Run gold-standard check for a baseline task (Move Prover or unit tests).

Usage:
  python check_task.py --task-id t0_plus1
  python check_task.py --task-id t1_aborts
  python check_task.py --task-id t2_hello_blockchain

For t0/t1, set BOOGIE_EXE and Z3_EXE (see ENV_SETUP.md). If unset, common
Windows defaults are applied when those paths exist.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PACKAGES = {
    "t0_plus1": Path(r"E:\src\move-poc\baseline\hello_prover_t0_plus1"),
    "t1_aborts": Path(r"E:\src\move-poc\baseline\hello_prover_t1_aborts"),
    "t2_hello_blockchain": Path(r"E:\src\move-poc\baseline\hello_blockchain_t2"),
}

_DEFAULT_BOOGIE = Path(r"C:\Users\96247\.dotnet\tools\boogie.exe")
_DEFAULT_Z3 = Path(r"E:\tools\z3_extract\z3-4.13.0-x64-win\bin\z3.exe")


def main() -> int:
    p = argparse.ArgumentParser(description="Run aptos move prove/test for baseline tasks.")
    p.add_argument(
        "--task-id",
        required=True,
        choices=list(PACKAGES.keys()),
        help="Baseline task identifier",
    )
    args = p.parse_args()

    pkg = PACKAGES[args.task_id]
    if not pkg.is_dir():
        print(f"Package directory not found: {pkg}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    if args.task_id != "t2_hello_blockchain":
        if not env.get("BOOGIE_EXE") and _DEFAULT_BOOGIE.is_file():
            env["BOOGIE_EXE"] = str(_DEFAULT_BOOGIE)
        if not env.get("Z3_EXE") and _DEFAULT_Z3.is_file():
            env["Z3_EXE"] = str(_DEFAULT_Z3)

    if args.task_id == "t2_hello_blockchain":
        cmd = ["aptos", "move", "test", "--package-dir", str(pkg)]
    else:
        cmd = ["aptos", "move", "prove", "--package-dir", str(pkg)]

    proc = subprocess.run(cmd, env=env)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
