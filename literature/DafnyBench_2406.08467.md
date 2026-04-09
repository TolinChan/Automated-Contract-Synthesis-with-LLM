# Literature Note: DafnyBench — A Benchmark for Formal Software Verification

## Metadata

- **Title**: DafnyBench: A Benchmark for Formal Software Verification
- **Authors**: Chloe Loughridge, Qinyi Sun, Seth Ahrenbach, Federico Cassano, Chuyue Sun, Ying Sheng, Anish Mudide, Nada Amin, Nikhil Swamy, Max Tegmark
- **Year**: 2024
- **Venue**: arXiv preprint (June 2024); arXiv:2406.08467
- **arXiv ID**: 2406.08467
- **URL**: https://arxiv.org/abs/2406.08467

---

## Abstract

We introduce DafnyBench, the largest benchmark for LLM-based formal software verification. We test the ability of LLMs to write enough correct Dafny code that the Dafny program verifier accepts. DafnyBench consists of 1,702 Dafny programming tasks, the majority of which come from MBPP and HumanEval translated into Dafny, and the rest from existing Dafny repositories. The benchmark tests synthesis of Dafny code including loop invariants, pre- and post-conditions, assertions, termination metrics, and ghost variables. We evaluate several state-of-the-art LLMs, including GPT-4o, Claude 3 Opus, Gemini 1.5 Pro, and open-source models, and find that the best model, GPT-4o, correctly verified 64.0% of problems with one attempt. We also perform experiments to better understand how LLMs perform on formal verification tasks, including the effect of providing hints and the importance of different benchmark components.

---

## Key Methodology

1. **Benchmark construction**: 1,702 Dafny tasks assembled from two sources — (a) MBPP and HumanEval programming problems translated into Dafny with full specifications, and (b) existing Dafny repositories. Tasks cover loop invariants, pre/postconditions, assertions, termination metrics, and ghost variables.
2. **Evaluation protocol**: LLMs are prompted to produce a complete, verifiable Dafny program for each task. A solution is accepted if and only if the Dafny verifier (backed by Z3) reports no errors — a binary pass/fail signal from the formal verifier.
3. **Models evaluated**: GPT-4o, Claude 3 Opus, Gemini 1.5 Pro, and several open-source LLMs are compared at pass@1 (single attempt).
4. **Hint experiments**: Ablations study the impact of providing partial specifications, hints, or examples to the LLM, measuring how much guidance narrows the gap between current LLM capabilities and full verification success.
5. **Component analysis**: The benchmark components (translated tasks vs. native Dafny tasks, different specification element types) are analysed separately to identify which aspects are hardest for LLMs.

---

## Main Findings

- GPT-4o achieves the highest pass@1 rate at 64.0%; other frontier models (Claude 3 Opus, Gemini 1.5 Pro) score notably lower, and open-source models trail further behind.
- Providing hints (partial specifications or examples) meaningfully improves LLM success rates, demonstrating that the bottleneck is often the formal annotation rather than the algorithmic logic.
- Loop invariants and termination metrics are consistently the hardest specification elements for LLMs to generate correctly.
- Translated tasks (MBPP/HumanEval converted to Dafny) are generally easier than tasks sourced natively from Dafny repositories, suggesting that problem familiarity aids LLM performance.
- There is a substantial gap between state-of-the-art LLM performance (64%) and full benchmark coverage, establishing clear headroom for future research.
- The binary verifier signal (accept/reject) provides a clean, unambiguous evaluation criterion that removes human judgment from the loop.

---

## Relevance to This Project

*(LLM-based repair of Aptos Move smart contracts using Move Prover as formal verifier oracle, with iterative feedback loop)*

- **Direct structural analogue**: DafnyBench uses the Dafny verifier (Z3-backed, deductive) as the ground-truth oracle, exactly as this project uses Move Prover (also Z3-backed) as its oracle. The binary pass/fail signal from the verifier is the same evaluation currency in both settings, making DafnyBench the closest published benchmark to what this project needs for Move.
- **LLM capability baseline**: The finding that GPT-4o reaches only 64% at one attempt on Dafny tasks sets a realistic expectation for single-shot LLM performance on Move Prover tasks; it directly motivates the iterative repair loop (multiple attempts with verifier feedback) as the necessary mechanism to push success rates higher.
- **Annotation element difficulty**: DafnyBench's identification of loop invariants and termination conditions as the hardest elements maps directly to Move Prover's most common failure modes (`loop_invariant` and `ensures` clauses); this informs which specification elements the repair agent should prioritise improving.
- **Benchmark design template**: DafnyBench's methodology — collect tasks with known correct solutions, evaluate strictly by verifier acceptance, report pass@k — provides a ready-made blueprint for constructing the Move equivalent benchmark used to evaluate this project.
- **Hint/feedback effect**: The hint experiments show that even lightweight additional context significantly improves LLM performance on formal tasks; this supports the design choice of feeding structured Move Prover error messages (rather than raw logs) back to the LLM in each repair iteration.
