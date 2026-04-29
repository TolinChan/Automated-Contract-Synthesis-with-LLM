# Agent Loop Design — for advisor review

> Per Haoxian's 2026-04-28 ask: review the design itself before further engineering tuning, and look for reusable principles. This document is the **plan given to the agent**, expressed as architecture (not implementation). Prompt strings, hyperparameters, and tuning experiments are deliberately excluded.

## 1. Purpose, scope, what this loop is NOT

**Purpose.** Given a function with a frozen formal specification but no body, repeatedly synthesise a body that satisfies the specification according to a formal verifier, using the verifier's output to drive correction.

**Solves.** "LLM produces a function body that an external formal tool will accept."

**Does not solve.**
- Spec synthesis (the spec is an input, never modified by the loop).
- Whole-program synthesis or refactoring (one function at a time, all sibling code stays canonical).
- Test-driven repair (the oracle is a formal prover, not a unit-test runner).
- Discovery of unknown idioms (the diagnoser's idiom library is part of the design, not learned at runtime).

This narrow scope is intentional. It lets the loop have a clean correctness signal (verifier exit code) and a closed search space (function body only).

## 2. Architecture overview

```
   ┌──────────────────────────────────────────┐
   │  Frozen inputs                           │
   │   • signature                            │
   │   • formal spec block                    │
   │   • module context (imports, structs,    │
   │     sibling signatures, ghost decls)     │
   └──────────────────────────────────────────┘
                   │
                   ▼
        ┌───────────────────┐    body_k
        │  Codegen LLM      │ ───────────────┐
        │  (single role:    │                │
        │   produce body)   │                ▼
        └───────────────────┘     ┌─────────────────────┐
                   ▲              │  Splice + Verifier  │
                   │              │  (deterministic     │
            feedback prompt       │   oracle)           │
                   │              └─────────────────────┘
                   │                       │
                   │            pass / fail+stderr+stdout
                   │                       │
                   │              ┌────────┴─────────┐
                   │              │                  │
                   │              ▼                  ▼
                   │           halt              ┌───────────────────┐
                   │           (success)         │  Diagnose LLM     │
                   │                             │  (single role:    │
                   │                             │   classify +      │
                   │                             │   prescribe fix   │
                   │                             │   in idiom terms) │
                   │                             └───────────────────┘
                   │                                      │
                   └──────────────────────────────────────┘
                              diagnosis_k
```

The loop has **two LLM roles** (codegen, diagnose) and **one deterministic oracle** (the verifier). They communicate via typed artifacts, not free-form prose.

## 3. Component contracts

Each component is defined by what it takes in, what it puts out, and what it is *not* allowed to do.

### 3.1 Inputs (frozen for the whole loop)

| Field | Source | Mutability |
|---|---|---|
| function signature | extracted from canonical source | frozen |
| formal spec block (`spec fun ...`) | extracted from canonical `.spec.move` | frozen |
| module context (imports, constants, structs, sibling fn signatures, **module-level ghost var decls**) | extracted from canonical sources | frozen |

**Invariant.** The spec is read-only. No component may modify the spec. This is what makes the loop a *verification-driven* loop rather than a free repair loop.

### 3.2 Codegen step

| | |
|---|---|
| **Input** | frozen inputs + (optional) previous body + (optional) diagnosis |
| **Output** | a function body, fenced in a recognisable marker |
| **Responsibility** | produce Move code that, when spliced into the function, satisfies the spec |
| **NOT its job** | analyse why a previous attempt failed — that is the diagnoser's job |

The codegen role is intentionally narrow. It is given the diagnosis as a *premise to act on*, not an open question to debate.

### 3.3 Verifier step (oracle)

| | |
|---|---|
| **Input** | the LLM body, spliced into a clean copy of the canonical source tree |
| **Output** | exit code, stdout, stderr, wall time, command line |
| **Properties** | deterministic, hermetic (workspace reset before every run), no LLM in the loop |

**Invariant.** The verifier is the **only source of pass/fail truth** in the loop. No LLM is asked "did this verify?". This eliminates LLM-side hallucinated success.

A practical wrinkle: `aptos move prove` swallows compile errors and emits only a JSON summary. We rerun `aptos move compile` on failure to recover the real compiler messages before handing them to the diagnoser. This is a **correctness fix, not a tuning** — the diagnoser's input must reflect what the body actually broke.

### 3.4 Diagnose step

| | |
|---|---|
| **Input** | spec, signature, module context, failed body, prover stdout/stderr |
| **Output** | a typed record: `{ CATEGORY, ROOT_CAUSE, FIX_INSTRUCTION }` |
| **Responsibility** | translate raw prover error → category in a known taxonomy + actionable code-level instruction phrased in **domain idioms** |
| **NOT its job** | rewrite the body. That hands work back to codegen. |

The diagnose role is the **bridge** between the verifier (which speaks at the level of VC failures, line numbers, error codes) and the codegen role (which speaks at the level of code transformations). Without this bridge, raw verifier output is too low-level for codegen to act on, and codegen drifts.

### 3.5 Feedback re-prompt

The feedback prompt is **structured composition**, not narrative:

```
{frozen inputs} + {previous body} + {diagnosis record} + {output format}
```

It does *not* contain the raw prover output; that has already been processed by the diagnoser. This keeps the codegen role's input bounded and on-topic.

## 4. Loop control

| Concern | Choice |
|---|---|
| Budget | `feedback_rounds` (1 → "B6 simple"; 3 → "B7"); plus 1 round-0 attempt |
| Stop on success | first round whose verifier output is `pass` |
| Stop on failure | budget exhausted |
| Stop on extraction failure | body cannot be extracted from response → counts as a failed round |
| Persistence | every round writes `{prompt, response, extracted_body, verify.json, diagnosis}` under `rounds/round_k/` |
| Metrics | `passed`, `rounds_to_success` (1 = round 0; k = k-th attempt), `feedback_rounds_used` |

**Pass@1 vs `rounds_to_success` are not interchangeable.** This is enforced at the metric level: B1/B3 only report Pass@1; B6/B7 only report `rounds_to_success`. They are never aggregated into one column.

## 5. Design principles (why this shape)

### P1 — Two LLM roles, single responsibility each

One LLM is asked to **produce**; another is asked to **analyse**. Never the same call. Reasons:
- A producer asked to also self-correct in the same turn tends to defend its previous output instead of admit the mistake.
- The two roles need different prompts, different examples, and different evaluation. Bundling them hides which role is the bottleneck.
- Empirically (feas_run_02): codegen succeeded on the hardest function when the diagnoser was hand-written, proving codegen capability is sufficient and the diagnoser is the bottleneck. That separability is only visible because the roles are separate.

### P2 — Verifier is the only truth source

LLMs in the loop never decide pass/fail. The verifier exit code is the contract. This eliminates a whole class of false successes. Cost: the verifier must be reliable enough that a `pass` is meaningful — for `aptos move prove` this holds; for an LLM-judged "looks correct" it would not.

### P3 — Spec is invariant; body is the only edit surface

The loop's degree of freedom is **one function body**. This is small enough that:
- Splicing is mechanical (regex on `fun <name>`, brace-matched body replacement).
- Workspace reset between runs is cheap (full re-copy from canonical sources).
- The loop cannot accidentally "succeed" by weakening the spec.

### P4 — Domain bridge ≠ generic error prose

The diagnoser does not just summarise prover output; it must classify into a **taxonomy of failure modes** and prescribe fixes in **domain idioms** (for Move Prover: ghost-var spec updates, while-header invariant placement, overflow `assume`, etc.). Without this, the diagnoser becomes a verbose error reformatter and the codegen role gets no actionable guidance. Empirically this is exactly what the auto-diagnoser failed to do in feas_run_02 and what the manual diagnosis got right.

### P5 — Round-level artifact persistence

Every round writes its prompt, its model response, the extracted body, the verify result, and (for k ≥ 1) the diagnosis. The reasons:
- The loop is fully replayable post-hoc — a passing round can be reproduced without rerunning the LLM.
- Failure analysis after a run is a deterministic, file-based exercise, not a memory-based one.
- Comparing variants (B1 vs B3 vs B6 vs B7) is a directory diff, not a re-run.

## 6. Abstractions — what generalises beyond Move Prover

These are the parts of the design that I think reuse cleanly to other "LLM + formal/automated checker" tasks (e.g., Solidity + SMT, Rust + Kani, OCaml + Why3, even strongly-typed code + a typechecker).

### A1 — Verifier-as-oracle pattern

The shape **{ frozen-spec inputs → LLM produces edit → deterministic checker → typed feedback → LLM revises }** is reusable whenever:
- the checker is decisive (pass/fail) and reasonably fast,
- the edit surface is bounded (a function body, not a whole program),
- the spec is in a frozen form the LLM can read.

This is not Move-specific.

### A2 — Two-role separation (producer vs diagnoser)

Reusable as a general agent shape: **don't ask one LLM call to both produce and self-critique**. Make the diagnoser a separate prompt with its own contract. The interface between them — a typed `{category, root_cause, fix_instruction}` record — is reusable as a generic "feedback envelope".

### A3 — Idiom library as the diagnose backbone

The single most domain-specific component is the diagnoser's **idiom library**: the set of failure modes + canonical fixes the diagnoser knows how to recognise. For Move Prover we have ~3 (ghost-var update, while-header invariants, overflow assume). For another verifier the library would be different but the *pattern* — "diagnoser bridges raw error to a finite taxonomy of code-level fixes" — is the same.

This suggests a useful abstraction:

```
DiagnoserContract = (
    classify : (raw_errors, body, spec) -> Category ∈ Taxonomy,
    prescribe: (Category, body, spec) -> FixInstruction,
)
Taxonomy is a domain-supplied finite set with worked examples.
```

Building a new domain target ≈ specifying its `Taxonomy` and worked examples; the loop architecture stays.

### A4 — Splice-and-reset workspace pattern

A canonical source tree, never mutated; a workspace tree, reset before every verify. This is reusable for any "edit one function in a large codebase, run a heavy tool over the whole package" workflow. It removes cross-run contamination and is cheaper than a containerised sandbox.

### A5 — Pass@1 vs rounds_to_success as orthogonal metrics

This metric distinction is not Move-specific. Any "n-shot with feedback" agent loop should report both, separately. Mixing them obscures whether the gain comes from the model or from the loop.

## 7. Risks the design has not yet addressed

These are open and worth advisor input before more engineering.

**R1 — The diagnoser's idiom library has to be authored.** Right now it is partially baked into the diagnose prompt. If a real test set exposes a new failure mode not in the taxonomy, the loop will fail in the same way as the unaided LLM. The library is a maintenance burden that scales with the verifier's surface area.

**R2 — The diagnoser may be the only non-trivially-prompt-engineered component.** This makes the experimental story "is the loop good?" entangle with "is our diagnose prompt good?". We have not yet found a clean ablation that separates loop architecture from diagnoser quality.

**R3 — Manual diagnosis is the strongest result we have.** That proves the *codegen+verifier* halves of the loop are sound; it does not yet prove the *automated diagnoser* half is. The loop is currently architecturally complete but only **half empirically validated**.

**R4 — The 5-function set is too small to claim generality.** The minimal feasibility test was about *existence proof* (can the method work at all?). Scaling to a benchmark requires more functions across more spec patterns; whether the loop architecture scales without per-function tuning is an open question.

**R5 — One-function-at-a-time scope is a real assumption.** Functions that depend on each other's correctness (mutual recursion, helper-function lemmas) currently fall outside the loop. A multi-function variant would require richer state than just "current body".

## 8. Open design questions for advisor

1. **Diagnoser-library status.** Should the idiom library be (a) inlined in the diagnose prompt, (b) a separate retrievable knowledge base, (c) learned from past failure traces? (a) is what we have; (b)/(c) would change the architecture.
2. **Two-role vs single-role ablation.** Worth running a controlled "single LLM does both" baseline to confirm P1 is empirically meaningful, not just intuitive?
3. **Verifier granularity.** `aptos move prove` is whole-package. For a body that breaks one VC, we still pay for the whole package's other VCs. Is per-function verification (if we can isolate it) worth the engineering cost, or is "whole package, filtered by module" good enough?
4. **Metric reporting.** Beyond Pass@1 / `rounds_to_success`, do we want a "diagnosis quality" intermediate metric — e.g., did the diagnoser correctly classify the failure category — independent of whether codegen converged?
5. **Generalisation target.** When we go beyond Move Prover, which target do we want? (Rust + Kani, Solidity + SMTChecker, …) Choice affects which abstraction layer (A1–A5) gets stress-tested first.

## 9. What this document is *not*

- Not a prompt-engineering report. We are deferring tuning of codegen/diagnose prompts until the design above is signed off.
- Not a results document. Empirical results are in `results/feas_run_02/RESULTS.md`.
- Not an implementation guide. Implementation lives in `scripts/`; this document is at one level above.
