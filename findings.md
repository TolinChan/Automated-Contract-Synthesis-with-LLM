# Research Findings

## Research Question

Can a coding agent driven by formal pre/postcondition specs (Move Prover) iteratively repair injected bugs in Aptos Move smart contracts, and how does iterative verifier-feedback repair compare to single-shot (Pass@1) LLM generation?

## Current Understanding

**The core architecture is validated at PoC level.** The Verifier-in-the-Loop loop (spec → LLM edit → `aptos move prove`/`aptos move test` → parse feedback → LLM edit → …) demonstrably works for simple injected bugs (T0 `plus1`, T1 `aborts_if`, T2 `hello_blockchain`). The PoC showed:
- For trivial semantic faults (off-by-one in postcondition), a single-shot LLM call with the frozen `fail.log` and PROMPT.txt can produce a passing patch.
- Move Prover failure messages contain rich counterexample information (specific values, failing assertion lines) that is interpretable by modern LLMs.

**The key research contribution is the Move-specific deployment of the spec-driven repair loop**, combining:
1. *Formal proof obligations* (not just unit tests) as the oracle — stronger guarantee than DafnyBench analogs.
2. *Frozen, code-internal specs* (`requires`/`ensures`/`aborts_if`) that the agent reads as part of the source — not a separate file.
3. *Coding agent with local tool access* (Baseline B) vs. API-only (Baseline A) — the agent advantage is tool execution, not model capability.

**Where the problem gets hard:** Complex M1–M3 tasks (NFT marketplace, FA vesting, advanced Todo) have multi-module dependencies and less complete specs. The `defi::locked_coins` PoC showed "no spec → prover proves nothing" — the agent must recognize when specs are insufficient and either ask or infer missing postconditions. This is an open research gap.

## Key Results

| Task | Baseline A (Pass@1) | Baseline B (rounds_to_success) | Notes |
|------|--------------------|---------------------------------|-------|
| T0 (plus1 proof) | TBD | TBD | Simplest; counterexample is a single value |
| T1 (aborts_if proof) | TBD | TBD | Requires understanding abort conditions |
| T2 (unit test) | TBD | TBD | Test failure more readable than prover output |
| M1 (NFT marketplace) | TBD | TBD | Large package; multi-file context |
| M2 (FA vesting) | TBD | TBD | Resource safety semantics |
| M3 (advanced Todo) | TBD | TBD | Complex state invariants |

*Experiments not yet run systematically — PoC level only. Full benchmark run is the next inner loop.*

## Patterns and Insights

1. **Verifier feedback > no feedback**: Consistent with Clover (53/60 vs 48/60 with Dafny feedback) and RePair (process supervision outperforms outcome-only). Expected to hold for Move Prover.

2. **Spec precision drives repair quality**: SYSSPEC showed 100% accuracy on strong-model + formal spec vs 81.8% on oracle baseline. In our setting, the spec is pre-existing and frozen — the question is whether the LLM can parse Move's spec syntax without needing explicit Dafny-style separation.

3. **Error translation is a key variable**: Move Prover outputs Z3 SMT counterexamples that may be verbose. Whether the agent's context window is overwhelmed by raw `fail.log` (vs. a cleaned/truncated version) is an empirical question not yet answered.

4. **Pass@1 vs. rounds_to_success gap**: Expected to be large on M1–M3 (complex tasks) and small on T0–T2 (simple tasks). The gap quantifies the value of the iterative loop.

## Lessons and Constraints

- **Boogie must be exactly 3.5.1.x** — higher versions rejected by Aptos CLI. Version mismatch is the most common environment failure.
- **T2/M-series use `aptos move test` not `aptos move prove`** — agent must route correctly based on task type.
- **"No spec → no proof"**: `defi::locked_coins` showed that Move Prover only checks what's specified. Tasks with sparse annotations may show Pass@1=100% for the wrong reason.
- **Move package paths are hardcoded to E: drive** — any portability work requires updating `loop_tasks.py` constants.
- **Do not manually fix model output** before running `apply_and_check_mbe.py` — this would contaminate the Pass@1 metric.

## Open Questions

1. **Error translation layer**: Is raw `fail.log` sufficient for LLMs to repair T0/T1, or do we need a preprocessing step (truncate, extract counterexample line, add natural language explanation)?
2. **Spec coverage gap**: For M1–M3, are the specs complete enough to force the agent to fix the actual bug, or will the agent find a trivially passing but semantically wrong patch?
3. **Model comparison**: How do GPT-4o, Claude Sonnet, and Gemini compare on Move (a low-resource language with little training data)?
4. **Context window pressure**: Multi-module packages like M1–M3 may exceed single-context limits. How does the agent handle cross-file reasoning?
5. **Reflexion-style memory**: Would adding a verbal reflection step between rounds reduce the rounds_to_success on complex tasks?

## Optimization Trajectory

*No systematic runs yet. Inner loop begins after workspace setup.*

Proxy metric: `pass_rate` (fraction of tasks where verification passes within N rounds).
Baseline: Pass@1 across T0–T2 + M1–M3 using default model (claude-sonnet-4-6 or gpt-4o).
