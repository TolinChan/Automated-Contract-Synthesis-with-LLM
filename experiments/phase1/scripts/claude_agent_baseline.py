"""Run the Claude Code CLI baseline for Phase 1 benchmarks.

This harness treats Claude Code as the code-generation/repair backend, while
keeping verification and artifact writing under the existing Phase 1 verifier.
It deliberately splices only generated function bodies into the isolated Move
workspace via verify_synth.py; benchmark specs, signatures, metadata, and the
canonical aptos-framework tree are never edited.

Default run:
    python claude_agent_baseline.py --pilot

Full run after pilot:
    python claude_agent_baseline.py --all
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from body_fence import extract_body
from metadata_extractor import FEASIBILITY_DIR, FunctionSpec, load_registry
from synth_common import FunctionInputs, utc_timestamp
from verify_synth import verify


RESULTS_DIR = FEASIBILITY_DIR / "results"
DEFAULT_DEEPSEEK_OUTPUT_DIR = RESULTS_DIR / "claude_agent_deepseek_20260604"
DEFAULT_OFOX_OUTPUT_DIR = RESULTS_DIR / "claude_agent_ofox_opus47_failed8_20260604"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro[1m]"
DEFAULT_DEEPSEEK_HAIKU_MODEL = "deepseek-v4-flash"
DEFAULT_OFOX_MODEL = "anthropic/claude-opus-4.7"
DEFAULT_BACKEND = "deepseek"
BACKENDS = {
    "deepseek": {
        "label": "DeepSeek Anthropic-compatible API",
        "metadata": "deepseek_anthropic_compatible",
        "base_url": "https://api.deepseek.com/anthropic",
        "model": DEFAULT_DEEPSEEK_MODEL,
        "haiku_model": DEFAULT_DEEPSEEK_HAIKU_MODEL,
    },
    "ofox": {
        "label": "OFOX Anthropic Native",
        "metadata": "ofox_anthropic_native",
        "base_url": "https://api.ofox.ai/anthropic",
        "model": DEFAULT_OFOX_MODEL,
        "haiku_model": DEFAULT_OFOX_MODEL,
    },
}
PILOT_IDS = [
    "chain_id_initialize",
    "account_create_account_if_does_not_exist",
    "coin_mint_internal",
]

DISABLED_SPEC_IDS = {
    "stake_append",
    "staking_contract_request_commission",
}

WEAK_SPEC_IDS = {
    "block_block_prologue_common",
    "block_emit_new_block_event",
    "fungible_asset_unchecked_deposit",
    "reconfiguration_reconfigure",
    "stake_next_validator_consensus_infos",
    "stake_remove_validators",
    "stake_update_perf",
    "stake_update_stake_pool",
    "staking_contract_create_staking_contract_with_coins",
    "storage_gas_on_reconfig",
}

SYSTEM_APPEND = (
    "You are running a controlled Claude Code Agent baseline for an Aptos Move "
    "spec-to-code experiment. Do not edit files. A separate harness will splice "
    "and verify your generated body. Return only the requested body markers."
)

ROUND0_PROMPT = """\
Task: Generate the body of the Aptos Move function below.

The body will be spliced between the function's outer braces and checked with
`aptos move prove`. Satisfy every relevant clause in the formal specification.

Hard constraints:
- Output only the function body wrapped in <<<BODY ... BODY>>>.
- Do not include the function signature or surrounding braces.
- Do not modify the spec, `spec fun`, signature, imports, structs, constants, or metadata.
- Use only valid Aptos Move code available from the signature or module context.
- If a spec idiom needs ghost updates, use Move Prover syntax such as
  `spec {{ update ghost_x = expr; }};` inside the body.

=== Function ID ===
{fn_id}

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Output Format ===
<<<BODY
... Move body only ...
BODY>>>
"""

FEEDBACK_PROMPT = """\
Your previous body for this Aptos Move function failed verification.
Generate a corrected body. The harness will splice and verify it.

Hard constraints:
- Output only the corrected function body wrapped in <<<BODY ... BODY>>>.
- Do not include the function signature or surrounding braces.
- Do not modify the spec, `spec fun`, signature, imports, structs, constants, or metadata.
- Keep fixes targeted to the prover/compiler failure below.

=== Function ID ===
{fn_id}

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Previous Body ===
{previous_body}

