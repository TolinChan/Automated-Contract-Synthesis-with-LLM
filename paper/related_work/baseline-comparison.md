# Baseline Comparison: Positioning Our Approach

This table positions our Move repair agent against the most closely related prior work. A critical axis is whether the LLM is driven by a **formal/structured specification** (spec-driven) or by **verifier/compiler error feedback** (error-driven).

| Dimension | MSG (Zhang et al.) | PropertyGPT | Clover | RePair | **Our Approach** |
|-----------|-------------------|-------------|--------|--------|------------------|
| **Input to LLM** | Code + static-analysis hints → **generate specs** | Retrieved properties + code → **generate specs** | Docstring / annotation / code → **generate triples** | Buggy code + compiler/test **error logs** → **repair code** | Buggy Move code + Move Prover **failure log** → **repair code** |
| **Spec-driven vs. Error-driven** | **Spec-driven** | **Spec-driven** | **Spec-driven** | **Error-driven** | **Error-driven** *(redesign toward spec-driven ongoing)* |
| **Target Language** | Move (Move Spec Language) | Solidity (CVL / Echidna / Halmos) | Dafny (w/ Verus ext.) | Competitive Python | Aptos Move |
| **Verifier / Oracle** | Move Prover | Certora Prover, Halmos, Echidna | Dafny (soundness edge) + GPT-4 (consistency edges) | CodeNet test judge + compiler | Move Prover + `aptos move test` |
| **Core Mechanism** | Modular clause-gen agents (aborts_if, ensures, modifies, loop invariants) | RAG over property DB + iterative property refinement | Three-artifact consistency (code, annotation, docstring) | SFT + PPO with learned reward model mimicking process feedback | Single-shot or multi-round LLM repair with raw/error-translated Prover feedback |
| **Task** | Specification **synthesis** | Property **synthesis** | Code + annotation **generation** | Code **repair** | **Contract synthesis and repair** (code generation & patch under formal/test constraints) |
| **Feedback Loop** | Prover errors fed back to refine generated specs | Verifier/fuzzer errors fed back to refine properties | Compiler / Dafny errors fed back to regenerate triples | Per-step reward from virtual critic; rollback to best step | Round-by-round Prover error fed back to LLM context |
| **Key Distinction** | Generates MSL specs from scratch; does **not** start from injected bugs or failing proofs | Focuses on invariant/property generation for Solidity; closest structural analogue in the smart-contract domain | Heavy use of LLM-as-judge for docstring/annotation consistency; reduces false positives but introduces hallucination risk | Learns a reward model to avoid expensive online tool calls; scales to 15B param models | Targets **Aptos Move** specifically; uses **real Move Prover** as single source of truth rather than LLM-as-judge |

---

## Narrative Positioning

### The Spec-Driven Camp
**MSG**, **PropertyGPT**, and **Clover** all treat the formal specification as the *source of truth* that shapes the LLM's output.

- **MSG** generates Move specifications from code, using a modular agent architecture. It is the closest prior work for our *target language*, but it solves **spec synthesis**, not **code repair**.
- **PropertyGPT** uses RAG to generate Certora/Echidna properties for Solidity. Its loop architecture (LLM → verifier → error feedback → LLM revision) is structurally identical to ours, but it remains **spec-driven** because the LLM's task is to invent properties, not to generate or patch implementations against an existing spec.
- **Clover** generates code *from* annotations (and vice versa), enforcing consistency across code, annotation, and docstring. Its reliance on GPT-4 as a consistency checker for docstring edges creates a "LLM judges LLM" vulnerability that our approach avoids by delegating all soundness checks to the **Move Prover**.

### The Error-Driven Camp
**RePair** gives the LLM a **failing artifact** (buggy code + compiler/test error signal) and asks it to repair. **Our current pipeline** also operates in the error-driven space — the model receives the buggy source and the `fail.log`, then produces a patch — but the overall project goal is broader: **contract synthesis and repair under formal or test oracle constraints**. As noted in project memory, relying on dense verifier error text as the primary input is a limitation; a redesign toward making the task explicitly spec-driven (grounded in structured Hoare-style contracts or resource invariants) is ongoing.

### What Makes Our Approach Distinct
1. **Language specificity**: We target **Aptos Move**, a resource-oriented language with first-class formal verification (Move Prover) that is absent in Solidity/Python baselines.
2. **Synthesis *and* repair under one oracle**: Unlike MSG and PropertyGPT (pure synthesis) or RePair (pure repair), our project evaluates LLMs on both generating contract code and patching injected bugs, all under the same Move Prover / unit-test oracle.
3. **Hard verifier oracle**: Unlike Clover, we do not use an LLM to judge correctness; **Move Prover** is the sole arbiter of soundness.
4. **Error-translator layer**: Because Move Prover/Z3 logs are noisy, we invest in distilling them into structured, actionable feedback — an intermediate layer neither MSG nor PropertyGPT needed to the same degree.
5. **Spec-driven redesign trajectory**: While MSG and PropertyGPT are natively spec-driven, our current pipeline is error-driven. The planned redesign will make our approach **spec-driven at the input layer** while retaining the **verifier-in-the-loop** generation and repair mechanism.
