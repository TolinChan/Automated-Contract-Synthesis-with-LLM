"""Screen hard benchmark candidates by static Move/spec features.

This script is intentionally model-free: it scores aptos-framework functions
using static complexity signals only, so the hard expansion pack is not
selected based on DeepSeek failures.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from metadata_extractor import (
    FEASIBILITY_DIR,
    FRAMEWORK_SRC,
    extract_function,
    extract_spec_block,
    load_registry,
)


PRIMARY_CANDIDATES = [
    ("reconfiguration_reconfigure", "aptos_framework::reconfiguration", "reconfigure", "reconfiguration.move", "reconfiguration.spec.move"),
    ("stake_update_stake_pool", "aptos_framework::stake", "update_stake_pool", "stake.move", "stake.spec.move"),
    ("stake_append", "aptos_framework::stake", "append", "stake.move", "stake.spec.move"),
    ("stake_remove_validators", "aptos_framework::stake", "remove_validators", "stake.move", "stake.spec.move"),
    ("stake_distribute_rewards", "aptos_framework::stake", "distribute_rewards", "stake.move", "stake.spec.move"),
    ("coin_mint_internal", "aptos_framework::coin", "mint_internal", "coin.move", "coin.spec.move"),
    ("storage_gas_on_reconfig", "aptos_framework::storage_gas", "on_reconfig", "storage_gas.move", "storage_gas.spec.move"),
    ("stake_next_validator_consensus_infos", "aptos_framework::stake", "next_validator_consensus_infos", "stake.move", "stake.spec.move"),
    ("fungible_asset_unchecked_withdraw", "aptos_framework::fungible_asset", "unchecked_withdraw", "fungible_asset.move", "fungible_asset.spec.move"),
    ("fungible_asset_unchecked_deposit", "aptos_framework::fungible_asset", "unchecked_deposit", "fungible_asset.move", "fungible_asset.spec.move"),
    ("block_block_prologue_common", "aptos_framework::block", "block_prologue_common", "block.move", "block.spec.move"),
    ("block_emit_new_block_event", "aptos_framework::block", "emit_new_block_event", "block.move", "block.spec.move"),
]

BACKUP_CANDIDATES = [
    ("block_emit_genesis_block_event", "aptos_framework::block", "emit_genesis_block_event", "block.move", "block.spec.move"),
    ("aggregator_v2_string_concat", "aptos_framework::aggregator_v2", "string_concat", "aggregator_v2/aggregator_v2.move", "aggregator_v2/aggregator_v2.spec.move"),
    ("aggregator_v2_copy_snapshot", "aptos_framework::aggregator_v2", "copy_snapshot", "aggregator_v2/aggregator_v2.move", "aggregator_v2/aggregator_v2.spec.move"),
    ("genesis_create_initialize_validators", "aptos_framework::genesis", "create_initialize_validators", "genesis.move", "genesis.spec.move"),
    ("object_grant_permission", "aptos_framework::object", "grant_permission", "object.move", "object.spec.move"),
]


@dataclass
class CandidateReport:
    id: str
    module: str
    function: str
    source_file: str
    spec_file: str
    tier: str
    score: int
    features: list[str]
    reject_reasons: list[str]
    screen_passed: bool
    selected: bool
    selection_note: str


def feature_score(spec_block: str, signature: str, body: str) -> tuple[int, list[str]]:
    hay = "\n".join([spec_block, signature, body])
    features: list[str] = []
    score = 0

    weighted = [
        ("modifies", r"\bmodifies\b", 3),
        ("schema_include", r"\binclude\s+[A-Za-z0-9_]+Schema\b", 3),
        ("old", r"\bold\s*\(", 2),
        ("global_resource", r"\bglobal(?:<|\s*\()", 2),
        ("quantifier", r"\b(forall|exists)\b", 2),
        ("loop_or_vector", r"\bwhile\b|vector::", 3),
        ("table_or_map", r"table::|simple_map::|big_ordered_map", 2),
        ("resource_mutation", r"borrow_global_mut|move_to|move_from", 2),
    ]
    for name, pattern, weight in weighted:
        if re.search(pattern, hay):
            features.append(name)
            score += weight

    aborts = len(re.findall(r"\baborts_if\b", spec_block))
    ensures = len(re.findall(r"\bensures\b", spec_block))
    if aborts >= 3:
        features.append(f"aborts_if={aborts}")
        score += min(aborts, 6)
    if ensures >= 2:
        features.append(f"ensures={ensures}")
        score += min(ensures, 6)

    duration_vals = [
        int(x)
        for x in re.findall(r"verify_duration_estimate\s*=\s*(\d+)", spec_block)
    ]
    if duration_vals:
        duration = max(duration_vals)
        features.append(f"verify_duration_estimate={duration}")
        score += 3 + (2 if duration >= 300 else 0)

    return score, features


def reject_reasons(spec_block: str, score: int, features: list[str]) -> list[str]:
    reasons: list[str] = []
    if "pragma verify = false" in spec_block:
        reasons.append("pragma_verify_false")
    if re.search(r"\baborts_if\s+true\s*;", spec_block):
        reasons.append("aborts_if_true")
    feature_kinds = {
        f.split("=", 1)[0]
        for f in features
    }
    if len(feature_kinds) < 2:
        reasons.append("fewer_than_two_static_feature_classes")
    return reasons


def screen_one(raw: tuple[str, str, str, str, str], tier: str) -> CandidateReport:
    cid, module, function, source_file, spec_file = raw
    reasons: list[str] = []
    score = 0
    features: list[str] = []
    try:
        src = (FRAMEWORK_SRC / source_file).read_text(encoding="utf-8")
        spec = (FRAMEWORK_SRC / spec_file).read_text(encoding="utf-8")
        spec_block = extract_spec_block(spec, function)
        signature, body, _ = extract_function(src, function)
        score, features = feature_score(spec_block, signature, body)
        reasons = reject_reasons(spec_block, score, features)
    except Exception as exc:  # noqa: BLE001 - script report should keep going
        reasons = [f"extract_error:{type(exc).__name__}:{exc}"]
    return CandidateReport(
        id=cid,
        module=module,
        function=function,
        source_file=source_file,
        spec_file=spec_file,
        tier=tier,
        score=score,
        features=features,
        reject_reasons=reasons,
        screen_passed=not reasons,
        selected=False,
        selection_note="",
    )


def write_markdown(path: Path, reports: list[CandidateReport]) -> None:
    lines = [
        "# Hard Candidate Screening",
        "",
        "Static, model-free screening of hard benchmark candidates.",
        "",
        "| tier | id | score | screen_passed | selected | features | reject_reasons | selection_note |",
        "|---|---:|---:|---|---|---|---|---|",
    ]
    for r in reports:
        lines.append(
            f"| {r.tier} | `{r.id}` | {r.score} | {str(r.screen_passed).lower()} | "
            f"{str(r.selected).lower()} | {', '.join(r.features)} | "
            f"{', '.join(r.reject_reasons)} | {r.selection_note} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Screen hard benchmark candidates by static features.")
    p.add_argument("--output-dir", default=str(FEASIBILITY_DIR / "candidate_screening"))
    p.add_argument(
        "--allow-registered",
        action="store_true",
        help="Do not reject candidates that are already in functions.yaml.",
    )
    args = p.parse_args()

    existing_ids = {fn.id for fn in load_registry()}
    reports: list[CandidateReport] = []
    for raw in PRIMARY_CANDIDATES:
        report = screen_one(raw, "primary")
        if report.id in existing_ids and not args.allow_registered:
            report.reject_reasons.append("already_registered")
            report.screen_passed = False
        reports.append(report)
    for raw in BACKUP_CANDIDATES:
        report = screen_one(raw, "backup")
        if report.id in existing_ids and not args.allow_registered:
            report.reject_reasons.append("already_registered")
            report.screen_passed = False
        reports.append(report)

    primary_passed = [r for r in reports if r.tier == "primary" and r.screen_passed]
    backup_passed = [r for r in reports if r.tier == "backup" and r.screen_passed]
    selected_ids = {r.id for r in primary_passed[:12]}
    if len(selected_ids) < 12:
        selected_ids.update(r.id for r in backup_passed[: 12 - len(selected_ids)])
    for r in reports:
        r.selected = r.id in selected_ids
        if r.selected:
            r.selection_note = "selected_for_hard_expansion_v1"
        elif r.screen_passed and r.tier == "backup":
            r.selection_note = "backup_passed_not_needed"
        elif r.screen_passed:
            r.selection_note = "screen_passed_not_selected"
        else:
            r.selection_note = "rejected"

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hard_candidates_20260526.json"
    md_path = out_dir / "hard_candidates_20260526.md"
    json_path.write_text(
        json.dumps([asdict(r) for r in reports], indent=2),
        encoding="utf-8",
    )
    write_markdown(md_path, reports)

    selected = [r for r in reports if r.selected]
    passed = [r for r in reports if r.screen_passed]
    print(f"screened={len(reports)} screen_passed={len(passed)} selected={len(selected)}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    for r in selected:
        print(f"{r.tier}: {r.id} score={r.score} features={','.join(r.features)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
