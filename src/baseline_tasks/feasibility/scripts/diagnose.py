"""Error-diagnosis LLM call for B6/B7 feedback loops.

Given the spec, signature, the body that failed verification, and the prover
output, ask Kimi to:
    1. Classify the failure (compile error / spec violation / API misuse / ...).
    2. Pinpoint the root cause as specifically as possible.
    3. Suggest a concrete fix the codegen step can apply.

We keep the diagnosis short and structured so the next codegen prompt can
ingest it without bloating the context window.
"""
from __future__ import annotations

from kimi_client import chat

SYSTEM_PROMPT = (
    "You are a senior Move/Move-Prover engineer. Given a function specification, "
    "the function body that failed to verify, and the prover output, you produce "
    "a concise structured diagnosis. You never invent file paths or facts not in "
    "the prover output."
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

Produce a diagnosis with EXACTLY these labelled sections, no other prose:

CATEGORY: <one of: compile_error | type_error | api_misuse | constant_misuse |
           missing_abort | extra_abort | postcondition_violation |
           ghost_var_missing | other>

ROOT_CAUSE: <one or two sentences pinpointing why verification failed.>

FIX_INSTRUCTION: <one short paragraph telling the next codegen step what to
change. Be concrete: name the line / clause / API to fix.>
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
        temperature=0.2,
        max_tokens=max_tokens,
        timeout_sec=600,
    )
