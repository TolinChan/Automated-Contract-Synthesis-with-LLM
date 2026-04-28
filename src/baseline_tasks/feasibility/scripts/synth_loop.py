"""B6 / B7 baseline: iterative codegen with prover-error feedback.

Round 0 = B3 (Spec + Signature + Module Context, single LLM call).
Round k>0 (feedback round) = LLM call with:
    - the original spec/signature/context
    - the previous body that failed
    - the prover output
    - a diagnosis produced by a separate Kimi call (see diagnose.py)

Number of feedback rounds is configurable:
    --feedback-rounds 1    -> B6 (round 0 + 1 feedback round; up to 2 attempts)
    --feedback-rounds 3    -> B7 (round 0 + 3 feedback rounds; up to 4 attempts)

Metric tracked: rounds_to_success.
    1 = passed on the very first try (no feedback needed)
    k = passed in round k-1 of feedback (i.e., k-th attempt overall)
    failure = exhausted feedback budget without passing.

NOTE: rounds_to_success is NOT the same as Pass@1; do not mix them in tables.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from body_fence import extract_body
from diagnose import diagnose
from metadata_extractor import load_registry
from synth_b3 import build_b3_prompt
from synth_common import (
    FunctionInputs,
    RESULTS_DIR,
    call_llm_for_body,
    utc_run_id,
    verify_or_extraction_failed,
    write_baseline_summary,
)

FEEDBACK_PROMPT_TEMPLATE = """\
Your previous attempt at this Move function body failed `aptos move prove`.
Use the diagnosis to produce a corrected body. The spec block must NOT change;
only the body changes.

=== Function Signature (do not repeat in your output) ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context (imports, constants, structs, sibling fn signatures) ===
{module_context}

=== Previous Body (failed) ===
{previous_body}

=== Diagnosis (from prover output) ===
{diagnosis}

=== Output format ===
Return ONLY the corrected function body wrapped in the markers below.
Do not include the function signature, the surrounding braces, or any prose
outside the markers.

