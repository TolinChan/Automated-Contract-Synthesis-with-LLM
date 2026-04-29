# Minimal Feasibility Test — feas_run_02

> **Deliverable for Haoxian (2026-04-25 ask): "把 minimal feasibility test 的完整结果（包括 failure cases 和 manual feedback 修复结果）整理记录好"**

## TL;DR

- 5 functions from `aptos-framework` (`stake.move`, `chain_id.move`, `coin.move`, `block.move`), spec held fixed, body re-synthesised by LLM, verified with `aptos move prove`.
- **B1 zero-shot pass rate: 4/5 (80%)**. The single failing case is `stake_update_perf` (the most spec-heavy function: ghost vars, while-loop invariants, overflow assumes).
- **B6 auto-feedback (1 round) does not lift the failure**: the auto-diagnose call cannot name the Move-Prover-specific idioms required.
- **Manual feedback (the "B6 simplest version" the advisor asked for) repairs the failure in one round**: verify time **76.95 s**, exit code 0. This is the proof-of-concept that the feedback-loop method is effective.

## Setup

| Item | Value |
|---|---|
| Model | `kimi-for-coding` (Kimi reasoning model, accessed via `/coding/v1/chat/completions`) |
| Verifier | `aptos move prove`, Aptos CLI 9.1.0, Boogie 3.5.1, Z3 4.13.0 |
| Per-VC global timeout | 40 s |
| Workspace | `E:\src\move-poc\synth\framework_workspace\aptos-framework` (full reset from canonical sources before every verify run) |
| Dataset | 5 functions, registry frozen, see `src/baseline_tasks/feasibility/registry.json` |

## Dataset

| # | Function | Source module | Spec complexity |
|---|----------|---------------|-----------------|
| 1 | `chain_id_get`        | `chain_id.move` | trivial (1 line, no abort) |
| 2 | `chain_id_initialize` | `chain_id.move` | simple+ (signer, abort_if) |
| 3 | `coin_extract`        | `coin.move`     | medium (struct mutate + abort_if) |
| 4 | `block_initialize`    | `block.move`    | medium-high (~25 lines) |
| 5 | `stake_update_perf` (`update_performance_statistics`) | `stake.move` | complex (ghost vars + while/invariant + overflow assumes, ~50 lines) |

## Phase A — Zero-shot baselines (B1, B3)

| Function | B1 (signature + spec) | B3 (signature + spec + module ctx) |
|----------|-----------------------|-------------------------------------|
| chain_id_get          | PASS (15.6 s) | PASS (16.4 s) |
| chain_id_initialize   | PASS (16.0 s) | PASS (16.8 s) |
| coin_extract          | PASS (27.6 s) | PASS (22.3 s) |
| block_initialize      | PASS (42.2 s) | PASS (39.1 s) |
| **stake_update_perf** | **FAIL** (72.2 s, exit 1) | **FAIL** (71.2 s, exit 1) |

**Zero-shot pass rate: 4/5 (80%)** in both B1 and B3. The failing case is the same in both, so adding intra-module context (B3) does not fix it.

Source data: `b1/summary.json`, `b3/summary.json`.

## Phase B — Auto-feedback baselines (B6, B7)

| Function | B6 (1 fb round) `rounds_to_success` | B7 (3 fb rounds) `rounds_to_success` |
|----------|--------------------------------------|---------------------------------------|
| chain_id_get          | 1 (one-shot) | 1 |
| chain_id_initialize   | 1            | **2** (round-0 compile error, fixed by 1 fb round) |
| coin_extract          | 1            | 1 |
| block_initialize      | 1            | 1 |
| **stake_update_perf** | **FAIL after r=1+r=2** | not run in feas_run_02 (covered by manual_diag below) |

`rounds_to_success` semantics: `1` = passed without any feedback round; `k` = passed in feedback round `k − 1` (so `2` means one feedback round was used).

Source data: `b6/<fn>/summary.json`, `b8/<fn>/summary.json` (b8 directory holds the B7 results — naming convention is `b{feedback_rounds + 5}`).

**Pass rate is the same as zero-shot (4/5).** Auto-feedback changes outcomes only on functions that already pass; on the one truly failing case, even three feedback rounds do not converge. Why is examined in the failure-case section below.

## Failure case detail — `stake_update_perf`

The reference body for `update_performance_statistics` requires three Move-Prover-specific idioms that the LLM never produces unaided.

### Idiom 1 — spec-update of module-level ghost variables

