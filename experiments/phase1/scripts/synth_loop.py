"""+Diag condition: iterative codegen with prover-error feedback.

Round 0 = +Ctx (Spec + Signature + Module Context, single LLM call).
Round k>0 (feedback round) = LLM call with:
    - the original spec/signature/context
    - the previous body that failed
    - the prover output
    - a diagnosis produced by a separate configured LLM call (see diagnose.py)

Number of feedback rounds is configurable:
    --feedback-rounds 1    -> +Diag-1 (round 0 + 1 feedback round; up to 2 attempts)
    --feedback-rounds 3    -> +Diag-3 (round 0 + 3 feedback rounds; up to 4 attempts)

Metric tracked: rounds_to_success.
    1 = passed on the very first try (no feedback needed)
    k = passed in round k-1 of feedback (i.e., k-th attempt overall)
    failure = exhausted feedback budget without passing.

NOTE: rounds_to_success is NOT the same as Pass@1; do not mix them in tables.
The lowercase `b6`/`b7` paths are internal artifact tags, not paper-facing names.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from body_fence import extract_body
from diagnose import diagnose_with_metadata, trim_prover_output
from metadata_extractor import load_registry
from synth_b3 import build_b3_prompt
from synth_common import (
    DEFAULT_TEMPERATURE,
    FunctionInputs,
    RESULTS_DIR,
    call_llm_for_body_with_metadata,
    make_error_row,
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

RAW_FEEDBACK_PROMPT_TEMPLATE = """\
Your previous attempt at this Move function body failed `aptos move prove`.
Use the raw prover/compiler output below to produce a corrected body. The spec
block must NOT change; only the body changes.

=== Function Signature (do not repeat in your output) ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context (imports, constants, structs, sibling fn signatures) ===
{module_context}

=== Previous Body (failed) ===
{previous_body}

=== Raw Prover Output (stderr + stdout, may be truncated) ===
{prover_output}

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


def build_raw_feedback_prompt(
    inp: FunctionInputs,
    previous_body: str,
    prover_stdout: str,
    prover_stderr: str,
) -> str:
    return RAW_FEEDBACK_PROMPT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
        previous_body=previous_body.strip() or "(empty)",
        prover_output=trim_prover_output(prover_stdout, prover_stderr).strip() or "(empty)",
    )


