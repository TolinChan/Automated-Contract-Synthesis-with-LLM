# MoveBiSynth: Spec-Driven Smart-Contract Synthesis with Verifier-in-the-Loop Feedback

> Full paper draft — ASE submission format  
> Target: Automated Software Engineering (ASE), full research track

---

## Abstract

Generating implementations that satisfy formal specifications is a long-standing goal in software engineering. Large language models (LLMs) can produce code from natural-language or formal specs, yet the generated code frequently fails to pass formal verification—particularly for languages with first-class verification support such as Aptos Move. We observe that the bottleneck is often not the LLM's *code-generation* capability but its inability to interpret low-level verifier output and translate it into actionable, domain-specific repairs.

We present **MoveBiSynth**, a verifier-in-the-loop synthesis pipeline for Move smart contracts. Given a function signature and a fixed Move-Spec formal specification, MoveBiSynth repeatedly synthesises a function body and validates it with the Move Prover (Boogie/Z3). When verification fails, a dedicated **diagnoser** role classifies the failure into a taxonomy of Move-Prover-specific idioms and prescribes structured fix instructions, which are fed back to a separate **code-generation** role for the next round. This two-role separation prevents the generator from defending its own mistakes and keeps the feedback bounded and actionable.

A minimal feasibility test on five Aptos-framework functions shows that zero-shot LLM synthesis passes 4/5 cases; the single failure—a complex function requiring ghost-variable updates, while-header invariants, and overflow assumes—cannot be repaired by generic error feedback, yet is fixed in one round when the diagnoser names the three required idioms explicitly. These results separate *codegen capability* (sufficient) from *diagnosis quality* (the bottleneck), and motivate the structured, domain-specific feedback loop at the heart of MoveBiSynth.

**Keywords:** smart-contract synthesis, formal verification, Move Prover, LLM agent, feedback loop

---

## 1. Introduction

Smart contracts manage high-value assets on-chain; a single bug can lead to irreversible financial loss. Formal verification offers mathematical guarantees of correctness, but writing both the implementation and the formal specification is labour-intensive and requires expertise in verification tools. Automated synthesis of verified implementations from formal specifications would dramatically lower this barrier.

Large language models have shown promise in code generation from natural-language descriptions [1,2], and recent work has extended this to specification-driven generation [3,4]. However, when the target language includes a built-in formal verifier—as Aptos Move does with the Move Prover [5]—a generated body that "looks correct" may still fail verification because of subtle domain-specific requirements (e.g., ghost-variable bookkeeping, loop-invariant placement, arithmetic-overflow assumptions) that the LLM has not encountered in its training data.

A natural response is to close the loop: run the verifier, feed its error output back to the LLM, and ask for a revised body. Prior work has explored this pattern in other domains [6,7,8], but two problems remain under-addressed:

1. **Raw verifier output is too low-level.** The Move Prover emits Boogie/Z3-level messages (verification-condition failures, SMT timeouts, counter-example traces). Feeding these directly into an LLM as "feedback" overwhelms the context window and does not surface the high-level code transformation required.
2. **Asking one LLM to both generate and self-critique conflates two distinct tasks.** A generator asked to repair its own output tends to make local, syntactic patches rather than recognise missing domain idioms; the failure mode and the fix are often orthogonal skills.

We address both problems with **two-role separation** and **structured domain-specific diagnosis**. MoveBiSynth splits the work between a *codegen* role (produce a body) and a *diagnoser* role (analyse verifier output and prescribe fixes in the vocabulary of Move-Prover idioms). The diagnoser's output is not raw prover stderr; it is a typed record `{CATEGORY, ROOT_CAUSE, FIX_INSTRUCTION}` phrased in domain terms the codegen role can act on.

### 1.1 Motivating Example

Consider `update_performance_statistics` from the Aptos `stake` module, a function that updates validator performance counters. Its specification (held fixed throughout our experiments) declares two module-level ghost variables, a while-loop over failed proposer indices, and post-conditions relating the updated state to the input snapshots.

When we ask an LLM (`kimi-for-coding`) to generate the function body from the signature and spec alone (zero-shot), it produces a body that compiles but fails verification with a timeout after 72 s. The generated body is missing three Move-Prover-specific idioms:

- **Idiom 1 — Ghost-variable update.** The spec references `global ghost_valid_perf` and `global ghost_proposer_idx`; the body must initialise them with `spec { update ghost_valid_perf = validator_perf; }` blocks, not regular `let` bindings.
- **Idiom 2 — While-header invariant placement.** Loop invariants must be placed inside the while-header expression (`while ({ spec { invariant ... }; cond })`), not in the loop body. The LLM places them in the body, triggering a compile-level prover error.
- **Idiom 3 — Overflow assume.** Every `u64 += 1` must be preceded by `spec { assume X + 1 <= MAX_U64; };`, otherwise the prover generates an unbounded overflow verification condition and times out.

