# Literature Note: SmartInv — Multimodal Learning for Smart Contract Invariant Inference

## Metadata

- **Title**: SmartInv: Multimodal Learning for Smart Contract Invariant Inference
- **Authors**: Sally Junsong Wang (Columbia University), Kexin Pei (University of Chicago), Junfeng Yang (Columbia University)
- **Year**: 2024
- **Venue**: IEEE/ACM International Conference on Software Engineering (ICSE 2024); extended preprint on arXiv November 2024
- **arXiv ID**: 2411.13073 (preprint; ICSE 2024 conference version also at arXiv:2411.13715, DOI: 10.1145/3597503.3623335)
- **ACM DL**: https://dl.acm.org/doi/10.1145/3597503.3623335

---

## Abstract

Smart contracts are software programs deployed on blockchains that hold significant financial value and have been subject to numerous exploits. Existing tools for detecting smart contract vulnerabilities often rely on predefined patterns or manual specifications, which struggle to generalize across diverse vulnerability types. SmartInv proposes a multimodal learning framework to automatically infer *transaction invariants* for smart contracts. The key insight is that smart contract source code and its on-chain transaction history constitute complementary modalities; combining them enables more accurate invariant inference than either modality alone. SmartInv takes both source code and transaction execution traces as input, leverages fine-tuned large language models to generate candidate invariants, and employs a feedback-guided refinement loop to validate and improve the invariants. The system detects real-world vulnerabilities by checking for invariant violations at runtime or statically against known exploit patterns.

---

## Key Methodology

1. **Multimodal input**: SmartInv consumes two modalities jointly — (a) Solidity source code and ABI, and (b) on-chain transaction traces (historical execution data from Ethereum mainnet).
2. **LLM-based invariant synthesis**: A code-oriented LLM (fine-tuned on smart contract data) is prompted to generate candidate temporal and value-based invariants that should hold across all valid transactions.
3. **Feedback-guided refinement**: Generated invariants are checked against the transaction history and potentially against a static/dynamic analyzer; failed checks produce structured feedback that is fed back to the LLM for revision.
4. **Vulnerability detection**: The inferred invariants are used as oracles — contracts whose execution histories violate an invariant are flagged as potentially exploitable.
5. **Evaluation**: The system is evaluated on hundreds of real Ethereum contracts, including contracts involved in known DeFi exploits (flash loan attacks, reentrancy, price manipulation), and compared against baselines such as Slither, Mythril, and Echidna.

---

## Main Findings

- SmartInv outperforms single-modality baselines (code-only or trace-only) substantially, confirming that transaction history provides signal that source code alone cannot capture.
- The multimodal approach achieves higher precision and recall than existing static and dynamic analysis tools (Slither, Mythril, Echidna) on vulnerability detection benchmarks.
- SmartInv successfully identifies invariants whose violation corresponds to real historical DeFi exploits, including attacks on major protocols.
- The feedback-guided refinement loop improves invariant quality over zero-shot generation, especially for complex temporal properties.
- The work demonstrates that LLMs can learn to produce semantically meaningful, contract-specific invariants rather than generic pattern-matched checks.

---

## Relevance to This Project

*(LLM-based repair of Aptos Move smart contracts using Move Prover as formal verifier oracle, with iterative feedback loop)*

- **Invariant synthesis as a first-class task**: SmartInv frames invariant generation as an LLM task with automatic feedback, directly analogous to generating Move `spec` invariants and function postconditions that Move Prover can then verify. The approach validates that LLMs can produce non-trivial, contract-specific formal properties.
- **Feedback loop architecture**: The feedback-guided refinement loop in SmartInv (generate invariant → check → revise on failure) mirrors the core iterative loop in this project (generate/repair spec → run `aptos move prove` → parse verifier output → revise). SmartInv provides a published precedent for this loop in the smart contract security domain.
- **Multimodal signal vs. single-modality**: SmartInv's finding that transaction traces augment code-only LLM reasoning suggests that our project could similarly benefit from providing the LLM with Move Prover counterexample traces (execution witnesses produced by Z3) alongside the source code, rather than raw source alone.
- **Solidity-to-Move analogy**: SmartInv operates on Solidity smart contracts with financial invariants; this project targets Aptos Move contracts with similar financial semantics (resource types, ownership, arithmetic). SmartInv's vulnerability taxonomy (reentrancy, price manipulation, value overflow) maps conceptually onto Move Prover specification categories.
- **Benchmark design reference**: SmartInv's evaluation methodology — testing against contracts with known real-world exploits and measuring both precision and recall of invariant violations — offers a template for constructing a Move-contract evaluation suite where ground-truth specification correctness is known.
