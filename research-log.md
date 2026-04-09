# Research Log

Chronological record of research decisions and actions. Append-only.

| # | Date | Type | Summary |
|---|------|------|---------|
| 2 | 2026-04-09 | bootstrap | Literature survey complete. 8 papers summarized in literature/. Three new papers added: SmartInv (IEEE S&P 2025, Solidity invariant inference with feedback loop), DafnyBench (1702 Dafny tasks, GPT-4o 64% pass@1 — closest benchmark analog to our Move Prover tasks), PropertyGPT (RAG+CVL property generation+Certora loop — structurally closest end-to-end analogue to our pipeline). survey.md written. All 8 papers rated High relevance. Key gap confirmed: no prior work targets Move/Move Prover with coding agent iterative repair. Direction: proceed to inner loop — run Pass@1 baseline on T0-T2. |
| 1 | 2026-04-09 | bootstrap | Initialized autoresearch workspace. Project: LLM-based repair of injected bugs in Aptos Move smart contracts using Move Prover as verifier oracle. Core architecture: spec → LLM edit → `aptos move prove`/`aptos move test` → parse feedback → LLM edit → repeat. Prior work already covered: SYSSPEC/FAST'26, RePair/CodeNet4Repair, Clover, Reflexion, SWE-agent. 3 new papers identified and verified: SmartInv (IEEE S&P 2025, arXiv:2411.13073), DafnyBench (arXiv:2406.08467), PropertyGPT (arXiv:2405.02580). PoC completed: simple T0 bug fixed by LLM in 1 round; defi::locked_coins revealed "no spec → no proof" constraint. 4 hypotheses formed. Proxy metric: pass_rate. Next: read 3 new papers, write literature summaries, then run Pass@1 baseline experiments. |