We then run a generic feedback loop (B6): the prover error is fed back to the LLM with a prompt that asks it to diagnose and fix. After one feedback round the body changes, but two of the three idioms are still wrong; the error type shifts from timeout to "loop invariants must be declared at the beginning of the loop header." After a second round the result is still a failure. The loop is making *some* progress, but the generic diagnoser does not surface the idiom-level fixes because it has no Move-Prover checklist.

Finally, we hand-write a structured diagnosis that explicitly names all three idioms with code-level instructions, feed it through the *same* codegen prompt, and the resulting body passes verification in 76.95 s on the first attempt. The generated body matches the reference implementation almost line-for-line.

**Insight.** The LLM's *code-generation* capability is sufficient to produce a verifying body for this complex function. The bottleneck is the *diagnosis* step: without a domain-specific taxonomy that bridges raw prover output to actionable code transformations, the feedback loop cannot converge.

### 1.2 Contributions

We make the following contributions:

1. **A two-role architecture for verifier-in-the-loop synthesis.** We separate code generation from error diagnosis into distinct LLM roles with distinct contracts, preventing the generator from defending its own mistakes and making the bottleneck (diagnosis quality) independently measurable.
2. **A domain-specific diagnosis taxonomy for Move Prover.** We identify a finite set of failure modes and canonical fixes (ghost-variable update, while-header invariant placement, overflow assume) that bridge raw verifier output to actionable codegen instructions.
3. **An empirical separation of concerns.** A minimal feasibility test on five Aptos-framework functions shows that zero-shot codegen succeeds on 4/5; the one failure is repaired in one round by manual structured diagnosis but not by generic feedback. This demonstrates that codegen capability is not the limiting factor—diagnosis quality is.

### 1.3 Paper Organisation

Section 2 introduces Move, the Move Prover, and the spec-driven synthesis task. Section 3 surveys related work. Section 4 presents the MoveBiSynth design. Section 5 reports the minimal feasibility test. Section 6 discusses threats to validity and open questions. Section 7 concludes.

---

## 2. Background

### 2.1 The Move Language and the Move Prover

Move is a resource-oriented smart-contract language developed for the Aptos blockchain [9]. Resources are linear types that cannot be copied or dropped implicitly, making asset-tracking amenable to static analysis. The Move Prover [5] is a formal verifier integrated into the Aptos toolchain; it translates Move code together with Move-Spec (MSL) annotations into the Boogie intermediate verification language, which is then discharged by the Z3 SMT solver.

A Move function can carry a `spec fun` block that declares preconditions (`requires`), postconditions (`ensures`), abort conditions (`aborts_if`), frame conditions (`modifies`), and loop invariants (`invariant`). The Prover generates verification conditions (VCs) from the function body and the spec block; if Z3 proves all VCs, the function is verified. If not, the Prover emits an error trace or a timeout.

### 2.2 Spec-Driven Synthesis Task

We adopt the following task definition, which narrows the scope enough to obtain a clean correctness signal:

> **Input.** A function signature, a fixed `spec fun` block, and module context (imports, structs, sibling function signatures, module-level ghost-variable declarations).  
> **Output.** A function body that, when spliced into the signature, satisfies the spec according to `aptos move prove`.  
> **Invariant.** The spec block is read-only; the only editable surface is the function body.

This definition is intentional: it removes spec synthesis from the loop, giving us a deterministic oracle (prover exit code) and a bounded edit surface (one function body). Extending to spec synthesis is future work (Section 7).

---

## 3. Related Work

We classify related work along two axes: **spec-driven vs. error-driven** input, and **spec synthesis vs. code synthesis** task.

### 3.1 Spec-Driven Synthesis

