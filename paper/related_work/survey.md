# Literature Survey: LLM-Based Contract Synthesis, Repair, and Formal Verification

**Project**: Automated Contract Synthesis and Repair with Large Language Models
**Focus**: LLM-based repair of Aptos Move smart contracts using Move Prover as formal verifier oracle, with iterative feedback loop.
**Last updated**: 2026-04-09

---

## Survey Table

| # | Title | Venue | arXiv ID | 2-Sentence Summary | Relevance |
|---|-------|-------|----------|--------------------|-----------|
| 1 | Sharpen the Spec, Cut the Code: A Case for Generative File System with SYSSPEC | USENIX FAST 2026 | — (conference paper; project page: llmnativeos.github.io/specfs) | Uses structured multi-part specifications (Hoare-style contracts, Rely-Guarantee, concurrency specs) as unambiguous blueprints for LLM-driven code generation and evolution of a full file system, with a retry-with-feedback loop between a code generator and a separate evaluator agent. Demonstrates that formalizing intent at the spec level rather than the code level dramatically reduces maintenance burden and enables correct-by-construction module regeneration. | **High** |
| 2 | RePair: Automated Program Repair with Process-based Feedback | arXiv 2024 | 2408.11296 | Trains a 15B-parameter model (StarCoderBase) to perform multi-step competitive-programming repair using a learned reward model that mimics compiler and test-judge feedback, combined with PPO reinforcement learning to iteratively improve patches. Establishes that process-level supervision (per-step rewards) and a virtual critic that avoids expensive online tool calls are key to making smaller open-source models competitive with GPT-3.5/Claude 2 on repair benchmarks. | **High** |
| 3 | Clover: Closed-Loop Verifiable Code Generation | arXiv 2023 (v4: 2024) | 2310.17807 | Proposes a three-artifact consistency framework (code, formal annotation, docstring) in which Dafny verifies code-against-annotation soundness while LLM-based reconstruction checks check the other consistency edges, achieving zero false positives on adversarial examples while maintaining high acceptance rates on correct programs. Demonstrates that deductive-verifier feedback is essential for GPT-4 to produce syntactically and semantically valid Dafny annotations, directly validating the "verifier-in-the-loop" repair paradigm. | **High** |
| 4 | Reflexion: Language Agents with Verbal Reinforcement Learning | NeurIPS 2023 | 2303.11366 | Introduces verbal reinforcement learning where an LLM agent converts environmental feedback (success/failure signals) into natural-language reflections stored as episodic memory, enabling iterative improvement without gradient updates across decision-making, coding, and reasoning tasks. The verbal memory mechanism provides a principled way to prevent an LLM repair agent from repeating the same failed patches across multiple Move Prover invocations. | **High** |
| 5 | SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering | NeurIPS 2024 | 2405.15793 | Proposes Agent-Computer Interfaces (ACI) — purpose-built abstractions between LLM agents and software development tools — that provide concise, structured tool output rather than raw terminal streams, enabling GPT-4 to resolve real GitHub issues at significantly higher rates than prior agent baselines. The ACI design philosophy directly informs the "Error Translator" component of this project, which must distill verbose Move Prover / Z3 logs into compact, actionable feedback strings before returning them to the LLM. | **High** |
| 6 | SmartInv: Multimodal Learning for Smart Contract Invariant Inference | ICSE 2024 | 2411.13073 | Combines Solidity source code with on-chain transaction traces as two complementary modalities to train an LLM to infer transaction invariants for smart contracts, then uses a feedback-guided refinement loop to validate and improve the invariants, detecting real-world DeFi exploits with higher precision/recall than static and dynamic analysis baselines. Demonstrates that LLMs can generate non-trivial, contract-specific formal invariants when provided with execution-trace context, providing a precedent for LLM-driven invariant synthesis in the financial smart contract domain. | **High** |
| 7 | DafnyBench: A Benchmark for Formal Software Verification | arXiv 2024 | 2406.08467 | Constructs a 1,702-task benchmark of Dafny formal verification problems (loop invariants, pre/postconditions, ghost variables) and evaluates frontier LLMs under strict verifier-acceptance criteria, finding that GPT-4o achieves only 64% pass@1, with loop invariants and termination metrics being the hardest elements. Provides the most direct LLM-capability baseline for deductive-verifier tasks analogous to Move Prover, and its pass@k evaluation methodology and benchmark construction approach are directly transferable to building a Move smart contract verification benchmark. | **High** |
| 8 | PropertyGPT: LLM-driven Formal Verification of Smart Contracts through Retrieval-Augmented Property Generation | arXiv 2024 | 2405.02580 | Uses retrieval-augmented generation (RAG) over a database of existing verified smart contract properties to prompt an LLM to generate Certora CVL, Echidna, and Halmos properties for new contracts, then iteratively refines properties using structured verifier error feedback, outperforming zero-shot and fine-tuned baselines and discovering novel bugs in deployed DeFi contracts. Structurally the closest published analogue to this project's entire pipeline (RAG-seeded generation + formal verifier oracle + iterative LLM repair loop), differing only in target language (Solidity/CVL vs. Move/Move Spec) and verifier (Certora/Halmos vs. Move Prover). | **High** |

---

## Notes on Individual Summary Files

| Paper | Summary File |
|-------|-------------|
| SYSSPEC / Generative FS (FAST '26) | `literature/SYSSPEC_FAST26.md` |
| RePair / CodeNet4Repair (arXiv:2408.11296) | `literature/RePair_2408.11296.md` |
| Clover (arXiv:2310.17807) | `literature/Clover_2310.17807.md` |
| Reflexion (arXiv:2303.11366) + SWE-agent (arXiv:2405.15793) | `literature/Reflexion_SWEagent_notes.md` |
| SmartInv (arXiv:2411.13073) | `literature/SmartInv_2411.13073.md` |
| DafnyBench (arXiv:2406.08467) | `literature/DafnyBench_2406.08467.md` |
| PropertyGPT (arXiv:2405.02580) | `literature/PropertyGPT_2405.02580.md` |

---

## Thematic Clusters

### Iterative LLM + Verifier/Tool Feedback Loops
Clover, Reflexion, SWE-agent, PropertyGPT, RePair — all establish that repeated tool invocation with structured feedback return to the LLM is the dominant mechanism for improving LLM-generated formal artifacts beyond single-shot quality.

### Formal Property / Invariant Generation for Smart Contracts
SmartInv, PropertyGPT — both directly address LLM-based synthesis of formal properties for financial smart contracts, the closest prior work to this project's target domain.

### Benchmarking LLMs on Formal Verification Tasks
DafnyBench — the primary reference for evaluating LLM performance under strict deductive-verifier acceptance criteria; Clover also contributes CloverBench as a smaller adversarial benchmark.

### Spec-Driven Code Generation and Repair
SYSSPEC, RePair — demonstrate that structuring the LLM's task around formal/semi-formal specifications (rather than natural language) and providing step-level process feedback are essential for achieving correct complex software artifacts.
