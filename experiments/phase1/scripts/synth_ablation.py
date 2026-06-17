"""Ablation baselines for MoVES Phase 1.

Supports three ablation modes:
    --mode single_role    Same LLM sees prover error and rewrites; no separate diagnoser.
    --mode few_shot       +Ctx prompt + 1-2 worked examples from same module.
    --mode cot            +Ctx prompt + chain-of-thought spec analysis before coding.

Each mode runs on 5 representative functions (1 L1 + 2 L2 + 1 L3 + 1 L4).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from body_fence import extract_body
from metadata_extractor import load_registry
from synth_b3 import build_b3_prompt
from synth_common import (
    DEFAULT_TEMPERATURE,
    FunctionInputs,
    RESULTS_DIR,
    call_llm_for_body,
    make_error_row,
    utc_run_id,
    verify_or_extraction_failed,
    write_baseline_summary,
)
from verify_synth import verify

# ── Representative 5-function sample for ablations ──
ABLATION_SAMPLE = [
    "chain_id_get",          # L1
    "guid_create",           # L2
    "account_create_account",  # L2
    "coin_extract",          # L3
    "stake_update_perf",     # L4
]

# ═══════════════════════════════════════════════════════════════════════════════
# Single-role ablation
# ═══════════════════════════════════════════════════════════════════════════════

SINGLE_ROLE_FEEDBACK_TEMPLATE = """\
Your previous attempt at this Move function body failed `aptos move prove`.
Analyze the error below and produce a corrected body. The spec block must NOT
change; only the body changes.

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Previous Body (failed) ===
{previous_body}

=== Prover Output (raw) ===
{prover_output}

=== Output format ===
Return ONLY the corrected function body wrapped in:
<<<BODY
... your corrected Move code here ...
BODY>>>
"""


def build_single_role_feedback_prompt(
    inp: FunctionInputs, previous_body: str, prover_stdout: str, prover_stderr: str
) -> str:
    output = f"STDOUT:\n{prover_stdout}\n\nSTDERR:\n{prover_stderr}".strip()
    if len(output) > 6000:
        output = output[:3000] + "\n... [truncated] ...\n" + output[-3000:]
    return SINGLE_ROLE_FEEDBACK_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
        previous_body=previous_body.strip() or "(empty)",
        prover_output=output,
    )


def run_single_role(
    fn_id: str,
    run_dir: Path,
    *,
    feedback_rounds: int,
    max_tokens: int,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """Same LLM for codegen + diagnosis. No separate diagnose call."""
    inp = FunctionInputs.load(fn_id)
    out_dir = run_dir / fn_id
    rounds_dir = out_dir / "rounds"

    # Round 0: +Ctx-style
    prompt0 = build_b3_prompt(inp)
    resp0 = call_llm_for_body(prompt0, max_tokens=max_tokens, provider=provider, model=model)
    body0 = extract_body(resp0)
    verify0 = verify_or_extraction_failed(fn_id, body0)

    _write_round_single(rounds_dir / "round_0", prompt0, resp0, body0, verify0)
    history = [_history_entry(0, body0, verify0)]
    print(f"{fn_id} round 0: passed={verify0['passed']} summary={verify0.get('error_summary','')!r}")

    if verify0["passed"]:
        passed, rounds_to_success = True, 1
    else:
        passed, rounds_to_success = False, None
        previous_body = body0 or ""
        previous_verify = verify0

        for k in range(1, feedback_rounds + 1):
            prompt_k = build_single_role_feedback_prompt(
                inp, previous_body,
                previous_verify.get("stdout", ""),
                previous_verify.get("stderr", ""),
            )
            resp_k = call_llm_for_body(prompt_k, max_tokens=max_tokens, provider=provider, model=model)
            body_k = extract_body(resp_k)
            verify_k = verify_or_extraction_failed(fn_id, body_k)
            _write_round_single(rounds_dir / f"round_{k}", prompt_k, resp_k, body_k, verify_k)
            history.append(_history_entry(k, body_k, verify_k))
            print(f"{fn_id} round {k}: passed={verify_k['passed']} summary={verify_k.get('error_summary','')!r}")

            if verify_k["passed"]:
                passed, rounds_to_success = True, k + 1
                break
            previous_body = body_k or previous_body
            previous_verify = verify_k

    return _finalize(fn_id, out_dir, passed, rounds_to_success, feedback_rounds, history)


# ═══════════════════════════════════════════════════════════════════════════════
# Few-shot ablation
# ═══════════════════════════════════════════════════════════════════════════════

FEW_SHOT_TEMPLATE = """\
Task: Write the body of a Move function so that it satisfies the formal specification.