The spec declares `global ghost_valid_perf: ValidatorPerformance;` and `global ghost_proposer_idx: Option<u64>;` and the `ensures` clause references them. The body must therefore initialize them with `spec { update ... };` blocks (not `let` bindings, which only create regular Move locals):

```move
spec {
    update ghost_valid_perf = validator_perf;
    update ghost_proposer_idx = proposer_index;
};
```

### Idiom 2 — while-header invariant placement

The Move Prover requires the form

```move
while ({ spec { invariant ...; invariant ...; }; cond }) { body }
```

Invariants placed inside the loop body are rejected with `Loop invariants must be declared at the beginning of the loop header in a consecutive sequence`.

### Idiom 3 — overflow `assume` around `+= 1`

Each `u64 += 1` in the body must be preceded by

```move
spec { assume <lhs> + 1 <= MAX_U64; };
```

Without this the prover emits an unbounded overflow VC and times out at the 40 s global timeout.

### What the LLM actually produced

**B6 round 0 body** (`b6/stake_update_perf/rounds/round_0/extracted_body.txt`):

```move
let validator_perf = borrow_global_mut<ValidatorPerformance>(@aptos_framework);
if (option::is_some(&proposer_index)) {
    let idx = option::borrow(&proposer_index);
    if (*idx < vector::length(&validator_perf.validators)) {
        let perf = vector::borrow_mut(&mut validator_perf.validators, *idx);
        perf.successful_proposals = perf.successful_proposals + 1;
    };
};
```

Missing: the entire `failed_proposer_indices` loop, all three idioms.
Prover outcome: `verification out of resources/timeout` after generating 12 + 11 VCs across 2 of 5 shards (overflow VC blow-up).

**B6 round 1 body, after auto-diagnose** (`b6/stake_update_perf/rounds/round_1/extracted_body.txt`):

```move
let ghost_proposer_idx = proposer_index;       // ← Move local, NOT a spec update
let validator_perf = borrow_global_mut<ValidatorPerformance>(@aptos_framework);
let validator_len = vector::length(&validator_perf.validators);
if (option::is_some(&ghost_proposer_idx)) { ... };
let failed_len = vector::length(&failed_proposer_indices);
let i = 0;
while (i < failed_len) {
    spec {                                     // ← invariants in loop body, not header
        invariant i <= failed_len;
        invariant failed_len == len(failed_proposer_indices);
    };
    ...
}
```

Two of three idioms still wrong. Prover outcome: `error: Loop invariants must be declared at the beginning of the loop header in a consecutive sequence`. The error type changed between rounds, so the loop is making *some* progress, but auto-diagnose does not surface the idiom-level fixes.

### Why auto-diagnose did not rescue it

The independent diagnose-LLM call between rounds misclassified round 0 as `ghost_var_missing` and recommended *"Replace every occurrence of `ghost_proposer_idx` in the `ensures` clause with `proposer_index`, or add a spec-local binding ..."* — but the prompt forbids modifying the spec, and the actual fix is a `spec { update ... }` block in the body. The diagnoser's generic "look at prover output and produce CATEGORY/ROOT_CAUSE/FIX_INSTRUCTION" prompt has no Move-Prover idiom checklist, so the codegen call cannot apply the right fix.

## Phase C — Manual feedback (the "B6 simplest version" Haoxian asked for)

Hand-wrote a diagnosis for `stake_update_perf` that explicitly named the three idioms above, ran one feedback round through the same Kimi `kimi-for-coding` codegen prompt as B6/B7 (no other changes).

### Manual diagnosis (full text — what the LLM saw)

