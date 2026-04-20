# Baseline Comparison: Positioning Our Approach

This table positions **MoveBiSynth** against the most closely related prior work. A critical axis is whether the LLM is driven by a **formal/structured specification** (spec-driven) or by **verifier/compiler error feedback** (error-driven).

| Dimension                        | MSG (Zhang et al., ASE'25)                                   | PropertyGPT (Chu et al.)                                     | Clover (LaChance et al.)                                     | RePair (Le et al.)                                           | **MoveBiSynth (Our Approach)**                               |
| -------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Input to LLM**                 | Code + static-analysis hints → **generate specs**            | Retrieved properties + code → **generate specs**             | Docstring / annotation / code → **generate triples**         | Buggy code + compiler/test **error logs** → **repair code**  | **Formal Spec / NL Intent** → **generate spec + code** (bidirectional synthesis) |
| **Spec-driven vs. Error-driven** | **Spec-driven**                                              | **Spec-driven**                                              | **Spec-driven**                                              | **Error-driven**                                             | **Spec-driven** *(with verifier-in-the-loop validation)*     |
| **Target Language**              | Move (Move Spec Language)                                    | Solidity (CVL / Echidna / Halmos)                            | Dafny (w/ Verus ext.)                                        | Competitive Python                                           | **Aptos Move**                                               |
| **Verifier / Oracle**            | Move Prover                                                  | Certora Prover, Halmos, Echidna                              | Dafny (soundness edge) + GPT-4 (consistency edges)           | CodeNet test judge + compiler                                | **Move Prover**                                              |
| **Core Mechanism**               | Modular clause-gen agents (aborts_if, ensures, modifies, loop invariants) | RAG over property DB + iterative property refinement         | Three-artifact consistency (code, annotation, docstring)     | SFT + PPO with learned reward model mimicking process feedback | **Multi-agent pipeline**: Constraint Agent generates spec → Spec Check validates completeness → Contract Agent generates code → Merger combines → Verifier validates → Error Diagnosis routes failures for repair |
| **Task**                         | Specification **synthesis**                                  | Property **synthesis**                                       | Code + annotation **generation**                             | Code **repair**                                              | **Contract synthesis** (generate spec + implementation under formal verification constraints) |
| **Feedback Loop**                | Prover errors fed back to refine generated specs             | Verifier/fuzzer errors fed back to refine properties         | Compiler / Dafny errors fed back to regenerate triples       | Per-step reward from virtual critic; rollback to best step   | **Structured routing**: Error Diagnosis Agent classifies failure → routes to Constraint Adjustment Agent (fix spec) or Contract Agent (fix code) → re-validate via Spec Check |
| **Key Distinction**              | Generates MSL specs from code; solves spec synthesis, not code generation | Focuses on invariant/property generation for Solidity; closest structural analogue in smart-contract domain | Heavy use of LLM-as-judge for docstring/annotation consistency; introduces hallucination risk | Learns a reward model to avoid expensive online tool calls; scales to 15B param models | **Bidirectional spec-code synthesis** with **spec completeness validation** before verifier invocation |

---

## Narrative Positioning

### The Spec-Driven Camp
**MSG**, **PropertyGPT**, and **Clover** all treat the formal specification as the *source of truth* that shapes the LLM's output.

- **MSG** generates Move specifications from code, using a modular agent architecture (aborts_if, ensures, modifies, loop invariant agents). It is the closest prior work for our *target language*, but it solves **spec synthesis** (Code → Spec), not **code generation** (Spec → Code).
- **PropertyGPT** uses RAG to generate Certora/Echidna properties for Solidity. Its loop architecture (LLM → verifier → error feedback → LLM revision) is structurally similar to our verifier-in-the-loop design, but it remains **spec-driven** at the output layer because the LLM's task is to invent properties, not to generate implementations against an existing spec.
- **Clover** generates code *from* annotations (and vice versa), enforcing consistency across code, annotation, and docstring. Its reliance on GPT-4 as a consistency checker for docstring edges creates a "LLM judges LLM" vulnerability that our approach avoids by delegating all soundness checks to the **Move Prover**.

### The Error-Driven Camp
**RePair** gives the LLM a **failing artifact** (buggy code + compiler/test error signal) and asks it to repair. This is fundamentally different from our approach: we start from a structured specification (or natural language intent) and generate both the specification and the implementation, rather than patching an existing buggy program.

### What Makes Our Approach Distinct

1. **Bidirectional synthesis**: Unlike MSG (Code → Spec) or conventional approaches (Spec → Code in C/Solidity), we design a unified pipeline where the specification and the implementation are generated in tandem, with the specification serving as a structured contract that the implementation must satisfy.

2. **Spec completeness validation before verifier invocation**: We introduce a **Spec Check** step that validates whether the generated specification fully captures the implementation's behavior (e.g., abort conditions, state modifications, return value guarantees) before invoking the Move Prover.

3. **Hard verifier oracle**: Unlike Clover, we do not use an LLM to judge correctness; **Move Prover** (Boogie + Z3) is the sole arbiter of soundness.

4. **Error diagnosis as structured routing**: When verification fails, our **Error Diagnosis Agent** parses the Prover output, classifies the failure type (compilation error / spec violation / timeout), and routes to the appropriate repair agent (Constraint Adjustment for spec fixes, Contract Agent for code fixes). This is more targeted than generic "round-by-round" feedback.

5. **Language specificity**: We target **Aptos Move**, a resource-oriented language with first-class formal verification support that is absent in Solidity/Python baselines. Move's borrow checker and resource semantics require specification constructs (aborts_if, modifies, ensures) that do not directly map to C or Solidity properties.

---

## Additional Related Work

The following works informed our architecture but are not included in the primary comparison table (different domains or tasks):

| Work                            | Domain                             | Relevance                                                    |
| ------------------------------- | ---------------------------------- | ------------------------------------------------------------ |
| **ConMover** (arXiv 2412.12513) | Move code generation from NL       | Confirms multi-agent design (+47.1% improvement); validates Move as target |
| **AlphaVerus** (ICLR'25)        | Dafny → Verus translation          | Introduced critique model for specification validation; relevant to our Spec Check step |
| **SysSpec** (arXiv 2025)        | Spec-driven file system generation | Demonstrates spec → code feasibility in systems domain; validated two-phase prompting |
| **LaM4Inv** (ASE'24)            | Loop invariant inference           | LLM + BMC closed-loop synergy; informed our verifier-in-the-loop feedback design |

---

## Critical Design Decisions (vs. Baselines)

| Decision                                  | Rationale                                                    | Contrast with                                   |
| ----------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------- |
| **Spec-driven input**                     | Starting from structured spec (or NL intent mapped to spec) provides stronger generation guidance than error logs alone | RePair (error-driven), conventional LLM repair  |
| **Spec Check step**                       | Validates that generated specifications fully capture implementation behavior (aborts, modifications, ensures) before invoking verifier | AlphaVerus (critique model for spec validation) |
| **Separate Constraint / Contract Agents** | Specialization improves output quality vs. single LLM handling both spec and code | PropertyGPT (single property generator)         |
| **Merger before Verifier**                | Ensures syntactic coherence of spec + code as a unified Move contract | MSG (spec-only, no code merger needed)          |
| **Error Diagnosis as router**             | Structured failure classification avoids wasted iterations on wrong repair target | RePair (generic rollback)                       |