Constraints:
- Move (Aptos dialect) source code only.
- You may use anything declared in the Module Context below.
- Do NOT modify the spec block.

=== Worked Example (from same module) ===
The following is a correct function from the same module, showing how spec and body align.

Example Signature:
{example_signature}

Example Spec:
{example_spec}

Example Body:
{example_body}

=== Function Signature (do not repeat in your output) ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Output format ===
Return ONLY the function body wrapped in:
<<<BODY
... your Move code here ...
BODY>>>
"""


def _pick_example(fn_id: str, inp: FunctionInputs) -> FunctionInputs | None:
    """Pick another function from the same module as a worked example."""
    registry = load_registry()
    module = inp.signature.split("fun")[0].split("::")[-1].strip() if "::" in inp.signature else ""
    # Simple heuristic: find another function with same source_file
    candidates = [
        f for f in registry
        if f.id != fn_id and f.source_file == registry[[r.id for r in registry].index(fn_id)].source_file
    ] if fn_id in [r.id for r in registry] else []
    if not candidates:
        return None
    ex = candidates[0]
    try:
        return FunctionInputs.load(ex.id)
    except Exception:
        return None


def build_few_shot_prompt(inp: FunctionInputs) -> str:
    example = _pick_example(inp.id, inp)
    if example is None:
        # Fallback to plain +Ctx
        return build_b3_prompt(inp)
    return FEW_SHOT_TEMPLATE.format(
        example_signature=example.signature.strip(),
        example_spec=example.spec_block.strip(),
        example_body=example.reference_body.strip(),
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CoT ablation
# ═══════════════════════════════════════════════════════════════════════════════

COT_TEMPLATE = """\
Task: Write the body of a Move function so that it satisfies the formal specification.

Before writing code, analyze the specification step by step:
1. What does each `requires` clause demand?
2. Under what conditions should the function abort (per `aborts_if`)?
3. What state must hold after the function returns (per `ensures`)?
4. What memory locations may the function modify (per `modifies`)?
5. Are there any loop invariants or ghost variables involved?

Write your analysis inside <<<ANALYSIS ... ANALYSIS>>> markers, then write the
function body inside <<<BODY ... BODY>>> markers.

Constraints:
- Move (Aptos dialect) source code only.
- You may use anything declared in the Module Context below.
- Do NOT modify the spec block.

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Output format ===
<<<ANALYSIS
Your step-by-step analysis of the spec...
ANALYSIS>>>