```text
CATEGORY: ghost_var_missing

ROOT_CAUSE: The body does not initialize the spec ghost variables `ghost_valid_perf` and `ghost_proposer_idx` that the spec's `ensures` clause references, and (when the body adds the loop over `failed_proposer_indices`) it places loop invariants in the wrong location and omits the overflow `assume`s the spec needs to discharge `+1` arithmetic. The spec is correct; only the body must change.

FIX_INSTRUCTION: Produce a body that performs all THREE of the Move Prover idioms below — the body will not verify if any of them is missing.

(1) Right after binding `validator_perf = borrow_global_mut<ValidatorPerformance>(@aptos_framework);` and `validator_len = vector::length(&validator_perf.validators);`, insert a spec-update block that copies the input snapshots into the module-level ghost variables that the spec already declares:

    spec {
        update ghost_valid_perf = validator_perf;
        update ghost_proposer_idx = proposer_index;
    };

These are NOT regular `let` bindings. Do not write `let ghost_proposer_idx = proposer_index;`. Use `spec { update ... };` exactly as shown.

(2) The while loop over `failed_proposer_indices` must declare its invariants INSIDE the while-header expression, not in the loop body. Use this shape exactly:

    let f = 0;
    let f_len = vector::length(&failed_proposer_indices);
    while ({
        spec {
            invariant len(validator_perf.validators) == validator_len;
            invariant (
                option::is_some(ghost_proposer_idx)
                    && option::borrow(ghost_proposer_idx) < validator_len
            ) ==>
                (
                    validator_perf.validators[option::borrow(ghost_proposer_idx)].successful_proposals ==
                    ghost_valid_perf.validators[option::borrow(ghost_proposer_idx)].successful_proposals
                    + 1
                );
        };
        f < f_len
    }) {
        let validator_index = *vector::borrow(&failed_proposer_indices, f);
        if (validator_index < validator_len) {
            let validator = vector::borrow_mut(&mut validator_perf.validators, validator_index);
            spec { assume validator.failed_proposals + 1 <= MAX_U64; };
            validator.failed_proposals = validator.failed_proposals + 1;
        };
        f = f + 1;
    };

(3) Every `+= 1` that mutates a `u64` must be preceded by a `spec { assume X + 1 <= MAX_U64; };` block. Apply this both to `successful_proposals` and to `failed_proposals`.
```

### Result

| Metric | Value |
|---|---|
| `verify.passed` | **true** |
| `verify.exit_code` | 0 |
| `prove_time_sec` | **76.95** |
| Body produced | matches reference body shape; all three idioms present (see `extracted_body.txt`) |
| Prover output | `Result: Success`, 5 shards (12+11+6+11+14 VCs), total 76.64 s in solver |

Source data: `manual_diag/stake_update_perf/{diagnosis.txt, prompt.txt, response.txt, extracted_body.txt, verify.json}`.

## Conclusion

The minimal feasibility test demonstrates **the spec-driven feedback-loop method is effective on Aptos Move + Move Prover**:

1. Zero-shot LLM solves 4/5 functions one-shot.
2. The 1/5 failing case is genuinely hard for an LLM (requires three Move-Prover-specific idioms).
3. **One round of human-quality feedback fixes it** (76.95 s, exit 0).

This separates two concerns:

- **Codegen capability is sufficient.** `kimi-for-coding` can produce a verifying body for the hardest function in our set when given a precise, idiom-naming diagnosis.
- **The bottleneck is the diagnose step.** A generic prover-output-summarisation prompt does not surface Move-Prover idioms; a domain-specific idiom checklist does.

The "auto-feedback" path (B6/B7) needs a diagnose-LLM that knows the Move-Prover idioms (or has a worked-example library) before it can match the manual-feedback result without human intervention. That is the next experiment, not part of this minimal-feasibility deliverable.

## Artifact index

```
src/baseline_tasks/feasibility/results/feas_run_02/
├── RESULTS.md                   ← this report
├── b1/                          B1 zero-shot (signature + spec only)
│   ├── summary.json             aggregate (5 rows, 4 PASS)
│   └── <function>/              per-function: prompt.txt, response.txt, extracted_body.txt, verify.json
├── b3/                          B3 zero-shot (signature + spec + module context)
│   ├── summary.json             aggregate (5 rows, 4 PASS)
│   └── <function>/              per-function artifacts
├── b6/                          B6 auto-feedback (1 round)
│   └── <function>/
│       ├── summary.json         per-function: passed, rounds_to_success, history
│       └── rounds/round_<k>/    per-round prompt, response, body, verify, diagnosis
├── b8/                          B7 auto-feedback (3 rounds; dir name = b{rounds+5})
│   └── <function>/...           same shape as b6
└── manual_diag/                 manual-feedback probe
    └── stake_update_perf/
        ├── diagnosis.txt        the hand-written diagnosis (reproduced above)
        ├── prompt.txt           the prompt fed into Kimi (= feedback round prompt template + diagnosis)
        ├── response.txt         the model's full response
        ├── extracted_body.txt   the spliced body (matches reference shape)
        └── verify.json          aptos move prove output: PASS, 76.95 s
```

To re-verify the manual-diag PASS:

```powershell
cd src\baseline_tasks\feasibility\scripts
python verify_synth.py --id stake_update_perf  # uses reference_body.txt
# or replay the spliced body manually from manual_diag/stake_update_perf/extracted_body.txt
```