<<<BODY
... your corrected Move code here ...
BODY>>>
"""


def build_feedback_prompt(
    inp: FunctionInputs, previous_body: str, diagnosis_text: str
) -> str:
    return FEEDBACK_PROMPT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
        previous_body=previous_body.strip() or "(empty)",
        diagnosis=diagnosis_text.strip() or "(no diagnosis available)",
    )


def write_round(
    round_dir: Path,
    *,
    prompt: str,
    response: str,
    body: str | None,
    verify_payload: dict,
    diagnosis_text: str | None = None,
) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (round_dir / "response.txt").write_text(response, encoding="utf-8")
    (round_dir / "extracted_body.txt").write_text(body or "", encoding="utf-8")
    (round_dir / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")
    if diagnosis_text is not None:
        (round_dir / "diagnosis.txt").write_text(diagnosis_text, encoding="utf-8")


def run_loop_one(
    fn_id: str, run_dir: Path, *, feedback_rounds: int, max_tokens: int
) -> dict:
    inp = FunctionInputs.load(fn_id)
    out_dir = run_dir / fn_id
    rounds_dir = out_dir / "rounds"

    # ---- Round 0: B3-style attempt ----
    prompt0 = build_b3_prompt(inp)
    resp0 = call_llm_for_body(prompt0, max_tokens=max_tokens)
    body0 = extract_body(resp0)
    verify0 = verify_or_extraction_failed(fn_id, body0)
    write_round(rounds_dir / "round_0", prompt=prompt0, response=resp0, body=body0, verify_payload=verify0)

    history: list[dict] = [
        {
            "round": 0,
            "passed": bool(verify0["passed"]),
            "exit_code": verify0.get("exit_code"),
            "prove_time_sec": verify0.get("prove_time_sec", 0),
            "error_summary": verify0.get("error_summary", ""),
            "extraction_failed": body0 is None,
        }
    ]
    print(f"{fn_id} round 0: passed={verify0['passed']} summary={verify0.get('error_summary','')!r}")

    if verify0["passed"]:
        rounds_to_success = 1
        passed = True
    else:
        passed = False
        previous_body = body0 or ""
        previous_verify = verify0
        rounds_to_success = None

        for k in range(1, feedback_rounds + 1):
            try:
                diagnosis_text = diagnose(
                    signature=inp.signature,
                    spec_block=inp.spec_block,
                    module_context=inp.module_context,
                    failed_body=previous_body,
                    prover_stdout=previous_verify.get("stdout", ""),
                    prover_stderr=previous_verify.get("stderr", ""),
                    max_tokens=16000,
                )
            except Exception as exc:
                diagnosis_text = f"(diagnosis call failed: {type(exc).__name__}: {exc})"

            prompt_k = build_feedback_prompt(inp, previous_body, diagnosis_text)
            resp_k = call_llm_for_body(prompt_k, max_tokens=max_tokens)
            body_k = extract_body(resp_k)
            verify_k = verify_or_extraction_failed(fn_id, body_k)
            write_round(
                rounds_dir / f"round_{k}",
                prompt=prompt_k,
                response=resp_k,
                body=body_k,
                verify_payload=verify_k,
                diagnosis_text=diagnosis_text,
            )

            history.append(
                {
                    "round": k,
                    "passed": bool(verify_k["passed"]),
                    "exit_code": verify_k.get("exit_code"),
                    "prove_time_sec": verify_k.get("prove_time_sec", 0),
                    "error_summary": verify_k.get("error_summary", ""),
                    "extraction_failed": body_k is None,
                }
            )
            print(
                f"{fn_id} round {k}: passed={verify_k['passed']} summary={verify_k.get('error_summary','')!r}"
            )

            if verify_k["passed"]:
                passed = True
                rounds_to_success = k + 1
                break
            previous_body = body_k or previous_body
            previous_verify = verify_k

    summary = {
        "id": fn_id,
        "passed": passed,
        "rounds_to_success": rounds_to_success,
        "feedback_rounds_used": (rounds_to_success - 1) if passed else feedback_rounds,
        "feedback_rounds_budget": feedback_rounds,
        "history": history,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    line = (
        f"{fn_id}: passed={passed} rounds_to_success={rounds_to_success} "
        f"budget={feedback_rounds}"
    )
    (out_dir / "summary.txt").write_text(line + "\n", encoding="utf-8")
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description="Run B6/B7 feedback loop.")
    p.add_argument(
        "--feedback-rounds",
        type=int,
        required=True,
        help="Number of feedback rounds AFTER round 0 (B6=1, B7=3).",
    )
    p.add_argument("--id", help="Function id (omit to run all in registry).")
    p.add_argument("--max-tokens", type=int, default=16000)
    p.add_argument("--run-id", help="Override run directory name (default: timestamp).")
    p.add_argument(
        "--baseline-name",
        default=None,
        help="Output subdirectory name (defaults to b6 or b7 based on rounds).",
    )
    args = p.parse_args()

    if args.feedback_rounds < 1:
        print("--feedback-rounds must be >= 1", file=sys.stderr)
        return 1

    registry = load_registry()
    selected = [f for f in registry if args.id is None or f.id == args.id]
    if not selected:
        print(f"No function matching --id {args.id!r}", file=sys.stderr)
        return 1

    run_id = args.run_id or utc_run_id()
    baseline = args.baseline_name or ("b6" if args.feedback_rounds == 1 else f"b{args.feedback_rounds + 5}")
    run_dir = RESULTS_DIR / run_id / baseline
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for fn in selected:
        try:
            res = run_loop_one(
                fn.id, run_dir, feedback_rounds=args.feedback_rounds, max_tokens=args.max_tokens
            )
            rows.append(
                {
                    "id": fn.id,
                    "passed": res["passed"],
                    "rounds_to_success": res["rounds_to_success"],
                    "feedback_rounds_used": res["feedback_rounds_used"],
                }
            )
        except Exception as exc:
            err = f"{fn.id}: ERROR {type(exc).__name__}: {exc}"
            print(err, file=sys.stderr)
            (run_dir / fn.id).mkdir(parents=True, exist_ok=True)
            (run_dir / fn.id / "error.txt").write_text(str(exc), encoding="utf-8")
            rows.append({"id": fn.id, "passed": False, "error": str(exc)})

    write_baseline_summary(run_dir, baseline.upper(), rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
