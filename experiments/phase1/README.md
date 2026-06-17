# Phase 1 Formal Experiment Workspace

This is the canonical workspace for the current MoVES Phase 1 experiments.
Use this directory for formal Aptos Move Spec-to-Code runs.

## Layout

| Path | Purpose |
| --- | --- |
| `functions.yaml` | Benchmark registry for Phase 1 functions. |
| `functions/` | Extracted signature, spec, module context, reference body, and metadata. |
| `scripts/` | Current synthesis, feedback, diagnosis, and verification drivers. |
| `results/` | Phase 1 run artifacts and aggregate summaries. |
| `candidate_screening/` | Screening notes for harder candidate functions. |

The older `src/baseline_tasks/feasibility/` tree is historical feasibility
infrastructure. Keep it for evidence and comparison, but do not use it as the
main entry point for new formal Phase 1 runs.

## Quick Start

Run commands from `experiments/phase1/scripts`.

```powershell
cd experiments\phase1\scripts

# Required for Move Prover verification.
$env:BOOGIE_EXE = "C:\Users\96247\.dotnet\tools\boogie.exe"
$env:Z3_EXE     = "E:\tools\z3_extract\z3-4.13.0-x64-win\bin\z3.exe"

# Extract benchmark metadata from aptos-framework.
python metadata_extractor.py

# Zero-shot: signature + spec only. Internal artifact tag: b1.
python synth_b1.py --provider deepseek --model deepseek-v4-pro --id chain_id_get

# +Ctx: signature + spec + module context. Internal artifact tag: b3.
python synth_b3.py --provider deepseek --model deepseek-v4-pro --id chain_id_get

# +Diag-1 / +Diag-3: feedback loop with structured diagnosis.
python synth_loop.py --provider deepseek --model deepseek-v4-pro --feedback-rounds 1 --id stake_update_perf
python synth_loop.py --provider deepseek --model deepseek-v4-pro --feedback-rounds 3 --id stake_update_perf
```

Use paper-facing names in writing and tables: `Zero-shot`, `+Ctx`,
`+Diag-1`, `+Diag-3`, and `Oracle-Diag`. Reserve `b1`, `b3`, `b6`, `b7`,
and `manual_diag` for scripts, result directories, and artifact lookup.
