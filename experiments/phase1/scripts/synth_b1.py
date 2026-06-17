"""Zero-shot condition: Spec -> Function Body synthesis (Pass@1).

Inputs to LLM (per function):
    - the function's spec block
    - the function's signature

The LLM is asked to emit only the body, wrapped in <<<BODY ... BODY>>>.
The body is then spliced into a workspace copy of aptos-framework and
`aptos move prove --filter <module>` is run.

Per-function artifacts: prompt.txt, response.txt, extracted_body.txt,
verify.json, summary.txt under results/<run-id>/b1/<func_id>/.

Aggregate: results/<run-id>/b1/summary.json.
The lowercase `b1` path is an internal artifact tag, not the paper-facing name.
"""
from __future__ import annotations

import argparse
import sys

from metadata_extractor import load_registry
from synth_common import (
    DEFAULT_TEMPERATURE,
    FunctionInputs,
    RESULTS_DIR,
    make_error_row,
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
- Use only standard built-ins, the items implied by the signature, or items declared in the
  same module. (You are NOT given module context in this condition.)
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


def build_b1_prompt(inp: FunctionInputs) -> str:
    return USER_PROMPT_TEMPLATE.format(
        signature=inp.signature.strip(),
        spec_block=inp.spec_block.strip(),
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Run Zero-shot (internal tag: b1) on one or all functions.")
    p.add_argument("--id", help="Function id (omit to run all in registry).")
    p.add_argument("--ids", help="Comma-separated function ids. Mutually exclusive with --id.")
    p.add_argument("--provider", default=None, help="LLM provider: kimi or deepseek (default: env LLM_PROVIDER or kimi).")
    p.add_argument("--model", default=None, help="Provider model override.")
    p.add_argument("--max-tokens", type=int, default=32000)
    p.add_argument("--run-id", help="Override run directory name (default: timestamp).")
    args = p.parse_args()

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
        print("No function matching requested id selection", file=sys.stderr)
        return 1
    requested_ids = ({args.id} if args.id else selected_ids) or set()
    missing_ids = requested_ids - {f.id for f in selected}
    if missing_ids:
        print(f"Unknown function id(s): {', '.join(sorted(missing_ids))}", file=sys.stderr)
        return 1

    run_id = args.run_id or utc_run_id()
    run_dir = RESULTS_DIR / run_id / "b1"
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for fn in selected:
        try:
            inp = FunctionInputs.load(fn.id)
            prompt = build_b1_prompt(inp)
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
            rows.append(make_error_row(fn.id, exc))

    write_baseline_summary(
        run_dir,
        "Zero-shot",
        rows,
        artifact_tag="b1",
        provider=args.provider,
        model=args.model,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=args.max_tokens,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
