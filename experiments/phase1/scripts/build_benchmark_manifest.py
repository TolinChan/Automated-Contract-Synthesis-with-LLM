"""Build a Phase 1 benchmark manifest from registry, screening, and results."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from metadata_extractor import FEASIBILITY_DIR
from synth_common import utc_timestamp

RESULTS_DIR = FEASIBILITY_DIR / "results"

ZERO_SHOT_RUNS = [
    ("p1_r1_zeroshot_deepseek_20260525", "b1"),
    ("p1_r2_zeroshot_deepseek_20260525", "b1"),
    ("p1_r3_zeroshot_deepseek_20260525", "b1"),
    ("p1exp_r1_zeroshot_deepseek_20260526", "b1"),
    ("p1exp_r2_zeroshot_deepseek_20260526", "b1"),
    ("p1exp_r3_zeroshot_deepseek_20260526", "b1"),
]

CTX_RUNS = [
    ("p1_r1_ctx_deepseek_20260525", "b3"),
    ("p1_r2_ctx_deepseek_20260525", "b3"),
    ("p1_r3_ctx_deepseek_20260525", "b3"),
    ("p1exp_r1_ctx_deepseek_20260526", "b3"),
    ("p1exp_r2_ctx_deepseek_20260526", "b3"),
    ("p1exp_r3_ctx_deepseek_20260526", "b3"),
]

DIAG1_RUNS = [
    ("p2_diag1_deepseek_20260525", "b6"),
    ("p2exp_diag1_deepseek_20260526", "b6"),
]

DIAG3_RUNS = [
    ("p2_diag3_deepseek_20260525", "b7"),
    ("p2exp_diag3_deepseek_20260526", "b7"),
]

RAW1_RUNS = [
    ("p2_raw1_deepseek_20260527", "raw1"),
]

RAW3_RUNS = [
    ("p2_raw3_deepseek_20260527", "raw3"),
]


def parse_registry() -> list[dict]:
    text = (FEASIBILITY_DIR / "functions.yaml").read_text(encoding="utf-8")
    items: list[dict] = []
    cur: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("functions:"):
            continue
        if line.startswith("  - id:"):
            if cur:
                items.append(cur)
                cur = {}
            cur["id"] = line.split(":", 1)[1].strip()
            continue
        m = re.match(r"^    ([a-z_]+):\s*(.+?)\s*$", line)
        if m:
            key, val = m.group(1), m.group(2)
            cur[key] = val.strip().strip('"')
    if cur:
        items.append(cur)
    return items


def load_summary_rows(runs: list[tuple[str, str]]) -> dict[str, list[dict]]:
    by_id: dict[str, list[dict]] = defaultdict(list)
    for run_id, artifact_tag in runs:
        path = RESULTS_DIR / run_id / artifact_tag / "summary.json"
        if not path.is_file():
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        for row in summary.get("rows", []):
            row = dict(row)
            row["run_id"] = run_id
            row["artifact_tag"] = artifact_tag
            by_id[row["id"]].append(row)
    return by_id


def load_screening(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"]: row for row in rows}


def load_reference_sanity(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload.get("rows", [])}


def pass_stats(rows: list[dict]) -> tuple[int, int]:
    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    return passed, total


def category(zero_rows: list[dict], ctx_rows: list[dict]) -> str:
    zero_passed, zero_total = pass_stats(zero_rows)
    ctx_passed, ctx_total = pass_stats(ctx_rows)
    if ctx_total and ctx_passed < ctx_total:
        return "Feedback-eligible"
    if zero_total and ctx_total and zero_passed < zero_total and ctx_passed == ctx_total:
        return "Context-sensitive"
    if zero_total and ctx_total and zero_passed == zero_total and ctx_passed == ctx_total:
        return "Easy"
    return "Unclassified"


def best_round(rows: list[dict]) -> int | None:
    vals = [
        int(row["rounds_to_success"])
        for row in rows
        if row.get("rounds_to_success") is not None
    ]
    return min(vals) if vals else None


def main() -> int:
    p = argparse.ArgumentParser(description="Build the Phase 1 benchmark manifest.")
    p.add_argument(
        "--screening",
        default=str(FEASIBILITY_DIR / "candidate_screening" / "hard_candidates_20260526.json"),
    )
    p.add_argument(
        "--reference-sanity",
        default=str(RESULTS_DIR / "reference_sanity_hard_expansion_20260526.json"),
    )
    p.add_argument(
        "--output-json",
        default=str(RESULTS_DIR / "benchmark_manifest_20260526.json"),
    )
    p.add_argument(
        "--output-csv",
        default=str(RESULTS_DIR / "benchmark_manifest_20260526.csv"),
    )
    args = p.parse_args()

    screening = load_screening(Path(args.screening))
    reference_sanity = load_reference_sanity(Path(args.reference_sanity))
    zero = load_summary_rows(ZERO_SHOT_RUNS)
    ctx = load_summary_rows(CTX_RUNS)
    diag1 = load_summary_rows(DIAG1_RUNS)
    diag3 = load_summary_rows(DIAG3_RUNS)
    raw1 = load_summary_rows(RAW1_RUNS)
    raw3 = load_summary_rows(RAW3_RUNS)

    rows: list[dict] = []
    for item in parse_registry():
        fn_id = item["id"]
        zero_passed, zero_total = pass_stats(zero.get(fn_id, []))
        ctx_passed, ctx_total = pass_stats(ctx.get(fn_id, []))
        diag1_rows = diag1.get(fn_id, [])
        diag3_rows = diag3.get(fn_id, [])
        raw1_rows = raw1.get(fn_id, [])
        raw3_rows = raw3.get(fn_id, [])
        screening_row = screening.get(fn_id, {})
        sanity_row = reference_sanity.get(fn_id, {})
        notes = item.get("notes", "")
        benchmark_set = (
            "hard_expansion_v1"
            if "Hard expansion static criteria" in notes
            else "full_benchmark_v1"
        )
        rows.append(
            {
                "id": fn_id,
                "module": item.get("module", ""),
                "function": item.get("function", ""),
                "source_file": item.get("source_file", ""),
                "spec_file": item.get("spec_file", ""),
                "complexity": item.get("complexity", ""),
                "benchmark_set": benchmark_set,
                "category": category(zero.get(fn_id, []), ctx.get(fn_id, [])),
                "static_features": ";".join(screening_row.get("features", [])),
                "static_score": screening_row.get("score"),
                "reference_sanity_passed": sanity_row.get("passed"),
                "reference_sanity_time_sec": sanity_row.get("prove_time_sec"),
                "zero_shot_passed": zero_passed,
                "zero_shot_total": zero_total,
                "ctx_passed": ctx_passed,
                "ctx_total": ctx_total,
                "feedback_eligible": bool(ctx_total and ctx_passed < ctx_total),
                "diag1_passed": sum(1 for row in diag1_rows if row.get("passed")),
                "diag1_total": len(diag1_rows),
                "diag1_best_rounds_to_success": best_round(diag1_rows),
                "diag3_passed": sum(1 for row in diag3_rows if row.get("passed")),
                "diag3_total": len(diag3_rows),
                "diag3_best_rounds_to_success": best_round(diag3_rows),
                "raw1_passed": sum(1 for row in raw1_rows if row.get("passed")),
                "raw1_total": len(raw1_rows),
                "raw1_best_rounds_to_success": best_round(raw1_rows),
                "raw3_passed": sum(1 for row in raw3_rows if row.get("passed")),
                "raw3_total": len(raw3_rows),
                "raw3_best_rounds_to_success": best_round(raw3_rows),
                "notes": notes,
            }
        )

    summary = {
        "created_at_utc": utc_timestamp(),
        "total_functions": len(rows),
        "by_benchmark_set": {
            name: sum(1 for row in rows if row["benchmark_set"] == name)
            for name in sorted({row["benchmark_set"] for row in rows})
        },
        "feedback_eligible_count": sum(1 for row in rows if row["feedback_eligible"]),
        "rows": rows,
    }

    out_json = Path(args.output_json)
    out_csv = Path(args.output_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"manifest_json={out_json}")
    print(f"manifest_csv={out_csv}")
    print(f"total={summary['total_functions']} feedback_eligible={summary['feedback_eligible_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
