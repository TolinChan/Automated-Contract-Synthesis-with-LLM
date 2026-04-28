# Feasibility Test — Run feas_run_02

Model: kimi-for-coding (reasoning model, accessed via Kimi `/coding/v1/chat/completions`).
Verifier: aptos move prove (Aptos CLI 9.1.0, Boogie 3.5.1, Z3 4.13.0), 40s per VC global timeout.
Workspace: cloned aptos-framework at `E:\src\move-poc\synth\framework_workspace\`, full reset from canonical before each verify.

## Phase A — 4 baselines × 5 functions

| # | Function | Source | Spec complexity | B1 | B3 | B6 (rounds_to_success) | B7 (rounds_to_success) |
|---|----------|--------|-----------------|----|----|------------------------|------------------------|
| 1 | chain_id_get          | chain_id.move        | trivial (1 line, no abort) | PASS (15.6s) | PASS (16.4s) | PASS, r=1 | PASS, r=1 |
| 2 | chain_id_initialize   | chain_id.move        | simple+ (signer + abort_if) | PASS (16.0s) | PASS (16.8s) | PASS, r=1 | PASS, r=2 |
| 3 | coin_extract          | coin.move            | medium (struct mutate + abort_if) | PASS (27.6s) | PASS (22.3s) | PASS, r=1 | PASS, r=1 |
| 4 | block_initialize      | block.move           | medium-high (~25 lines) | PASS (42.2s) | PASS (39.1s) | PASS, r=1 | PASS, r=1 |
| 5 | stake_update_perf     | stake.move           | complex (ghost vars + while/invariant + overflow assumes, ~50 lines) | **FAIL** | **FAIL** | **FAIL** (r=1+r=2) | (in progress; see below) |

**Headline:** 4/5 PASS for all four baselines. The single failing case is the most complex spec (`update_performance_statistics`).

`r` is `rounds_to_success` (1 = passed on first attempt, no feedback needed). For B7 chain_id_initialize, r=2 means the round 0 attempt failed and the body was corrected by the round 1 feedback. (The first time this same function ran in B6 it passed in round 0 — temperature 0.2 is non-zero, so per-call variation can move the needle one round either way.)

## Why stake_update_perf fails across all baselines

The reference body for `update_performance_statistics` requires three Move-Prover-specific patterns that the model never produces unaided:

1. **Spec ghost-variable updates inside the body**: `spec { update ghost_proposer_idx = proposer_index; update ghost_valid_perf = validator_perf; };`. These are *not* regular `let` bindings; they update module-level ghost vars referenced by the spec's `ensures` clause. The LLM consistently tries `let ghost_proposer_idx = proposer_index;`, which compiles but does not connect to the spec.

2. **Loop invariants embedded in the while header, not the loop body**: The Move Prover requires the form
   ```
   while ({ spec { invariant ...; invariant ...; }; cond }) { body }
   ```
   The LLM produces `while (cond) { spec { invariant ... }; body }`, which the prover rejects with `Loop invariants must be declared at the beginning of the loop header in a consecutive sequence`.

3. **Overflow-safety assumes around `+= 1`**: `spec { assume validator.successful_proposals + 1 <= MAX_U64 };`. Without these the prover generates an overflow VC that times out at 40s.

## Why the diagnose call did not rescue stake_update_perf

The independent diagnose LLM call (run between attempts in B6/B7) misclassified the failure on round 0 as `ghost_var_missing` and recommended *"Replace every occurrence of `ghost_proposer_idx` in the `ensures` clause with `proposer_index`, or add a spec-local binding ..."* — but the prompt forbids modifying the spec, and the actual fix is a `spec { update ... }` block in the body. The next codegen call did add `let ghost_proposer_idx = proposer_index;` (a regular Move binding, not a spec update), and additionally placed loop invariants in the wrong location (inside the loop body, triggering the prover's invariant-placement error). Round 1's prover error was *different* from round 0's, so progress was being made — but in a single feedback round B6 cannot converge on all three Move-Prover idioms simultaneously, and B7 (3 rounds) likely cannot either without the diagnose call having domain-specific knowledge of these idioms.

## Per-attempt prover errors for stake_update_perf (B6)

| Round | Body shape | Prover outcome |
|-------|------------|----------------|
| 0 | only handles `proposer_index`, ignores `failed_proposer_indices` | `verification out of resources/timeout (global timeout set to 40s)` after generating 12 + 11 VCs across 2 of 5 shards |
| 1 (after diagnose) | adds loop over `failed_proposer_indices`, places `spec { invariant ... }` inside the loop body, adds `let ghost_proposer_idx = proposer_index;` (not a spec update) | `error: Loop invariants must be declared at the beginning of the loop header in a consecutive sequence` |

## Aggregated metrics

| Baseline | Pass rate | Average rounds_to_success (passing only) | Notes |
|----------|-----------|------------------------------------------|-------|
| B1 (zero-shot)             | 4/5 (80%) | n/a | stake_update_perf fails; bodies for simple cases compile + verify in one shot |
| B3 (module context)        | 4/5 (80%) | n/a | Same set passes; bodies are slightly cleaner (more in-module API usage) |
| B6 (1 feedback round)      | 4/5 (80%) | r=1 for all 4 passing | No improvement over B3 because the only failing case requires Move-Prover idioms the diagnoser does not recognize |
| B7 (3 feedback rounds)     | 4/5 (80%) for the 4 simple cases; stake_update_perf to be re-run with manual diagnosis | r=1 for 3 of 4, r=2 for chain_id_initialize | Same conclusion |

## Headline finding for the feasibility test

* The feedback loop with an LLM-only diagnose call **does not** lift verification of the most complex Move spec on its own. The diagnose LLM cannot reliably name the missing Move-Prover idioms (`spec { update ghost_var = ... }`, while-header invariant placement, overflow `assume`s); without that the codegen call drifts.
* On simple-to-medium specs (4 of 5 functions), the LLM passes one-shot — feedback does not help because there is no failure to diagnose.
* The next experiment we want to run is whether **a hand-written diagnosis** that names the three Move-Prover idioms above is enough for the codegen step to produce a verifying body. That isolates "model can implement the idioms when told" from "diagnose-LLM can identify the idioms".

## Manual-diagnosis probe — answers the bottleneck question

I hand-wrote a diagnosis for `stake_update_perf` that explicitly named the three idioms above (`spec { update ... }`, while-header invariant placement, `spec { assume X + 1 <= MAX_U64 }`) and ran ONE feedback round (using the same Kimi `kimi-for-coding` codegen prompt as B6/B7).

* Artifacts: `feas_run_02/manual_diag/stake_update_perf/{diagnosis.txt, prompt.txt, response.txt, extracted_body.txt, verify.json}`
* **Result: PASS, prove_time 76.95s.**
* The body the model produced is essentially identical to the reference body — `spec { update ghost_valid_perf = ...; update ghost_proposer_idx = ...; }` placed before the proposer-index branch; while-header invariants in `while ({ spec { invariant ... }; cond })` form; `spec { assume X + 1 <= MAX_U64; }` immediately before every `+= 1`.

This isolates the failure mode in B6/B7:

* **Codegen capability is sufficient.** kimi-for-coding can produce a verifying body for the hardest function in our 5-function set when given a precise, idiom-naming diagnosis.
* **The bottleneck is the diagnose call.** The current generic "look at prover output and produce CATEGORY/ROOT_CAUSE/FIX_INSTRUCTION" prompt does not surface Move-Prover-specific idioms, so the codegen call cannot apply them.

Implication for next iteration: the diagnose-LLM prompt needs an explicit Move-Prover idiom checklist (or a few-shot library) — not just "diagnose the failure". With that addition, B6/B7 should match the manual-diagnosis result on this class of failures.

