"""Error-diagnosis LLM call for B6/B7 feedback loops.

Given the spec, signature, the body that failed verification, and the prover
output, ask the configured LLM to:
    1. Classify the failure (compile error / spec violation / API misuse / ...).
    2. Pinpoint the root cause as specifically as possible.
    3. Suggest a concrete fix the codegen step can apply.

We keep the diagnosis short and structured so the next codegen prompt can
ingest it without bloating the context window.
"""
from __future__ import annotations

from llm_client import chat

SYSTEM_PROMPT = (
    "You are a senior Move/Move-Prover engineer. Given a function specification, "
    "the function body that failed to verify, and the prover output, you produce "
    "a concise structured diagnosis. You never invent file paths or facts not in "
    "the prover output. You are familiar with Move-Prover-specific idioms — "
    "ghost variable spec updates, while-header loop invariants, and overflow "
    "assumes — and you recognise their failure signatures in prover output."
)

USER_PROMPT_TEMPLATE = """\
A Move function body failed `aptos move prove`. Diagnose the failure.

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context (imports, constants, structs, sibling fn signatures) ===
{module_context}

=== Failed Body (the candidate that did not verify) ===
{failed_body}

=== Prover Output (stderr + stdout, may be truncated) ===
{prover_output}

=== Move-Prover Idiom Checklist ===
Before producing the FIX_INSTRUCTION, scan the spec / failed body / prover output
for the symptoms below. Whenever a symptom matches, your fix MUST instruct the
codegen step to use the exact Move-Prover idiom shown. Do NOT invent these
idioms when no symptom matches — only apply them when the evidence supports it.

(1) Ghost-variable spec updates
    Symptom: the spec block references a module-level ghost var (typically
        named `ghost_*`) inside `ensures` / `invariant`, AND the failed body
        either does not initialise that ghost var at all, or initialises it
        with a regular Move `let` binding (e.g. `let ghost_x = ...;`). The
        prover may report a postcondition or invariant failure that
        references the ghost var.
    Fix idiom (inside the body, NOT the spec):
        spec {{ update ghost_x = <expression>; }};
    Forbidden: `let ghost_x = ...;` is a regular Move binding and does NOT
    update the spec ghost variable. Replace it with the `spec {{ update ... }}`
    form. Place the spec-update block immediately after the `let` bindings
    that compute the value being copied in.

(2) While-loop invariant placement / missing invariants
    Symptom: ANY of the following:
        - The prover output contains the message "Loop invariants must be
          declared at the beginning of the loop header in a consecutive
          sequence" (the explicit case — invariants exist but are placed
          inside the while body instead of the while-header).
        - The prover reports "global memory invariant does not hold" or any
          ensures/invariant failure whose trace mentions "enter loop" and
          "havocked and reassigned" (the implicit case — the body has a
          `while` that mutates state, but no `spec {{ invariant ... }}` block
          at all, so the prover loses information across iterations and
          cannot prove module-level / global invariants are preserved).
        - The failed body has `spec {{ invariant ... }}` inside the `while`
          BODY rather than inside the while-header expression.
    Fix idiom (rewrite the loop):
        while ({{
            spec {{
                invariant <inv1>;
                invariant <inv2>;
                ...
            }};
            <loop_condition>
        }}) {{
            <loop_body_without_any_spec_invariant_block>
        }}
    The `spec {{ invariant ... }}` block must be the FIRST thing inside the
    while-header expression, before the loop condition. When the implicit
    case applies (no invariants exist at all), the FIX_INSTRUCTION must
    list the SPECIFIC invariants to declare — at minimum:
        - the length of any vector being iterated over (so out-of-bounds
          reasoning is preserved);
        - the invariance of any spec ghost variable across the loop;
        - any inequality / ordering on the loop counter (e.g. `f <= f_len`).

    HARD CONSTRAINT — `old(...)` is FORBIDDEN inside `spec {{ invariant ... }}`
    blocks placed in a while-header. Move Prover rejects these with
    "invalid old(..) expression in inline spec block". Inline spec blocks may
    only reference current state, function parameters, and ghost vars. To
    express "X has not changed since loop entry":
        - prefer comparing to a `let` snapshot taken before the loop, OR
        - use a ghost var bound via `spec {{ update ghost_x = ...; }};`
          BEFORE the loop, then the invariant reads `ghost_x == <expr>`.
    Keep loop invariants MINIMAL: bound the counter, bound vector lengths,
    pin ghost vars. Do NOT try to encode the entire postcondition inside
    the loop invariant.

    Worked example (this is the canonical fix for a function whose body
    increments performance counters in a loop and whose ensures references
    `ghost_proposer_idx`):

        // body, immediately after the borrow_global_mut:
        let validator_perf = borrow_global_mut<ValidatorPerformance>(@aptos_framework);
        spec {{ update ghost_proposer_idx = proposer_index; }};
        let validators = &mut validator_perf.validators;
        // ... if-block on proposer_index ...
        let len = vector::length(&failed_proposer_indices);
        let i = 0;
        while ({{
            spec {{
                invariant 0 <= i && i <= vector::length(failed_proposer_indices);
                invariant ghost_proposer_idx == proposer_index;
            }};
            i < len
        }}) {{
            let idx = *vector::borrow(&failed_proposer_indices, i);
            if (idx < vector::length(validators)) {{
                let validator = vector::borrow_mut(validators, idx);
                validator.failed_proposals = validator.failed_proposals + 1;
            }};
            i = i + 1;
        }};

    Note how the example uses NO `old(...)` in the while-header; ghost vars
    and a bound on `i` are sufficient.

(3) Overflow `assume` before bounded arithmetic
    Symptom: the prover times out (e.g. "verification out of resources" or
        "timeout"), OR reports an overflow / abort VC at a `+= 1`, `= x + 1`
        or similar bounded-integer arithmetic line. This is especially likely
        when the spec does NOT have an `aborts_if X + 1 > MAX_U64` clause
        (i.e. the spec assumes overflow cannot happen).
    Fix idiom (immediately before each `+= 1` on a u64):
        spec {{ assume <lhs> + 1 <= MAX_U64; }};
        <lhs> = <lhs> + 1;
    Use `MAX_U8` / `MAX_U64` / `MAX_U128` matching the integer width. Apply
    to every increment site, not just the first one.

Produce a diagnosis with EXACTLY these labelled sections, no other prose:

CATEGORY: <one of: compile_error | type_error | api_misuse | constant_misuse |
           missing_abort | extra_abort | postcondition_violation |
           ghost_var_missing | loop_invariant_placement |
           overflow_assume_missing | other>

ROOT_CAUSE: <one or two sentences pinpointing why verification failed. If
multiple idiom symptoms apply, list each one.>

FIX_INSTRUCTION: <one short paragraph telling the next codegen step what to
change. Be concrete: name the line / clause / API to fix. When an idiom from
the checklist applies, quote the exact `spec {{ ... }}` snippet to insert and
say where to place it. If multiple idioms apply, list them all — the codegen
step will apply every fix in a single body rewrite.>
"""

_PROVER_OUTPUT_TAIL_LIMIT = 4000


def trim_prover_output(stdout: str, stderr: str) -> str:
    """Concatenate stderr+stdout and keep only the last N chars, since prover
    outputs can be very long."""
    blob = (stderr or "") + ("\n" + stdout if stdout else "")
    if len(blob) <= _PROVER_OUTPUT_TAIL_LIMIT:
        return blob
    return f"...(truncated head)...\n{blob[-_PROVER_OUTPUT_TAIL_LIMIT:]}"


def diagnose(
    *,
    signature: str,
    spec_block: str,
    module_context: str,
    failed_body: str,
    prover_stdout: str,
    prover_stderr: str,
    max_tokens: int = 4000,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    prompt = USER_PROMPT_TEMPLATE.format(
        signature=signature.strip(),
        spec_block=spec_block.strip(),
        module_context=module_context.strip() or "(none)",
        failed_body=failed_body.strip() or "(empty)",
        prover_output=trim_prover_output(prover_stdout, prover_stderr),
    )
    return chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider=provider,
        model=model,
        temperature=0.2,
        max_tokens=max_tokens,
        timeout_sec=600,
    )
