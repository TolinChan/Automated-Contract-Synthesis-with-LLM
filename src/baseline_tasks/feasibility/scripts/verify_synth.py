"""Splice a generated function body into aptos-framework, run Move Prover.

Workflow per call:
  1. Reset workspace source file from canonical aptos-framework copy.
  2. Locate `fun <name>(...) {...}` in the workspace file.
  3. Replace the body (between matched braces) with the candidate string.
  4. Run `aptos move prove --filter <module-stem>` against the workspace package.
  5. Capture exit code, stdout, stderr, wall time. Return as VerifyResult.

The workspace under E:\\src\\move-poc\\synth\\framework_workspace is a static
clone of aptos-framework (created once); resetting it from the canonical copy
gives strong isolation between runs. We never mutate the canonical tree.

Public surface:
    verify(function_id: str, body: str, *, timeout_sec: int = 600) -> VerifyResult
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from metadata_extractor import (
    FEASIBILITY_DIR,
    FRAMEWORK_SRC,
    find_block_after,
    load_registry,
)

WORKSPACE_ROOT = Path(r"E:\src\move-poc\synth\framework_workspace")
WORKSPACE_PKG = WORKSPACE_ROOT / "aptos-framework"
WORKSPACE_SRC = WORKSPACE_PKG / "sources"

_WINGET_APTOS = Path(
    r"C:\Users\96247\AppData\Local\Microsoft\WinGet\Packages"
    r"\AptosCore.aptos_Microsoft.Winget.Source_8wekyb3d8bbwe\aptos.exe"
)
_DEFAULT_BOOGIE = Path(r"C:\Users\96247\.dotnet\tools\boogie.exe")
_DEFAULT_Z3 = Path(r"E:\tools\z3_extract\z3-4.13.0-x64-win\bin\z3.exe")


@dataclass
class VerifyResult:
    function_id: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    command: list[str]
    prove_time_sec: float
    splice_succeeded: bool
    error_summary: str  # short hint when not passed (parsed from stderr/stdout)

    def to_json(self) -> dict:
        return asdict(self)


def _aptos_cmd() -> str:
    return str(_WINGET_APTOS) if _WINGET_APTOS.is_file() else "aptos"


def _registry_lookup(function_id: str):
    for fn in load_registry():
        if fn.id == function_id:
            return fn
    raise KeyError(function_id)


def _reset_workspace_file(rel_source: str) -> Path:
    """Reset the target .move (and matching .spec.move) AND any other .move files
    that may have been mutated by a prior run. Without this, splicing a bad body
    into module A pollutes A.move; the next run for module B compiles the whole
    package and fails on A.

    We restore every .move file under the workspace `sources/` from canonical.
    Cheap (a few hundred files, tens of MB at most) and bulletproof.
    """
    if not FRAMEWORK_SRC.is_dir():
        raise FileNotFoundError(f"Canonical sources missing: {FRAMEWORK_SRC}")
    if not WORKSPACE_SRC.is_dir():
        raise FileNotFoundError(f"Workspace sources missing: {WORKSPACE_SRC}")
    for canonical in FRAMEWORK_SRC.rglob("*.move"):
        rel = canonical.relative_to(FRAMEWORK_SRC)
        target = WORKSPACE_SRC / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(canonical, target)

    target = WORKSPACE_SRC / rel_source
    canonical = FRAMEWORK_SRC / rel_source
    if not canonical.is_file():
        raise FileNotFoundError(f"Canonical source missing: {canonical}")
    return target


_FUN_RE_TPL = (
    r"^[ \t]*(?:#\[[^\]]+\]\s*)*"
    r"(?:public(?:\s*\(\s*friend\s*\))?\s+|public\s+entry\s+|entry\s+)?"
    r"fun\s+{name}\b"
)


def _splice_body(file_path: Path, fn_name: str, new_body: str) -> bool:
    text = file_path.read_text(encoding="utf-8")
    pat = re.compile(_FUN_RE_TPL.format(name=re.escape(fn_name)), re.MULTILINE)
    m = pat.search(text)
    if m is None:
        return False
    open_pos, close_pos = find_block_after(text, m.end())
    new_text = text[: open_pos + 1] + new_body + text[close_pos:]
    file_path.write_text(new_text, encoding="utf-8")
    return True


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

_ERROR_HINT_RES = [
    re.compile(r"error\[E\d+\][^\n]*", re.IGNORECASE),
    re.compile(r"^error: .*$", re.MULTILINE),
    re.compile(r"verification failed[^\n]*", re.IGNORECASE),
    re.compile(r"abort error[^\n]*", re.IGNORECASE),
    re.compile(r"^.*could not [^\n]*$", re.MULTILINE),
]


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _extract_summary(stdout: str, stderr: str) -> str:
    text = _strip_ansi(stderr) + "\n" + _strip_ansi(stdout)
    for rx in _ERROR_HINT_RES:
        m = rx.search(text)
        if m:
            return m.group(0).strip()[:300]
    # fall back to last non-empty line
    for line in reversed(text.splitlines()):
        s = line.strip()
        if s and s not in ("}", "{"):
            return s[:300]
    return ""


def verify(function_id: str, body: str, *, timeout_sec: int = 600) -> VerifyResult:
    fn = _registry_lookup(function_id)
    target = _reset_workspace_file(fn.source_file)
    spliced = _splice_body(target, fn.function, body)
    if not spliced:
        return VerifyResult(
            function_id=function_id,
            passed=False,
            exit_code=-1,
            stdout="",
            stderr=f"Could not locate function `{fn.function}` in {target}",
            command=[],
            prove_time_sec=0.0,
            splice_succeeded=False,
            error_summary="splice_failed",
        )

    env = os.environ.copy()
    if not env.get("BOOGIE_EXE") and _DEFAULT_BOOGIE.is_file():
        env["BOOGIE_EXE"] = str(_DEFAULT_BOOGIE)
    if not env.get("Z3_EXE") and _DEFAULT_Z3.is_file():
        env["Z3_EXE"] = str(_DEFAULT_Z3)

    module_stem = Path(fn.source_file).stem
    cmd = [
        _aptos_cmd(),
        "move",
        "prove",
        "--package-dir",
        str(WORKSPACE_PKG),
        "--filter",
        module_stem,
    ]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        elapsed = time.monotonic() - t0
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = int(proc.returncode)
    except subprocess.TimeoutExpired as e:
        elapsed = time.monotonic() - t0
        stdout = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="replace") if e.stdout else "")
        stderr_raw = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="replace") if e.stderr else "")
        stderr = stderr_raw + f"\n[TIMEOUT after {timeout_sec}s]"
        exit_code = -2

    passed = exit_code == 0
    return VerifyResult(
        function_id=function_id,
        passed=passed,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        command=cmd,
        prove_time_sec=round(elapsed, 2),
        splice_succeeded=True,
        error_summary="" if passed else _extract_summary(stdout, stderr),
    )


def main() -> int:
    """CLI: verify the reference body for one function (sanity check)."""
    import argparse

    p = argparse.ArgumentParser(description="Sanity-check verify by splicing the reference body.")
    p.add_argument("--id", required=True)
    args = p.parse_args()

    fn = _registry_lookup(args.id)
    body_path = FEASIBILITY_DIR / "functions" / fn.id / "reference_body.txt"
    body = body_path.read_text(encoding="utf-8") if body_path.is_file() else ""
    if not body:
        print(f"reference_body.txt missing for {fn.id}; run metadata_extractor.py first")
        return 1
    res = verify(args.id, body)
    print(f"{fn.id}: passed={res.passed} exit={res.exit_code} time={res.prove_time_sec}s")
    if not res.passed:
        print(f"summary: {res.error_summary}")
        print("---- stderr tail ----")
        print((res.stderr or "")[-1500:])
    return 0 if res.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