<<<BODY
Your Move function body...
BODY>>>
"""


def build_cot_prompt(inp: FunctionInputs) -> str:
    return COT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
    )


def extract_body_cot(response: str) -> str | None:
    """Extract body from CoT response; ignores the ANALYSIS block."""
    # Try standard body fence first
    from body_fence import extract_body as _extract
    return _extract(response)


# ═══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _write_round_single(round_dir: Path, prompt: str, response: str, body: str | None, verify_payload: dict) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (round_dir / "response.txt").write_text(response, encoding="utf-8")
    (round_dir / "extracted_body.txt").write_text(body or "", encoding="utf-8")
    (round_dir / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")


def _history_entry(round_idx: int, body: str | None, verify_payload: dict) -> dict:
    return {
        "round": round_idx,
        "passed": bool(verify_payload["passed"]),
        "exit_code": verify_payload.get("exit_code"),
        "prove_time_sec": verify_payload.get("prove_time_sec", 0),
        "error_summary": verify_payload.get("error_summary", ""),
        "extraction_failed": body is None,
    }


def _finalize(fn_id: str, out_dir: Path, passed: bool, rounds_to_success: int | None, budget: int, history: list) -> dict:
    summary = {
        "id": fn_id,
        "passed": passed,
        "rounds_to_success": rounds_to_success,
        "feedback_rounds_used": (rounds_to_success - 1) if passed else budget,
        "feedback_rounds_budget": budget,
        "history": history,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    line = f"{fn_id}: passed={passed} rounds_to_success={rounds_to_success} budget={budget}"
    (out_dir / "summary.txt").write_text(line + "\n", encoding="utf-8")
    print(line)
    return summary


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    p = argparse.ArgumentParser(description="Run ablation baselines.")
    p.add_argument("--mode", choices=["single_role", "few_shot", "cot"], required=True)
    p.add_argument("--id", help="Function id (omit to run ablation sample set).")
    p.add_argument("--feedback-rounds", type=int, default=1, help="For single_role only.")
    p.add_argument("--provider", default=None, help="LLM provider: kimi or deepseek (default: env LLM_PROVIDER or kimi).")
    p.add_argument("--model", default=None, help="Provider model override.")
    p.add_argument("--max-tokens", type=int, default=32000)
    p.add_argument("--run-id", help="Override run directory name.")
    args = p.parse_args()

    registry = load_registry()
    if args.id:
        selected = [f for f in registry if f.id == args.id]
    else:
        selected = [f for f in registry if f.id in ABLATION_SAMPLE]
    if not selected:
        print(f"No function matching --id {args.id!r}", file=sys.stderr)
        return 1

    run_id = args.run_id or utc_run_id()
    run_dir = RESULTS_DIR / run_id / args.mode
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for fn in selected:
        try:
            if args.mode == "single_role":
                res = run_single_role(
                    fn.id,
                    run_dir,
                    feedback_rounds=args.feedback_rounds,
                    max_tokens=args.max_tokens,
                    provider=args.provider,
                    model=args.model,
                )
            elif args.mode == "few_shot":
                inp = FunctionInputs.load(fn.id)
                prompt = build_few_shot_prompt(inp)
                resp = call_llm_for_body(
                    prompt,
                    max_tokens=args.max_tokens,
                    provider=args.provider,
                    model=args.model,
                )
                body = extract_body(resp)
                verify_payload = verify_or_extraction_failed(fn.id, body)
                out = run_dir / fn.id
                out.mkdir(parents=True, exist_ok=True)
                (out / "prompt.txt").write_text(prompt, encoding="utf-8")
                (out / "response.txt").write_text(resp, encoding="utf-8")
                (out / "extracted_body.txt").write_text(body or "", encoding="utf-8")
                (out / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")
                line = f"{fn.id}: passed={verify_payload['passed']} exit={verify_payload['exit_code']} time={verify_payload.get('prove_time_sec',0)}s"
                (out / "summary.txt").write_text(line + "\n", encoding="utf-8")
                print(line)
                res = {"id": fn.id, "passed": bool(verify_payload["passed"]), "exit_code": verify_payload["exit_code"]}
            elif args.mode == "cot":
                inp = FunctionInputs.load(fn.id)
                prompt = build_cot_prompt(inp)
                resp = call_llm_for_body(
                    prompt,
                    max_tokens=args.max_tokens,
                    provider=args.provider,
                    model=args.model,
                )
                body = extract_body_cot(resp)
                verify_payload = verify_or_extraction_failed(fn.id, body)
                out = run_dir / fn.id
                out.mkdir(parents=True, exist_ok=True)
                (out / "prompt.txt").write_text(prompt, encoding="utf-8")
                (out / "response.txt").write_text(resp, encoding="utf-8")
                (out / "extracted_body.txt").write_text(body or "", encoding="utf-8")
                (out / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")
                line = f"{fn.id}: passed={verify_payload['passed']} exit={verify_payload['exit_code']} time={verify_payload.get('prove_time_sec',0)}s"
                (out / "summary.txt").write_text(line + "\n", encoding="utf-8")
                print(line)
                res = {"id": fn.id, "passed": bool(verify_payload["passed"]), "exit_code": verify_payload["exit_code"]}
            else:
                raise ValueError(f"Unknown mode: {args.mode}")
            rows.append({"id": fn.id, "passed": res.get("passed", False)})
        except Exception as exc:
            err = f"{fn.id}: ERROR {type(exc).__name__}: {exc}"
            print(err, file=sys.stderr)
            (run_dir / fn.id).mkdir(parents=True, exist_ok=True)
            (run_dir / fn.id / "error.txt").write_text(str(exc), encoding="utf-8")
            rows.append(make_error_row(fn.id, exc))

    write_baseline_summary(
        run_dir,
        args.mode,
        rows,
        artifact_tag=args.mode,
        provider=args.provider,
        model=args.model,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=args.max_tokens,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
