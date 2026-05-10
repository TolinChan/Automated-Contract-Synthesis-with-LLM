"""Standalone model-comparison runner for stake_update_perf.

Runs B1 (zero-shot) and, on failure, B3 (+module context) on a single function
across arbitrary LLM providers (OFOX or Kimi). Results are written to a
directory structure compatible with feas_run_02 artifacts.

Usage:
    # OFOX — Claude Opus 4.7
    python run_model_cmp_stake.py --model anthropic/claude-opus-4.7 --output-dir ../../results/model_cmp_20250508/claude

    # OFOX — GPT 5.5
    python run_model_cmp_stake.py --model openai/gpt-5.5 --output-dir ../../results/model_cmp_20250508/gpt

    # Kimi baseline (for direct comparison)
    python run_model_cmp_stake.py --model kimi-for-coding --provider kimi --output-dir ../../results/model_cmp_20250508/kimi

    # Run B1 only
    python run_model_cmp_stake.py --model anthropic/claude-opus-4.7 --b1-only --output-dir ../../results/model_cmp_20250508/claude_b1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports from the existing feasibility framework (read-only reuse)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

from body_fence import extract_body
from metadata_extractor import FEASIBILITY_DIR
from synth_common import FunctionInputs, SYSTEM_PROMPT, utc_run_id
from verify_synth import verify

# ---------------------------------------------------------------------------
# Prompt templates (copied from synth_b1.py / synth_b3.py for independence)
# ---------------------------------------------------------------------------

B1_PROMPT_TEMPLATE = """\
Task: Write the body of a Move function so that it satisfies the formal specification.

The body must, when placed between the function's outer braces and verified with
`aptos move prove`, satisfy EVERY clause of the spec block — `aborts_if`,
`ensures`, `requires`, `modifies`, etc.

Constraints:
- Move (Aptos dialect) source code only — no English commentary inside the body.
- Use only standard built-ins, the items implied by the signature, or items declared in the
  same module. (You are NOT given module context in this baseline.)
- Do NOT modify the spec block — your output is the function BODY, not the whole function.

=== Function Signature (do not repeat in your output) ===
{signature}

=== Formal Specification ===
{spec_block}

=== Output format ===
Return ONLY the function body, with the wrapper markers shown below. The body is the
code that would go between the outer `{{` and `}}` of the function. Do not include the
braces themselves, do not repeat the signature, do not add prose.

<<<BODY
... your Move code here ...
BODY>>>
"""

B3_PROMPT_TEMPLATE = """\
Task: Write the body of a Move function so that it satisfies the formal specification.

The body must, when placed between the function's outer braces and verified with
`aptos move prove`, satisfy EVERY clause of the spec block — `aborts_if`,
`ensures`, `requires`, `modifies`, etc.

Constraints:
- Move (Aptos dialect) source code only — no English commentary inside the body.
- You may use anything declared in the Module Context section below (imports, constants,
  structs, sibling functions). Cross-module APIs not listed there are not provided;
  prefer in-module APIs when the spec allows.
- Do NOT modify the spec block — your output is the function BODY only.

=== Function Signature (do not repeat in your output) ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context (imports, constants, structs, sibling function signatures) ===
{module_context}

=== Output format ===
Return ONLY the function body, with the wrapper markers shown below. The body is the
code that would go between the outer `{{` and `}}` of the function. Do not include the
braces themselves, do not repeat the signature, do not add prose.

<<<BODY
... your Move code here ...
BODY>>>
"""

# ---------------------------------------------------------------------------
# B6 feedback loop templates (copied from diagnose.py / synth_loop.py)
# ---------------------------------------------------------------------------

DIAGNOSIS_SYSTEM_PROMPT = (
    "You are a senior Move/Move-Prover engineer. Given a function specification, "
    "the function body that failed to verify, and the prover output, you produce "
    "a concise structured diagnosis. You never invent file paths or facts not in "
    "the prover output. You are familiar with Move-Prover-specific idioms — "
    "ghost variable spec updates, while-header loop invariants, and overflow "
    "assumes — and you recognise their failure signatures in prover output."
)

DIAGNOSIS_PROMPT_TEMPLATE = """\
A Move function body failed `aptos move prove`. Diagnose the failure.

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Failed Body ===
{failed_body}

=== Prover Output ===
{prover_output}

=== Move-Prover Idiom Checklist ===
Before producing the FIX_INSTRUCTION, scan for these symptoms:

(1) Ghost-variable spec updates
    Symptom: spec references module-level ghost var (ghost_*) inside ensures/invariant,
    and body either does not initialise it or uses regular `let` binding.
    Fix idiom: spec {{ update ghost_x = <expression>; }};

(2) While-loop invariant placement / missing invariants
    Symptom: "Loop invariants must be declared at the beginning of the loop header"
    or "global memory invariant does not hold" with loop trace.
    Fix idiom: while ({{ spec {{ invariant ... }}; <condition> }}) {{ ... }}
    NEVER use `old(...)` inside while-header spec blocks.

