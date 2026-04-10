# Literature Note: PropertyGPT — LLM-driven Formal Verification of Smart Contracts through Retrieval-Augmented Property Generation

## Metadata

- **Title**: PropertyGPT: LLM-driven Formal Verification of Smart Contracts through Retrieval-Augmented Property Generation
- **Authors**: Ye Liu, Yue Xue, Daoyuan Wu, Yuqiang Sun, Yi Li, Miaolei Shi, Yang Liu
- **Year**: 2024
- **Venue**: arXiv preprint (submitted 4 May 2024); arXiv:2405.02580
- **arXiv ID**: 2405.02580
- **URL**: https://arxiv.org/abs/2405.02580

---

## Abstract

We explore in this paper the potential of harnessing existing LLMs combined with retrieval-augmented generation (RAG) to reason and generate verifiable and runtime-checkable properties for smart contracts, with the ultimate goal of enabling automated and comprehensive formal verification. To this end, we embed existing properties as well as the target smart contract code into vector representations and retrieve the most semantically similar properties from a pre-built property database. We then prompt the LLM to generate new properties by reasoning over the retrieved ones and the contract code. We further propose a property refinement mechanism that leverages feedback from the formal verification tool to iteratively improve the generated properties. Evaluation results show that PropertyGPT can effectively generate high-quality formal properties and outperforms existing state-of-the-art methods.

---

## Key Methodology

1. **Retrieval-Augmented Generation (RAG) for properties**: A vector database is built from existing formally verified smart contract properties (drawn from public audit reports, Certora community rules, and GitHub repositories). At query time, the target contract's code is embedded and the most semantically similar existing properties are retrieved and included in the LLM prompt as in-context examples.
2. **LLM property generation**: GPT-4 (primary backbone) is prompted with the retrieved properties plus the contract source to generate new candidate properties expressed in the target specification language (Certora Verification Language CVL, Solidity-based Echidna invariants, or Halmos assertions).
3. **Multi-tool verification backends**: Generated properties are checked by (a) Certora Prover (SMT-based formal verification using CVL rules), (b) Halmos (symbolic execution), and (c) Echidna (property-based fuzzing). Using multiple backends increases coverage across different property types.
4. **Iterative property refinement loop**:
   - Step 1: Generate candidate properties via RAG-augmented LLM.
   - Step 2: Submit to the verification/fuzzing backend.
   - Step 3: Parse results — if a property is rejected, counterexamples, violation traces, or syntax errors are fed back to the LLM.
   - Step 4: LLM revises the property using the error context.
   - Step 5: Repeat for N rounds or until the property is accepted.
5. **Evaluation**: Assessed on a benchmark of real-world DeFi protocol contracts (including known-buggy contracts from audit datasets) measuring property correctness, bug recall, and novel bug discovery.

---

## Main Findings

- PropertyGPT significantly outperforms zero-shot LLM property generation (no RAG) across all backends, confirming that retrieved similar properties are essential scaffolding for the LLM.
- The iterative refinement loop substantially improves final property correctness — a large fraction of initially rejected properties are successfully repaired within a small number of feedback rounds.
- The system detects known vulnerabilities in the benchmark contracts with high recall, and reports finding several previously unknown bugs in deployed DeFi contracts.
- Certora CVL properties, being more complex to express, require more refinement rounds than Echidna Solidity invariants, but yield stronger formal guarantees when verified.
- RAG-based generation consistently outperforms both pure prompting and fine-tuning baselines, suggesting that domain-specific retrieval is more data-efficient than retraining for formal specification tasks.

---

## Relevance to This Project

*(LLM-based repair of Aptos Move smart contracts using Move Prover as formal verifier oracle, with iterative feedback loop)*

- **Closest published analogue to this project's core loop**: PropertyGPT's architecture — LLM generates formal properties, a verifier checks them, errors are fed back, LLM revises, repeat — is structurally identical to this project's pipeline, differing only in language (Solidity/CVL vs. Move/Move Spec Language) and verifier (Certora/Halmos vs. Move Prover/Z3). PropertyGPT provides the strongest published validation that this loop is tractable for smart contract formal verification.
- **RAG as a mechanism to seed Move specifications**: PropertyGPT demonstrates that retrieving similar verified contracts as in-context examples dramatically improves LLM property generation. This project can adopt the same technique by building a vector database of verified Aptos Move modules (from the Aptos framework and ecosystem) to retrieve analogous specs when repairing a target contract.
- **Iterative refinement loop design details**: PropertyGPT's specific loop design — parsing verifier errors into structured feedback, capping iterations, handling syntax vs. semantic failures differently — offers concrete engineering patterns directly applicable to the Move Prover feedback loop (which produces similar categories of errors: type errors, precondition failures, postcondition violations, loop invariant breaks).
- **Multi-backend evaluation approach**: PropertyGPT's use of multiple verification/fuzzing backends (Certora, Halmos, Echidna) to triangulate property quality is analogous to combining Move Prover verification with Move unit tests and the Aptos framework's test harness, strengthening confidence beyond what any single oracle provides.
- **Property database construction**: PropertyGPT's pre-built property database from audit reports and community rules maps directly onto the idea of mining Move Prover spec annotations from the open-source Aptos framework codebase to build a retrieval corpus, enabling few-shot prompting grounded in real, verified Move specifications.