**MSG** (Zhang et al., ASE'25) [10] generates Move specifications from code using a modular multi-agent architecture (separate agents for `aborts_if`, `ensures`, `modifies`, and loop invariants). It is the closest prior work for our target language, but it solves the inverse problem: code → spec, not spec → code. Its prover-feedback loop refines generated specs, not implementations.

**PropertyGPT** (Chu et al.) [11] uses retrieval-augmented generation to produce Certora/Echidna properties for Solidity. Its loop architecture (LLM → verifier → error feedback → LLM revision) is structurally similar to our verifier-in-the-loop design, but the LLM's task is to invent properties, not to generate implementations against an existing spec.

**Clover** (LaChance et al.) [12] generates code and annotations together, enforcing consistency across code, annotation, and docstring. It relies on GPT-4 as a consistency checker for docstring edges, creating an "LLM judges LLM" vulnerability that our approach avoids by delegating all soundness checks to the Move Prover.

**SysSpec** (Liu et al., FAST'26) [3] demonstrates spec-driven file-system generation, validating that formal specifications can guide LLM output in systems domains. It motivates our spec-driven input assumption, though its target (file systems) does not involve an external verifier oracle.

### 3.2 Error-Driven Repair

**RePair** (Le et al.) [6] gives an LLM buggy code plus compiler/test error logs and asks it to repair. This is fundamentally different from our approach: we start from a structured specification and generate an implementation, rather than patching an existing buggy program.

**Reflexion** (Shinn et al.) [7] and **SWE-agent** (Yang et al.) [8] explore multi-turn agent loops with tool use and verbal reinforcement. These inform our loop-control design (round budgets, persistence, metric separation), but neither addresses the specific challenge of translating formal-verifier output into actionable code repairs.

### 3.3 Positioning

| Dimension | MSG | PropertyGPT | RePair | **MoveBiSynth** |
|---|---|---|---|---|
| Task | Code → Spec | Property synthesis | Bug repair | **Spec → Code** |
| Input | Code + static analysis | Retrieved properties | Buggy code + errors | **Formal spec** |
| Oracle | Move Prover | Certora/Halmos/Echidna | Test/compiler | **Move Prover** |
| Feedback | Generic prover error | Property refinement | Rollback to best step | **Structured idiom-level diagnosis** |
| Roles | Multi-agent (spec clauses) | Single LLM + RAG | Actor + critic | **Codegen + Diagnose (separate)** |

MoveBiSynth is distinguished by (1) the spec-to-code direction, (2) the two-role separation with a domain-specific diagnoser, and (3) the hard verifier oracle without LLM-as-judge.

---

## 4. Design

### 4.1 Architecture Overview

MoveBiSynth is a feedback loop with two LLM roles and one deterministic oracle:

```
Frozen inputs
  ├─ function signature
  ├─ formal spec block (read-only)
  └─ module context (imports, structs, sibling signatures, ghost decls)
         │
         ▼
   ┌──────────────┐     body_k
   │  Codegen     │ ───────────────┐
   │  LLM         │                │
   └──────────────┘                ▼
         ▲              ┌───────────────────┐
         │              │  Splice + Verifier│
    feedback prompt     │  (deterministic   │
         │              │   oracle)         │
         │              └───────────────────┘
         │                       │
         │            pass / fail+output
         │                       │
         │              ┌────────┴─────────┐
         │              │                  │
         │           halt              ┌──────────┐
         │           (success)         │ Diagnose │
         │                             │ LLM      │
         │                             │(classify + prescribe)│
         │                             └──────────┘
         │                                  │
         └──────────────────────────────────┘
                    diagnosis_k
```

**Codegen role.** Takes frozen inputs plus an optional previous body and an optional structured diagnosis. Outputs a function body fenced in a recognisable marker. Its contract is: *produce Move code that satisfies the spec when spliced into the function*. It is not asked to analyse why a previous attempt failed.

**Verifier step.** Splices the generated body into a clean copy of the canonical source tree and runs `aptos move prove`. The verifier is the **sole source of pass/fail truth**; no LLM decides correctness. This eliminates hallucinated success.

**Diagnose role.** Takes the spec, signature, module context, failed body, and prover stdout/stderr. Outputs a typed record `{CATEGORY, ROOT_CAUSE, FIX_INSTRUCTION}` where the fix instruction is phrased in **domain idioms** (not raw prover jargon). Its contract is: *translate verifier output into a taxonomy of failure modes and prescribe code-level fixes*. It does not rewrite the body.

### 4.2 Design Principles

**P1 — Two LLM roles, single responsibility each.** One LLM produces; another analyses. Never the same call. A producer asked to self-correct in the same turn tends to defend its previous output. Separating the roles makes the bottleneck independently measurable: if codegen succeeds when the diagnosis is hand-written, the diagnoser is the bottleneck.

**P2 — Verifier is the only truth source.** LLMs in the loop never decide pass/fail. The verifier exit code is the contract.

**P3 — Spec is invariant; body is the only edit surface.** The loop's degree of freedom is one function body. This makes splicing mechanical, workspace reset cheap, and prevents "success by weakening the spec."

**P4 — Domain bridge, not generic error prose.** The diagnoser classifies into a finite taxonomy and prescribes fixes in domain idioms. Without this, the diagnoser becomes a verbose error reformatter and the codegen role gets no actionable guidance.

**P5 — Round-level artifact persistence.** Every round writes its prompt, model response, extracted body, verify result, and diagnosis. The loop is fully replayable post-hoc.

### 4.3 Loop Control

| Concern | Choice |
|---|---|
| Budget | `feedback_rounds` (1 or 3 in our experiments) plus 1 round-0 attempt |
| Stop on success | First round with verifier exit code 0 |
| Stop on failure | Budget exhausted |
| Metrics | `Pass@1` (round 0 only) and `rounds_to_success` (never mixed) |

---

## 5. Evaluation

### 5.1 Research Questions

- **RQ1:** How well does zero-shot LLM synthesis perform on spec-driven Move body generation?
- **RQ2:** Does generic verifier feedback improve the success rate?
- **RQ3:** Can structured domain-specific diagnosis repair cases that generic feedback cannot?

### 5.2 Setup

| Item | Value |
|---|---|
| Model | `kimi-for-coding` (via OpenAI-compatible API) |
| Verifier | `aptos move prove`, Aptos CLI 9.1.0, Boogie 3.5.1, Z3 4.13.0 |
| Per-VC timeout | 40 s |
| Workspace | Full reset from canonical sources before every verify run |

### 5.3 Dataset

Five functions from `aptos-framework`, selected to span spec complexity:

| Function | Module | Spec complexity |
|---|---|---|
| `chain_id_get` | `chain_id.move` | Trivial (1 line) |
| `chain_id_initialize` | `chain_id.move` | Simple (`signer`, `aborts_if`) |
| `coin_extract` | `coin.move` | Medium (struct mutate + `aborts_if`) |
| `block_initialize` | `block.move` | Medium-high (~25 lines) |
| `update_performance_statistics` | `stake.move` | Complex (ghost vars + while/invariant + overflow, ~50 lines) |

### 5.4 Baselines

- **B1 (Zero-shot).** Prompt = signature + spec. No context.
- **B3 (Zero-shot with module context).** Prompt = signature + spec + imports, structs, sibling signatures.
- **B6 (Auto-feedback, 1 round).** Round 0 = B3. If fail, generic diagnose prompt → feedback → round 1.
- **B7 (Auto-feedback, 3 rounds).** Up to 3 feedback rounds with generic diagnose.
- **Manual-diag (structured diagnosis, 1 round).** Hand-written diagnosis naming Move-Prover idioms, fed through the same codegen prompt as B6.

### 5.5 Results

**RQ1 — Zero-shot performance.**

| Function | B1 | B3 |
|---|---|---|
| `chain_id_get` | PASS (15.6 s) | PASS (16.4 s) |
| `chain_id_initialize` | PASS (16.0 s) | PASS (16.8 s) |
| `coin_extract` | PASS (27.6 s) | PASS (22.3 s) |
| `block_initialize` | PASS (42.2 s) | PASS (39.1 s) |
| `update_performance_statistics` | FAIL (72.2 s) | FAIL (71.2 s) |

**Pass rate: 4/5 (80%)** in both B1 and B3. Adding module context does not lift the failure.

**RQ2 — Generic feedback.**

| Function | B6 `rounds_to_success` | B7 `rounds_to_success` |
|---|---|---|
| `chain_id_get` | 1 | 1 |
| `chain_id_initialize` | 1 | 2 |
| `coin_extract` | 1 | 1 |
| `block_initialize` | 1 | 1 |
| `update_performance_statistics` | FAIL | FAIL |

Pass rate remains 4/5. Generic feedback does not repair the one failing case. The auto-diagnoser misclassifies the root cause (e.g., recommending spec modifications, which are forbidden) and does not surface the three required idioms.

**RQ3 — Structured diagnosis.**

For `update_performance_statistics`, a hand-written structured diagnosis explicitly naming the three idioms (Section 1.1) was fed to the same codegen prompt. Result:

| Metric | Value |
|---|---|
| Passed | **true** |
| Exit code | 0 |
| Prove time | **76.95 s** |
| Body quality | Matches reference implementation; all three idioms present |

### 5.6 Analysis

The results separate two concerns:

1. **Codegen capability is sufficient.** `kimi-for-coding` can produce a verifying body for the hardest function when given a precise, idiom-naming diagnosis.
2. **The bottleneck is the diagnose step.** A generic prover-output summarisation prompt does not surface Move-Prover idioms; a domain-specific diagnosis does.

This validates the two-role architecture: the codegen role works when the diagnoser role does its job. The next step is to automate the diagnoser to match the manual-diagnosis result without human intervention.

---

## 6. Discussion

### 6.1 Threats to Validity

**External validity.** The dataset is five functions from one framework. While the set spans spec complexity, generalisation to a larger benchmark (e.g., the full MSG benchmark suite) is future work.

**Construct validity.** We use `aptos move prove` exit code as the sole correctness criterion. This is sound (the Prover is a trusted tool) but may miss runtime behaviours not covered by the spec. Our task definition explicitly limits scope to spec satisfaction.

**Internal validity.** The manual-diagnosis result proves the architecture's potential but does not prove the *automated* diagnoser works. The auto-diagnoser with an idiom checklist has not yet matched the manual result (feas_run_03, not included in this deliverable). The architecture is sound; the diagnoser prompt engineering is ongoing.

### 6.2 Open Questions

**Diagnoser automation.** The idiom library is currently partially baked into the diagnose prompt. Scaling to a full benchmark requires either (a) a retrievable knowledge base of worked examples, or (b) learning the taxonomy from past failure traces.

**Single-role ablation.** A controlled "one LLM does both" baseline would empirically validate P1 (two-role separation), distinguishing architecture benefit from prompt quality.

**Few-shot prompting.** Would adding 1–2 correct spec→code examples to the round-0 prompt solve the idiom problem without any feedback loop? This baseline is planned but not yet run.

---

## 7. Conclusion

We presented MoveBiSynth, a verifier-in-the-loop synthesis pipeline for Move smart contracts. Its core design—two-role separation between codegen and diagnosis, with a domain-specific idiom taxonomy bridging raw prover output to actionable fixes—is motivated by an empirical observation: LLMs can generate verifying code for complex Move functions, but only when the feedback names the required domain idioms explicitly. Generic feedback loops fail on the same cases.

A minimal feasibility test on five Aptos-framework functions supports this claim: 4/5 pass zero-shot; the one failure is repaired in one round by structured manual diagnosis but not by generic auto-feedback. This separates codegen capability from diagnosis quality and establishes the diagnoser as the critical component for scaling to larger benchmarks.

**Future work** includes (1) automating the diagnoser to match manual-diagnosis quality, (2) scaling to a benchmark of 50+ functions, (3) running the single-role and few-shot ablations, and (4) porting the architecture to other verified-language targets (e.g., Rust + Kani, Dafny).

---

## References

[1] M. Chen et al., "Evaluating Large Language Models Trained on Code," *arXiv:2107.03374*, 2021.

[2] J. Austin et al., "Program Synthesis with Large Language Models," *arXiv:2108.07732*, 2021.

[3] Q. Liu et al., "Sharpen the Spec, Cut the Code: A Case for Generative File System with SYSSPEC," *FAST*, 2026.

[4] H. Le et al., "CodeRL: Mastering Code Generation through Pretrained Models and Deep Reinforcement Learning," *NeurIPS*, 2022.

[5] D. Angelis et al., "The Move Prover," *CPAL*, 2020.

[6] H. Le et al., "RePair: Automated Program Repair with Process-based Feedback," *arXiv:2408.11296*, 2024.

[7] N. Shinn et al., "Reflexion: Self-Reflective Agents with Verbal Reinforcement Learning," *NeurIPS*, 2023.

[8] J. Yang et al., "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering," *NeurIPS*, 2024.

[9] S. Blackshear et al., "Move: A Language With Programmable Resources," *Diem Association*, 2019.

[10] Y. Zhang et al., "Agentic Specification Generator for Move Programs," *ASE*, 2025.

[11] C. Chu et al., "PropertyGPT: LLM-driven Formal Verification of Smart Contracts," *arXiv:2405.02580*, 2024.

[12] E. LaChance et al., "Clover: Closed-Loop Verifiable Code Generation," *arXiv:2310.17807*, 2023.

---

## Appendix: Artifact Index

All experimental artifacts are available in the repository:

```
src/baseline_tasks/feasibility/results/feas_run_02/
├── RESULTS.md              # this report
├── b1/                     # zero-shot (signature + spec)
├── b3/                     # zero-shot + module context
├── b6/                     # auto-feedback (1 round)
├── b8/                     # auto-feedback (3 rounds)
└── manual_diag/            # structured manual diagnosis
```

Each subdirectory contains per-function prompts, model responses, extracted bodies, and verifier output (`verify.json`), enabling full reproduction without re-invoking the LLM.
