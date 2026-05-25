"""B3 baseline: Spec + Signature + Module Context (imports/constants/structs/siblings).

Same Pass@1 setup as B1, but the prompt additionally includes:
    - module imports
    - friend declarations
    - module constants
    - struct definitions in the module
    - sibling function signatures (bodies omitted)

The hypothesis is that supplying this context reduces API/constant misuse
errors that B1 typically produces.
"""
from __future__ import annotations

import argparse
import sys

from metadata_extractor import load_registry
from synth_common import (
    FunctionInputs,
    RESULTS_DIR,
    one_shot_run,
    utc_run_id,
    write_baseline_summary,
)

USER_PROMPT_TEMPLATE = """\
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


def build_b3_prompt(inp: FunctionInputs) -> str:
    return USER_PROMPT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
        module_context=inp.module_context.strip() or "(no extra context)",
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Run B3 (Spec + Signature + Module Context) on one or all functions.")
    p.add_argument("--id", help="Function id (omit to run all in registry).")
    p.add_argument("--provider", default=None, help="LLM provider: kimi or deepseek (default: env LLM_PROVIDER or kimi).")
    p.add_argument("--model", default=None, help="Provider model override.")
    p.add_argument("--max-tokens", type=int, default=32000)
    p.add_argument("--run-id", help="Override run directory name (default: timestamp).")
    args = p.parse_args()

    registry = load_registry()
    selected = [f for f in registry if args.id is None or f.id == args.id]
    if not selected:
        print(f"No function matching --id {args.id!r}", file=sys.stderr)
        return 1

    run_id = args.run_id or utc_run_id()
    run_dir = RESULTS_DIR / run_id / "b3"
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for fn in selected:
        try:
            inp = FunctionInputs.load(fn.id)
            prompt = build_b3_prompt(inp)
            rows.append(
                one_shot_run(
                    fn.id,
                    prompt,
                    run_dir / fn.id,
                    max_tokens=args.max_tokens,
                    provider=args.provider,
                    model=args.model,
                )
            )
        except Exception as exc:
            err = f"{fn.id}: ERROR {type(exc).__name__}: {exc}"
            print(err, file=sys.stderr)
            (run_dir / fn.id).mkdir(parents=True, exist_ok=True)
            (run_dir / fn.id / "error.txt").write_text(str(exc), encoding="utf-8")
            rows.append({"id": fn.id, "passed": False, "error": str(exc)})

    write_baseline_summary(run_dir, "B3", rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
