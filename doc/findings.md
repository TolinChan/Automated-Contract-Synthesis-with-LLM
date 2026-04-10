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
- **aptos.exe is NOT on PATH in bash/subprocess** — must use full WinGet path: `C:\Users\96247\AppData\Local\Microsoft\WinGet\Packages\AptosCore.aptos_Microsoft.Winget.Source_8wekyb3d8bbwe\aptos.exe`. Fixed in all three scripts via `_aptos()` helper (commit 79401af).
- **T2/M-series use `aptos move test` not `aptos move prove`** — agent must route correctly based on task type.
- **"No spec → no proof"**: `defi::locked_coins` showed that Move Prover only checks what's specified. Tasks with sparse annotations may show Pass@1=100% for the wrong reason.
- **Move package paths are hardcoded to E: drive** — any portability work requires updating `loop_tasks.py` constants.
- **Do not manually fix model output** before running `apply_and_check_mbe.py` — this would contaminate the Pass@1 metric.
- **Current input layer is NOT spec-driven** — `invoke_ofox_once.py` and `agent_verify_loop.py` send `PROMPT.txt + raw fail.log + source`, which is "here's broken code and an error, fix it." This is test/error-driven, not spec-driven. The `build_initial_user_message()` function needs a complete redesign.
- **T0/T1 vs T2/M are fundamentally different tasks**:
  - T0/T1: true formal spec-driven — `spec {}` blocks with `ensures`/`aborts_if` are the ground truth; Move Prover (Boogie+Z3) does mathematical proof
  - T2/M1–M3: test-driven — `assert!()` in unit tests; `aptos move test` just runs tests
  - Input format redesign must treat these two classes differently
- **fail.log has noise** — raw PowerShell output includes `NativeCommandError` headers, garbled paths, PS script paths. Needs a cleaning/extraction layer before sending to LLM.
- **Source code is duplicated in current prompts** — PROMPT.txt already inlines the source via `<<<CODE_START...CODE_END>>>`, and the script appends it again as `--- source file ---`. This wastes context and may confuse the model.

## Open Questions

1. **Input layer redesign**: What is the right context format for spec-driven repair? Options include: (a) spec block front-and-center with semantic explanation, (b) Clover-style three-way consistency framing, (c) SWE-agent ACI-style structured tool output. Need to brainstorm and evaluate.
2. **Error translation layer**: Is raw `fail.log` sufficient, or do we need a preprocessing step to extract the counterexample line, strip PS noise, and add natural language explanation?
3. **Spec coverage gap**: For M1–M3, are the specs complete enough to force the agent to fix the actual bug, or will the agent find a trivially passing but semantically wrong patch?
4. **Model comparison**: How do GPT-4o, Claude Sonnet, and Gemini compare on Move (a low-resource language with little training data)?
5. **Context window pressure**: Multi-module packages like M1–M3 may exceed single-context limits. How does the agent handle cross-file reasoning?
6. **Reflexion-style memory**: Would adding a verbal reflection step between rounds reduce the rounds_to_success on complex tasks?

## Optimization Trajectory

*No systematic runs yet. Inner loop begins after workspace setup.*

Proxy metric: `pass_rate` (fraction of tasks where verification passes within N rounds).
Baseline: Pass@1 across T0–T2 + M1–M3 using default model (claude-sonnet-4-6 or gpt-4o).
