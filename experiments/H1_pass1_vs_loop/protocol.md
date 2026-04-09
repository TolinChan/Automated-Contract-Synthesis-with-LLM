# Experiment Protocol: H1 — Pass@1 Baseline (T0–T2)

**Hypothesis**: H1 — Iterative verifier-feedback achieves higher pass rate than single-shot (Pass@1).

**This experiment**: Establish the Pass@1 baseline for T0, T1, T2 using single-shot API calls.

## What
- Run `invoke_ofox_once.py` on T0 (t0_plus1), T1 (t1_aborts), T2 (t2_hello_blockchain)
- Model: `openai/gpt-4o` (comparable to DafnyBench baseline: GPT-4o at 64% pass@1)
- Apply output with `check_task.py` (T0/T1) or via `apply_and_check_mbe.py` pattern
- Record: pass/fail per task, model response quality observations

## Why
- Establishes Pass@1 baseline before running multi-round loop (exp_baseline_B)
- DafnyBench shows GPT-4o at 64% pass@1 on Dafny — Move is lower-resource, expect lower
- H2 sub-test: raw fail.log sufficient for T0/T1 without Error Translation layer?

## Prediction
- T0 (trivial off-by-one): Pass@1 likely succeeds — counterexample is a single value
- T1 (aborts_if): Pass@1 may succeed — abort condition is explicit in the spec
- T2 (unit test): Pass@1 likely succeeds — test failure message is readable
- Overall Pass@1 rate for T0–T2: ≥ 2/3

## Protocol
1. `invoke_ofox_once.py --task-id t0_plus1 --model openai/gpt-4o`
2. `check_task.py --task-id t0_plus1` → record exit code
3. Repeat for t1_aborts, t2_hello_blockchain
4. Save model_response.txt copies to experiments/H1_pass1_vs_loop/results/

## Metric
- Pass@1: binary per task (0 or 1), fraction across T0–T2