def write_round(
    round_dir: Path,
    *,
    prompt: str,
    response: str,
    body: str | None,
    verify_payload: dict,
    llm_meta: dict | None = None,
    diagnosis_text: str | None = None,
    diagnosis_llm_meta: dict | None = None,
) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (round_dir / "response.txt").write_text(response, encoding="utf-8")
    (round_dir / "extracted_body.txt").write_text(body or "", encoding="utf-8")
    (round_dir / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")
    if llm_meta is not None:
        (round_dir / "llm_meta.json").write_text(json.dumps(llm_meta, indent=2), encoding="utf-8")
    if diagnosis_text is not None:
        (round_dir / "diagnosis.txt").write_text(diagnosis_text, encoding="utf-8")
    if diagnosis_llm_meta is not None:
        (round_dir / "diagnosis_llm_meta.json").write_text(
            json.dumps(diagnosis_llm_meta, indent=2),
            encoding="utf-8",
        )


def run_loop_one(
    fn_id: str,
    run_dir: Path,
    *,
    feedback_rounds: int,
    max_tokens: int,
    feedback_mode: str = "diagnose",
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    inp = FunctionInputs.load(fn_id)
    out_dir = run_dir / fn_id
    rounds_dir = out_dir / "rounds"

    # ---- Round 0: +Ctx-style attempt ----
    prompt0 = build_b3_prompt(inp)
    resp0, llm_meta0 = call_llm_for_body_with_metadata(
        prompt0,
        max_tokens=max_tokens,
        temperature=DEFAULT_TEMPERATURE,
        provider=provider,
        model=model,
    )
    body0 = extract_body(resp0)
    verify0 = verify_or_extraction_failed(fn_id, body0)
    write_round(
        rounds_dir / "round_0",
        prompt=prompt0,
        response=resp0,
        body=body0,
        verify_payload=verify0,
        llm_meta=llm_meta0,
    )

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
            if feedback_mode == "diagnose":
                try:
                    diagnosis_text, diagnosis_llm_meta = diagnose_with_metadata(
                        signature=inp.signature,
                        spec_block=inp.spec_block,
                        module_context=inp.module_context,
                        failed_body=previous_body,
                        prover_stdout=previous_verify.get("stdout", ""),
                        prover_stderr=previous_verify.get("stderr", ""),
                        max_tokens=32000,
                        provider=provider,
                        model=model,
                    )
                except Exception as exc:
                    diagnosis_text = f"(diagnosis call failed: {type(exc).__name__}: {exc})"
                    diagnosis_llm_meta = {
                        "provider": provider,
                        "model": model,
                        "temperature": DEFAULT_TEMPERATURE,
                        "max_tokens": 32000,
                        "error": str(exc),
                    }

                prompt_k = build_feedback_prompt(inp, previous_body, diagnosis_text)
            elif feedback_mode == "raw":
                diagnosis_text = None
                diagnosis_llm_meta = None
                prompt_k = build_raw_feedback_prompt(
                    inp,
                    previous_body,
                    previous_verify.get("stdout", ""),
                    previous_verify.get("stderr", ""),
                )
            else:
                raise ValueError(f"Unknown feedback_mode: {feedback_mode}")

            resp_k, llm_meta_k = call_llm_for_body_with_metadata(
                prompt_k,
                max_tokens=max_tokens,
                temperature=DEFAULT_TEMPERATURE,
                provider=provider,
                model=model,
            )
            body_k = extract_body(resp_k)
            verify_k = verify_or_extraction_failed(fn_id, body_k)
            write_round(
                rounds_dir / f"round_{k}",
                prompt=prompt_k,
                response=resp_k,
                body=body_k,
                verify_payload=verify_k,
                llm_meta=llm_meta_k,
                diagnosis_text=diagnosis_text,
                diagnosis_llm_meta=diagnosis_llm_meta,
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
        "feedback_mode": feedback_mode,
        "provider": llm_meta0.get("provider"),
        "model": llm_meta0.get("model"),
        "temperature": llm_meta0.get("temperature"),
        "max_tokens": llm_meta0.get("max_tokens"),
        "finish_reason": llm_meta0.get("finish_reason"),
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
    p = argparse.ArgumentParser(description="Run feedback loop.")
    p.add_argument(
        "--feedback-rounds",
        type=int,
        required=True,
        help="Number of feedback rounds AFTER round 0 (+Diag-1=1, +Diag-3=3).",
    )
    p.add_argument("--id", help="Function id (omit to run all in registry).")
    p.add_argument("--ids", help="Comma-separated function ids. Mutually exclusive with --id.")
    p.add_argument(
        "--feedback-mode",
        choices=["diagnose", "raw"],
        default="diagnose",
        help="Feedback source: diagnose uses the Diagnose LLM; raw feeds prover output directly.",
    )
    p.add_argument("--provider", default=None, help="LLM provider: kimi or deepseek (default: env LLM_PROVIDER or kimi).")
    p.add_argument("--model", default=None, help="Provider model override.")
    p.add_argument("--max-tokens", type=int, default=32000)
    p.add_argument("--run-id", help="Override run directory name (default: timestamp).")
    p.add_argument(
        "--baseline-name",
        default=None,
        help="Output subdirectory name (defaults to b6 for +Diag-1 or b7 for +Diag-3).",
    )
    args = p.parse_args()

    if args.feedback_rounds < 1:
        print("--feedback-rounds must be >= 1", file=sys.stderr)
        return 1

    if args.id and args.ids:
        print("--id and --ids are mutually exclusive", file=sys.stderr)
        return 1

    registry = load_registry()
    selected_ids = None
    if args.ids:
        selected_ids = {item.strip() for item in args.ids.split(",") if item.strip()}
    selected = [
        f for f in registry
        if (args.id is None and selected_ids is None)
        or (args.id is not None and f.id == args.id)
        or (selected_ids is not None and f.id in selected_ids)
    ]
    if not selected:
        print(f"No function matching requested id selection", file=sys.stderr)
        return 1

    run_id = args.run_id or utc_run_id()
    if args.baseline_name:
        baseline = args.baseline_name
    elif args.feedback_mode == "raw" and args.feedback_rounds == 1:
        baseline = "raw1"
    elif args.feedback_mode == "raw" and args.feedback_rounds == 3:
        baseline = "raw3"
    elif args.feedback_mode == "raw":
        baseline = f"raw{args.feedback_rounds}"
    elif args.feedback_rounds == 1:
        baseline = "b6"
    elif args.feedback_rounds == 3:
        baseline = "b7"
    else:
        baseline = f"diag{args.feedback_rounds}"
    run_dir = RESULTS_DIR / run_id / baseline
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for fn in selected:
        try:
            res = run_loop_one(
                fn.id,
                run_dir,
                feedback_rounds=args.feedback_rounds,
                max_tokens=args.max_tokens,
                feedback_mode=args.feedback_mode,
                provider=args.provider,
                model=args.model,
            )
            rows.append(
                {
                    "id": fn.id,
                    "passed": res["passed"],
                    "exit_code": res["history"][-1].get("exit_code") if res.get("history") else None,
                    "prove_time_sec": res["history"][-1].get("prove_time_sec", 0) if res.get("history") else 0,
                    "error_summary": res["history"][-1].get("error_summary", "") if res.get("history") else "",
                    "extraction_failed": res["history"][-1].get("extraction_failed", False) if res.get("history") else False,
                    "rounds_to_success": res["rounds_to_success"],
                    "feedback_rounds_used": res["feedback_rounds_used"],
                    "feedback_mode": res["feedback_mode"],
                    "provider": res.get("provider"),
                    "model": res.get("model"),
                    "temperature": res.get("temperature"),
                    "max_tokens": res.get("max_tokens"),
                    "finish_reason": res.get("finish_reason"),
                }
            )
        except Exception as exc:
            err = f"{fn.id}: ERROR {type(exc).__name__}: {exc}"
            print(err, file=sys.stderr)
            (run_dir / fn.id).mkdir(parents=True, exist_ok=True)
            (run_dir / fn.id / "error.txt").write_text(str(exc), encoding="utf-8")
            rows.append(make_error_row(fn.id, exc))

    if args.feedback_mode == "raw":
        condition_label = f"+Raw-{args.feedback_rounds}"
    else:
        condition_label = "+Diag-1" if args.feedback_rounds == 1 else (
            "+Diag-3" if args.feedback_rounds == 3 else f"+Diag-{args.feedback_rounds}"
        )
    write_baseline_summary(
        run_dir,
        condition_label,
        rows,
        artifact_tag=baseline,
        provider=args.provider,
        model=args.model,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=args.max_tokens,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