=== Prover/Compiler Output ===
{prover_output}

=== Output Format ===
<<<BODY
... corrected Move body only ...
BODY>>>
"""


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def trim_prover_output(verify_payload: dict[str, Any], limit: int = 14000) -> str:
    stdout = strip_ansi(verify_payload.get("stdout", ""))
    stderr = strip_ansi(verify_payload.get("stderr", ""))
    text = (stderr + "\n" + stdout).strip()
    if len(text) <= limit:
        return text or "(empty)"
    return "[truncated]\n" + text[-limit:]


def parse_ids(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    ids = {item.strip() for item in raw.split(",") if item.strip()}
    return ids or None


def select_registry(args: argparse.Namespace) -> list[FunctionSpec]:
    registry = load_registry()
    by_id = {fn.id: fn for fn in registry}

    modes = sum(bool(x) for x in (args.pilot, args.all, args.ids))
    if modes != 1:
        raise SystemExit("Select exactly one of --pilot, --all, or --ids.")

    if args.pilot:
        requested = PILOT_IDS
    elif args.all:
        requested = [fn.id for fn in registry]
    else:
        requested = list(parse_ids(args.ids) or [])

    missing = [fn_id for fn_id in requested if fn_id not in by_id]
    if missing:
        raise SystemExit(f"Unknown function id(s): {', '.join(missing)}")
    return [by_id[fn_id] for fn_id in requested]


def load_claude_settings_env() -> dict[str, str]:
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.is_file():
        return {}
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    env = payload.get("env")
    return env if isinstance(env, dict) else {}


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_dotenv_value(names: tuple[str, ...]) -> str | None:
    env_path = project_root() / ".env"
    if not env_path.is_file():
        return None
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() in names:
            return val.strip().strip('"').strip("'")
    return None


def resolve_backend(backend: str) -> dict[str, str]:
    try:
        return BACKENDS[backend]
    except KeyError as exc:
        raise RuntimeError(f"Unknown backend {backend!r}; expected one of: {', '.join(BACKENDS)}") from exc


def backend_token(backend: str, env: dict[str, str], settings_env: dict[str, str]) -> str:
    if backend == "deepseek":
        token = (
            settings_env.get("ANTHROPIC_AUTH_TOKEN")
            or env.get("ANTHROPIC_AUTH_TOKEN")
            or env.get("DEEPSEEK_API_KEY")
            or load_dotenv_value(("ANTHROPIC_AUTH_TOKEN", "DEEPSEEK_API_KEY"))
        )
        if not token:
            raise RuntimeError("DeepSeek token not found in Claude settings, ANTHROPIC_AUTH_TOKEN, or DEEPSEEK_API_KEY.")
        return token

    if backend == "ofox":
        token = (
            env.get("OFOX_API_KEY")
            or env.get("OFOXAI_API_KEY")
            or load_dotenv_value(("OFOX_API_KEY", "OFOXAI_API_KEY"))
        )
        if not token and "ofox.ai" in (settings_env.get("ANTHROPIC_BASE_URL") or ""):
            token = settings_env.get("ANTHROPIC_AUTH_TOKEN")
        if not token:
            raise RuntimeError("OFOX token not found. Set OFOX_API_KEY or OFOXAI_API_KEY in environment or .env.")
        return token

    raise RuntimeError(f"Unknown backend {backend!r}.")


def claude_env(
    model: str,
    *,
    backend: str,
    haiku_model: str | None = None,
    proxy_url: str | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    settings_env = load_claude_settings_env()
    cfg = resolve_backend(backend)
    token = backend_token(backend, env, settings_env)
    small_model = haiku_model or cfg["haiku_model"] or model

    env.pop("ANTHROPIC_API_KEY", None)
    env["ANTHROPIC_AUTH_TOKEN"] = token
    if backend == "ofox":
        env["ANTHROPIC_API_KEY"] = token
    env["ANTHROPIC_BASE_URL"] = cfg["base_url"]
    env["ANTHROPIC_MODEL"] = model
    env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model
    env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model
    env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = small_model
    env["CLAUDE_CODE_SUBAGENT_MODEL"] = small_model
    env["CLAUDE_CODE_EFFORT_LEVEL"] = "max"
    if proxy_url:
        env["HTTP_PROXY"] = proxy_url
        env["HTTPS_PROXY"] = proxy_url
        env["ALL_PROXY"] = proxy_url
        env["NODE_USE_ENV_PROXY"] = "1"
    return env


def claude_settings_file(env: dict[str, str]) -> str:
    settings_env = {
        "ANTHROPIC_BASE_URL": env["ANTHROPIC_BASE_URL"],
        "ANTHROPIC_AUTH_TOKEN": env["ANTHROPIC_AUTH_TOKEN"],
        "ANTHROPIC_MODEL": env["ANTHROPIC_MODEL"],
        "ANTHROPIC_DEFAULT_OPUS_MODEL": env["ANTHROPIC_DEFAULT_OPUS_MODEL"],
        "ANTHROPIC_DEFAULT_SONNET_MODEL": env["ANTHROPIC_DEFAULT_SONNET_MODEL"],
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": env["ANTHROPIC_DEFAULT_HAIKU_MODEL"],
        "CLAUDE_CODE_SUBAGENT_MODEL": env["CLAUDE_CODE_SUBAGENT_MODEL"],
        "CLAUDE_CODE_EFFORT_LEVEL": env["CLAUDE_CODE_EFFORT_LEVEL"],
    }
    if "ANTHROPIC_API_KEY" in env:
        settings_env["ANTHROPIC_API_KEY"] = env["ANTHROPIC_API_KEY"]
    fd, path = tempfile.mkstemp(prefix="claude-agent-", suffix=".settings.json")
    os.close(fd)
    Path(path).write_text(json.dumps({"env": settings_env}), encoding="utf-8")
    return path


def call_claude(
    prompt: str,
    *,
    model: str,
    backend: str,
    haiku_model: str | None,
    proxy_url: str | None,
    timeout_sec: int,
    max_budget_usd: float | None,
) -> tuple[str, dict[str, Any]]:
    env = claude_env(model, backend=backend, haiku_model=haiku_model, proxy_url=proxy_url)
    settings_path = claude_settings_file(env)
    cmd = [
        "claude",
        "-p",
        "--setting-sources",
        "local",
        "--settings",
        settings_path,
        "--model",
        model,
        "--effort",
        "max",
        "--output-format",
        "json",
        "--tools",
        "",
        "--append-system-prompt",
        SYSTEM_APPEND,
    ]
    if max_budget_usd and max_budget_usd > 0:
        cmd.extend(["--max-budget-usd", str(max_budget_usd)])

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_sec,
            env=env,
        )
    finally:
        Path(settings_path).unlink(missing_ok=True)

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {
            "type": "error",
            "is_error": True,
            "result": stdout,
            "stderr": stderr,
            "returncode": proc.returncode,
        }

    payload.setdefault("returncode", proc.returncode)
    if stderr:
        payload["stderr"] = stderr
    if proc.returncode != 0 and not payload.get("is_error"):
        payload["is_error"] = True
    response = str(payload.get("result") or "")
    return response, payload


def extraction_failed_payload(fn_id: str) -> dict[str, Any]:
    return {
        "function_id": fn_id,
        "passed": False,
        "exit_code": -3,
        "stdout": "",
        "stderr": "Body extraction failed: no <<<BODY...BODY>>> or ```move``` block found.",
        "command": [],
        "prove_time_sec": 0.0,
        "splice_succeeded": False,
        "error_summary": "extraction_failed",
    }


def spec_flags(fn_id: str, spec_text: str) -> dict[str, bool]:
    disabled_spec = bool(re.search(r"\bverify\s*=\s*false\b", spec_text)) or fn_id in DISABLED_SPEC_IDS
    has_ensures = bool(re.search(r"\bensures\b", spec_text))
    has_aborts_if = bool(re.search(r"\baborts_if\b", spec_text))
    has_modifies = bool(re.search(r"\bmodifies\b", spec_text))
    no_ensures = not has_ensures
    modifies_only = has_modifies and not has_ensures and not has_aborts_if
    weak_spec = disabled_spec or no_ensures or modifies_only or fn_id in WEAK_SPEC_IDS
    return {
        "clean_spec": not weak_spec,
        "weak_spec": weak_spec,
        "disabled_spec": disabled_spec,
        "no_ensures": no_ensures,
        "modifies_only": modifies_only,
    }


def build_prompt(fn_id: str, inp: FunctionInputs, round_idx: int, previous_body: str, previous_verify: dict[str, Any] | None) -> str:
    if round_idx == 0:
        return ROUND0_PROMPT.format(
            fn_id=fn_id,
            signature=inp.signature.strip(),
            spec_block=inp.spec_block.strip(),
            module_context=inp.module_context.strip() or "(no extra context)",
        )
    return FEEDBACK_PROMPT.format(
        fn_id=fn_id,
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
        previous_body=previous_body.strip() or "(empty)",
        prover_output=trim_prover_output(previous_verify or {}),
    )


def write_round(
    round_dir: Path,
    *,
    prompt: str,
    response: str,
    body: str | None,
    verify_payload: dict[str, Any],
    claude_payload: dict[str, Any],
) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (round_dir / "response.txt").write_text(response, encoding="utf-8")
    (round_dir / "extracted_body.txt").write_text(body or "", encoding="utf-8")
    (round_dir / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")
    (round_dir / "claude_result.json").write_text(json.dumps(claude_payload, indent=2), encoding="utf-8")


def run_one(
    fn: FunctionSpec,
    out_root: Path,
    *,
    model: str,
    backend: str,
    haiku_model: str | None,
    proxy_url: str | None,
    max_rounds: int,
    claude_timeout_sec: int,
    verify_timeout_sec: int,
    max_budget_usd: float | None,
    force: bool,
) -> dict[str, Any]:
    out_dir = out_root / fn.id
    summary_path = out_dir / "summary.json"
    if summary_path.is_file() and not force:
        return json.loads(summary_path.read_text(encoding="utf-8"))

    inp = FunctionInputs.load(fn.id)
    flags = spec_flags(fn.id, inp.spec_block)
    out_dir.mkdir(parents=True, exist_ok=True)

    history: list[dict[str, Any]] = []
    previous_body = ""
    previous_verify: dict[str, Any] | None = None
    passed = False
    rounds_to_success: int | None = None
    total_cost = 0.0
    model_usage: dict[str, Any] = {}

    for round_idx in range(max_rounds):
        prompt = build_prompt(fn.id, inp, round_idx, previous_body, previous_verify)
        try:
            response, claude_payload = call_claude(
                prompt,
                model=model,
                backend=backend,
                haiku_model=haiku_model,
                proxy_url=proxy_url,
                timeout_sec=claude_timeout_sec,
                max_budget_usd=max_budget_usd,
            )
        except subprocess.TimeoutExpired as exc:
            response = ""
            claude_payload = {
                "type": "error",
                "is_error": True,
                "error": f"claude_timeout_after_{claude_timeout_sec}s",
                "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
                "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            }

        total_cost += float(claude_payload.get("total_cost_usd") or claude_payload.get("costUSD") or 0.0)
        usage = claude_payload.get("modelUsage")
        if isinstance(usage, dict):
            for key, value in usage.items():
                model_usage[key] = value

        body = extract_body(response)
        if body is None:
            verify_payload = extraction_failed_payload(fn.id)
        else:
            verify_payload = verify(fn.id, body, timeout_sec=verify_timeout_sec).to_json()

        write_round(
            out_dir / "rounds" / f"round_{round_idx}",
            prompt=prompt,
            response=response,
            body=body,
            verify_payload=verify_payload,
            claude_payload=claude_payload,
        )

        row = {
            "round": round_idx,
            "passed": bool(verify_payload.get("passed")),
            "exit_code": verify_payload.get("exit_code"),
            "prove_time_sec": verify_payload.get("prove_time_sec", 0),
            "error_summary": verify_payload.get("error_summary", ""),
            "extraction_failed": body is None,
            "claude_is_error": bool(claude_payload.get("is_error")),
            "claude_returncode": claude_payload.get("returncode"),
            "claude_cost_usd": claude_payload.get("total_cost_usd"),
            "model": model,
            "backend": backend,
        }
        history.append(row)
        print(
            f"{fn.id} round {round_idx}: passed={row['passed']} "
            f"summary={row['error_summary']!r} cost={row['claude_cost_usd']}"
        )

        if verify_payload.get("passed"):
            passed = True
            rounds_to_success = round_idx + 1
            break
        previous_body = body or previous_body
        previous_verify = verify_payload

        if claude_payload.get("is_error") and body is None:
            # Do not spend more rounds when Claude itself failed before returning code.
            break

    summary = {
        "id": fn.id,
        "module": fn.module,
        "function": fn.function,
        "source_file": fn.source_file,
        "spec_file": fn.spec_file,
        "complexity": fn.complexity,
        "provider_surface": "claude_code_cli",
        "provider_backend": resolve_backend(backend)["metadata"],
        "backend": backend,
        "model": model,
        "effort": "max",
        "max_rounds": max_rounds,
        "passed": passed,
        "agent_rounds_to_success": rounds_to_success,
        "rounds_to_success": rounds_to_success,
        "feedback_rounds_used": (rounds_to_success - 1) if rounds_to_success else max(0, len(history) - 1),
        "total_cost_usd": round(total_cost, 6),
        "model_usage": model_usage,
        "final_error_summary": "" if passed else (history[-1]["error_summary"] if history else "no_rounds"),
        "history": history,
        **flags,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "summary.txt").write_text(
        f"{fn.id}: passed={passed} agent_rounds_to_success={rounds_to_success} "
        f"clean_spec={flags['clean_spec']} cost_usd={summary['total_cost_usd']}\n",
        encoding="utf-8",
    )
    return summary


CSV_FIELDS = [
    "id",
    "module",
    "function",
    "complexity",
    "provider_surface",
    "provider_backend",
    "backend",
    "passed",
    "agent_rounds_to_success",
    "feedback_rounds_used",
    "final_error_summary",
    "clean_spec",
    "weak_spec",
    "disabled_spec",
    "no_ensures",
    "modifies_only",
    "total_cost_usd",
    "model",
    "effort",
]


def aggregate(out_root: Path, selected_ids: list[str], model: str, backend: str, run_mode: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for fn_id in selected_ids:
        path = out_root / fn_id / "summary.json"
        if path.is_file():
            rows.append(json.loads(path.read_text(encoding="utf-8")))

    passed = sum(1 for row in rows if row.get("passed"))
    clean_rows = [row for row in rows if row.get("clean_spec")]
    clean_passed = sum(1 for row in clean_rows if row.get("passed"))
    total_cost = round(sum(float(row.get("total_cost_usd") or 0.0) for row in rows), 6)
    payload = {
        "created_at_utc": utc_timestamp(),
        "run_id": out_root.name,
        "run_mode": run_mode,
        "condition": "Claude Code Agent",
        "metric": "agent_rounds_to_success",
        "provider_surface": "claude_code_cli",
        "provider_backend": resolve_backend(backend)["metadata"],
        "backend": backend,
        "backend_label": resolve_backend(backend)["label"],
        "model": model,
        "effort": "max",
        "selected_total": len(selected_ids),
        "completed_total": len(rows),
        "passed": passed,
        "clean_spec_total": len(clean_rows),
        "clean_spec_passed": clean_passed,
        "total_cost_usd": total_cost,
        "rows": rows,
    }
    (out_root / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with (out_root / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    write_readme(out_root, payload)
    return payload


def write_readme(out_root: Path, payload: dict[str, Any]) -> None:
    rows = payload.get("rows", [])
    disabled = [row["id"] for row in rows if row.get("disabled_spec")]
    weak = [row["id"] for row in rows if row.get("weak_spec") and not row.get("disabled_spec")]
    failed = [row["id"] for row in rows if not row.get("passed")]
    lines = [
        "# Claude Code Agent Baseline",
        "",
        f"- Created: {payload['created_at_utc']}",
        "- Provider surface: Claude Code CLI",
        f"- Backend: {payload.get('backend_label', payload.get('provider_backend'))}",
        f"- Model: `{payload['model']}`",
        "- Effort: `max`",
        "- Metric: `agent_rounds_to_success` (1 = round 0 passed, max 4 attempts)",
        "- Note: failed-case reruns are not fresh 36-function headline baselines.",
        f"- Completed: {payload['completed_total']}/{payload['selected_total']}",
        f"- Passed: {payload['passed']}/{payload['completed_total']}",
        f"- Clean-spec passed: {payload['clean_spec_passed']}/{payload['clean_spec_total']}",
        f"- Total Claude-reported cost: ${payload['total_cost_usd']}",
        "",
        "## Interpretation Rules",
        "",
        "- Do not mix this condition with `Zero-shot` / `+Ctx` Pass@1 metrics.",
        "- Do not mix this condition with `+Diag-1` / `+Diag-3` structured-diagnoser metrics.",
        "- `stake_append` and `staking_contract_request_commission` are disabled-spec caveats and should not enter clean-spec claims.",
        "",
        "## Caveats",
        "",
        f"- Disabled spec: {', '.join(disabled) if disabled else '(none)'}",
        f"- Other weak spec: {', '.join(weak) if weak else '(none)'}",
        f"- Failed functions: {', '.join(failed) if failed else '(none)'}",
        "",
        "## Artifacts",
        "",
        "- Per-function artifacts live in `<function_id>/rounds/round_<n>/`.",
        "- Each round stores `prompt.txt`, `response.txt`, `extracted_body.txt`, `verify.json`, and `claude_result.json`.",
        "- Aggregate files: `summary.json` and `summary.csv`.",
        "",
    ]
    (out_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Run Claude Code CLI agent baseline for Phase 1.")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pilot", action="store_true", help="Run the 3-function pilot set.")
    mode.add_argument("--all", action="store_true", help="Run all registered functions.")
    mode.add_argument("--ids", help="Comma-separated function ids.")
    p.add_argument("--backend", default=DEFAULT_BACKEND, choices=sorted(BACKENDS), help="Claude Code API backend.")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--haiku-model", default=None, help="Small/subagent model override; defaults per backend.")
    p.add_argument("--proxy-url", default=None, help="Optional HTTP(S) proxy for Claude Code, e.g. http://127.0.0.1:7897.")
    p.add_argument("--max-rounds", type=int, default=4, help="Total attempts per function, including round 0.")
    p.add_argument("--max-budget-usd", type=float, default=5.0, help="Per-Claude-call budget guard. Use 0 to disable.")
    p.add_argument("--claude-timeout-sec", type=int, default=900)
    p.add_argument("--verify-timeout-sec", type=int, default=600)
    p.add_argument("--force", action="store_true", help="Rerun functions even if summary.json exists.")
    args = p.parse_args()

    if args.max_rounds < 1:
        raise SystemExit("--max-rounds must be >= 1")

    backend_cfg = resolve_backend(args.backend)
    model = args.model or backend_cfg["model"]
    out_root = Path(
        args.output_dir
        or (DEFAULT_OFOX_OUTPUT_DIR if args.backend == "ofox" else DEFAULT_DEEPSEEK_OUTPUT_DIR)
    )
    selected = select_registry(args)
    out_root.mkdir(parents=True, exist_ok=True)

    run_mode = "pilot" if args.pilot else ("all" if args.all else "ids")
    rows: list[dict[str, Any]] = []
    for fn in selected:
        try:
            rows.append(
                run_one(
                    fn,
                    out_root,
                    model=model,
                    backend=args.backend,
                    haiku_model=args.haiku_model,
                    proxy_url=args.proxy_url,
                    max_rounds=args.max_rounds,
                    claude_timeout_sec=args.claude_timeout_sec,
                    verify_timeout_sec=args.verify_timeout_sec,
                    max_budget_usd=args.max_budget_usd if args.max_budget_usd > 0 else None,
                    force=args.force,
                )
            )
        except Exception as exc:  # noqa: BLE001 - batch experiment should keep the artifact
            fn_dir = out_root / fn.id
            fn_dir.mkdir(parents=True, exist_ok=True)
            error_payload = {
                "id": fn.id,
                "passed": False,
                "agent_rounds_to_success": None,
                "rounds_to_success": None,
                "final_error_summary": f"{type(exc).__name__}: {exc}",
                "error": str(exc),
                "provider_surface": "claude_code_cli",
                "provider_backend": backend_cfg["metadata"],
                "backend": args.backend,
                "model": model,
                "effort": "max",
                **spec_flags(fn.id, FunctionInputs.load(fn.id).spec_block),
            }
            (fn_dir / "summary.json").write_text(json.dumps(error_payload, indent=2), encoding="utf-8")
            (fn_dir / "error.txt").write_text(str(exc), encoding="utf-8")
            rows.append(error_payload)
            print(f"{fn.id}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)

    aggregate(out_root, [fn.id for fn in selected], model, args.backend, run_mode)
    return 0 if all(row.get("passed") for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