(3) Overflow `assume` before bounded arithmetic
    Symptom: timeout or overflow VC at `+= 1` / `= x + 1`.
    Fix idiom: spec {{ assume <lhs> + 1 <= MAX_U64; }}; before each increment.

Produce a diagnosis with EXACTLY these labelled sections:

CATEGORY: <compile_error | type_error | api_misuse | postcondition_violation | ghost_var_missing | loop_invariant_placement | overflow_assume_missing | other>

ROOT_CAUSE: <one or two sentences. If multiple idiom symptoms apply, list each one.>

FIX_INSTRUCTION: <concrete fix instructions. When an idiom applies, quote the exact spec {{ ... }} snippet and where to place it.>
"""

FEEDBACK_PROMPT_TEMPLATE = """\
Your previous attempt at this Move function body failed `aptos move prove`.
Use the diagnosis to produce a corrected body. The spec block must NOT change;
only the body changes.

=== Function Signature (do not repeat in your output) ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Previous Body (failed) ===
{previous_body}

=== Diagnosis ===
{diagnosis}

=== Output format ===
Return ONLY the corrected function body wrapped in the markers below.
Do not include the function signature, the surrounding braces, or any prose.

<<<BODY
... your corrected Move code here ...
BODY>>>
"""


# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_ofox_key() -> str:
    env_path = _project_root() / ".env"
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key in ("OFOX_API_KEY", "OFOXAI_API_KEY") and val:
                return val
    env_key = os.environ.get("OFOX_API_KEY") or os.environ.get("OFOXAI_API_KEY")
    if env_key:
        return env_key
    raise RuntimeError("OFOX API key not found. Set OFOX_API_KEY in .env or environment.")


def _load_kimi_key() -> str:
    env_path = _project_root() / ".env"
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key == "KIMI_API_KEY" and val:
                return val
    env_key = os.environ.get("KIMI_API_KEY")
    if env_key:
        return env_key
    # Fallback to kimiapi.txt
    txt_path = _project_root() / "kimiapi.txt"
    if txt_path.is_file():
        return txt_path.read_text(encoding="utf-8").strip()
    raise RuntimeError("Kimi API key not found. Set KIMI_API_KEY in .env or environment.")


def call_ofox(messages: list[dict], model: str, max_tokens: int, temperature: float = 0.2) -> str:
    """Non-streaming OFOX API call."""
    api_url = "https://api.ofox.ai/v1/chat/completions"
    key = _load_ofox_key()
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
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
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OFOX API error {exc.code}: {err_body}") from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected OFOX response structure: {payload}") from exc


def call_kimi(messages: list[dict], model: str, max_tokens: int, temperature: float = 0.2) -> str:
    """Kimi API call (non-streaming to match interface)."""
    api_url = "https://api.kimi.com/coding/v1/chat/completions"
    key = _load_kimi_key()
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key.strip()}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "claude-cli/2.0.0 (model-comparison)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Kimi API error {exc.code}: {err_body}") from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Kimi response structure: {payload}") from exc


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def _trim_prover_output(stdout: str, stderr: str, limit: int = 4000) -> str:
    blob = (stderr or "") + ("\n" + stdout if stdout else "")
    if len(blob) <= limit:
        return blob
    return f"...(truncated head)...\n{blob[-limit:]}"


def run_baseline(
    fn_id: str,
    prompt: str,
    out_dir: Path,
    *,
    model: str,
    provider: str,
    max_tokens: int,
) -> dict:
    """Single LLM call + verify. Writes artifacts. Returns result dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    if provider == "ofox":
        response = call_ofox(messages, model=model, max_tokens=max_tokens)
    elif provider == "kimi":
        response = call_kimi(messages, model=model, max_tokens=max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider!r}")

    (out_dir / "response.txt").write_text(response, encoding="utf-8")

    body = extract_body(response)
    (out_dir / "extracted_body.txt").write_text(body or "", encoding="utf-8")

    if body is None:
        verify_payload = {
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
    else:
        result = verify(fn_id, body, timeout_sec=600)
        verify_payload = result.to_json()

    (out_dir / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")

    line = (
        f"{fn_id}: passed={verify_payload['passed']} "
        f"exit={verify_payload['exit_code']} "
        f"time={verify_payload.get('prove_time_sec', 0)}s "
        f"summary={verify_payload.get('error_summary', '')!r}"
    )
    (out_dir / "summary.txt").write_text(line + "\n", encoding="utf-8")
    print(line)

    return {
        "id": fn_id,
        "passed": bool(verify_payload["passed"]),
        "exit_code": verify_payload["exit_code"],
        "prove_time_sec": verify_payload.get("prove_time_sec", 0),
        "error_summary": verify_payload.get("error_summary", ""),
        "extraction_failed": body is None,
        "body": body,
        "verify_payload": verify_payload,
    }


def run_diagnosis(
    inp: FunctionInputs,
    failed_body: str,
    verify_payload: dict,
    *,
    model: str,
    provider: str,
    max_tokens: int = 32000,
) -> str:
    """Ask LLM to diagnose a failed verification."""
    prompt = DIAGNOSIS_PROMPT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(none)",
        failed_body=failed_body.strip() or "(empty)",
        prover_output=_trim_prover_output(
            verify_payload.get("stdout", ""),
            verify_payload.get("stderr", ""),
        ),
    )
    messages = [
        {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    if provider == "ofox":
        return call_ofox(messages, model=model, max_tokens=max_tokens)
    elif provider == "kimi":
        return call_kimi(messages, model=model, max_tokens=max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider!r}")


def run_feedback_round(
    fn_id: str,
    inp: FunctionInputs,
    previous_body: str,
    diagnosis: str,
    out_dir: Path,
    *,
    model: str,
    provider: str,
    max_tokens: int,
) -> dict:
    """One feedback round: build feedback prompt, call LLM, verify."""
    prompt = FEEDBACK_PROMPT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
        previous_body=previous_body.strip() or "(empty)",
        diagnosis=diagnosis.strip() or "(no diagnosis available)",
    )
    result = run_baseline(
        fn_id, prompt, out_dir,
        model=model, provider=provider, max_tokens=max_tokens,
    )
    (out_dir / "diagnosis.txt").write_text(diagnosis, encoding="utf-8")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Model comparison on stake_update_perf")
    p.add_argument("--model", required=True, help="Model ID (e.g. anthropic/claude-opus-4.7)")
    p.add_argument("--provider", default="ofox", choices=["ofox", "kimi"], help="API provider")
    p.add_argument("--output-dir", required=True, help="Directory to write results")
    p.add_argument("--max-tokens", type=int, default=16000)
    p.add_argument("--b1-only", action="store_true", help="Only run B1 baseline")
    p.add_argument("--feedback-rounds", type=int, default=0, help="Feedback rounds after B3 (B6=1, B7=3)")
    p.add_argument("--run-id", help="Override run directory name segment")
    args = p.parse_args()

    fn_id = "stake_update_perf"
    inp = FunctionInputs.load(fn_id)

    out_base = Path(args.output_dir)
    if args.run_id:
        out_base = out_base / args.run_id

    results: list[dict] = []

    # --- B1 ---
    print(f"\n=== B1 (zero-shot) — {args.model} ===")
    b1_prompt = B1_PROMPT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
    )
    b1_result = run_baseline(
        fn_id, b1_prompt, out_base / "b1" / fn_id,
        model=args.model, provider=args.provider, max_tokens=args.max_tokens,
    )
    results.append({"baseline": "B1", **b1_result})

    if b1_result["passed"]:
        print("B1 passed — stopping early.")
    elif args.b1_only:
        print("B1 failed — --b1-only set, stopping.")
    else:
        # --- B3 ---
        print(f"\n=== B3 (+module context) — {args.model} ===")
        b3_prompt = B3_PROMPT_TEMPLATE.format(
            signature=inp.signature.strip(),
            spec_block=inp.spec_block.strip(),
            module_context=inp.module_context.strip() or "(no extra context)",
        )
        b3_result = run_baseline(
            fn_id, b3_prompt, out_base / "b3" / fn_id,
            model=args.model, provider=args.provider, max_tokens=args.max_tokens,
        )
        results.append({"baseline": "B3", **b3_result})

        if b3_result["passed"]:
            print("B3 passed — stopping early.")
        elif args.feedback_rounds < 1:
            print("B3 failed — no feedback rounds requested. Stopping.")
        else:
            # --- B6/B7 feedback loop ---
            previous_body = b3_result.get("body") or ""
            previous_verify = b3_result.get("verify_payload", {})
            passed = False
            rounds_to_success = None

            for k in range(1, args.feedback_rounds + 1):
                print(f"\n=== Feedback round {k}/{args.feedback_rounds} — {args.model} ===")
                try:
                    diagnosis = run_diagnosis(
                        inp, previous_body, previous_verify,
                        model=args.model, provider=args.provider, max_tokens=32000,
                    )
                except Exception as exc:
                    diagnosis = f"(diagnosis call failed: {type(exc).__name__}: {exc})"
                    print(diagnosis, file=sys.stderr)

                fb_result = run_feedback_round(
                    fn_id, inp, previous_body, diagnosis,
                    out_base / f"b3_fb{k}" / fn_id,
                    model=args.model, provider=args.provider, max_tokens=args.max_tokens,
                )
                results.append({"baseline": f"B3_FB{k}", **fb_result})

                if fb_result["passed"]:
                    passed = True
                    rounds_to_success = k
                    print(f"Feedback round {k} passed — stopping.")
                    break

                previous_body = fb_result.get("body") or previous_body
                previous_verify = fb_result.get("verify_payload", previous_verify)

            if not passed:
                print(f"All {args.feedback_rounds} feedback rounds exhausted — failed.")

    # Write aggregate summary
    summary = {
        "model": args.model,
        "provider": args.provider,
        "function_id": fn_id,
        "max_tokens": args.max_tokens,
        "feedback_rounds": args.feedback_rounds,
        "results": results,
    }
    out_base.mkdir(parents=True, exist_ok=True)
    (out_base / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary written to {out_base / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
