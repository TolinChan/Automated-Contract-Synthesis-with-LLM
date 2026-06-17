"""Summarize feedback-loop ablations on feedback-eligible functions."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from metadata_extractor import FEASIBILITY_DIR
from synth_common import utc_timestamp

RESULTS_DIR = FEASIBILITY_DIR / "results"

CONDITION_RUNS = {
    "+Raw-1": [("p2_raw1_deepseek_20260527", "raw1")],
    "+Raw-3": [("p2_raw3_deepseek_20260527", "raw3")],
    "+Diag-1": [
        ("p2_diag1_deepseek_20260525", "b6"),
        ("p2exp_diag1_deepseek_20260526", "b6"),
    ],
    "+Diag-3": [
        ("p2_diag3_deepseek_20260525", "b7"),
        ("p2exp_diag3_deepseek_20260526", "b7"),
    ],
}


def load_target_ids(manifest_path: Path) -> list[str]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return sorted(
        row["id"]
        for row in payload.get("rows", [])
        if row.get("feedback_eligible")
    )


def load_function_summary(run_id: str, artifact_tag: str, fn_id: str) -> dict | None:
    path = RESULTS_DIR / run_id / artifact_tag / fn_id / "summary.json"
    if not path.is_file():
        return None
    row = json.loads(path.read_text(encoding="utf-8"))
    row["run_id"] = run_id
    row["artifact_tag"] = artifact_tag
    return row


def summarize_condition(condition: str, runs: list[tuple[str, str]], target_ids: list[str]) -> tuple[dict, list[dict]]:
    per_function: list[dict] = []
    for fn_id in target_ids:
        fn_summary = None
        for run_id, artifact_tag in runs:
            fn_summary = load_function_summary(run_id, artifact_tag, fn_id)
            if fn_summary is not None:
                break
        if fn_summary is None:
            per_function.append(
                {
                    "condition": condition,
                    "id": fn_id,
                    "present": False,
                    "run_id": None,
                    "artifact_tag": None,
                    "round0_passed": None,
                    "passed": False,
                    "true_repair": False,
                    "rounds_to_success": None,
                    "feedback_rounds_budget": None,
                    "final_error_summary": "missing_result",
                }
            )
            continue

        history = fn_summary.get("history") or []
        round0_passed = bool(history[0].get("passed")) if history else None
        passed = bool(fn_summary.get("passed"))
        true_repair = bool(round0_passed is False and passed)
        final_error = history[-1].get("error_summary", "") if history else ""
        per_function.append(
            {
                "condition": condition,
                "id": fn_id,
                "present": True,
                "run_id": fn_summary.get("run_id"),
                "artifact_tag": fn_summary.get("artifact_tag"),
                "round0_passed": round0_passed,
                "passed": passed,
                "true_repair": true_repair,
                "rounds_to_success": fn_summary.get("rounds_to_success"),
                "feedback_rounds_budget": fn_summary.get("feedback_rounds_budget"),
                "final_error_summary": final_error,
            }
        )

    present_rows = [r for r in per_function if r["present"]]
    round0_failed = [r for r in present_rows if r["round0_passed"] is False]
    true_repairs = [r for r in present_rows if r["true_repair"]]
    summary = {
        "condition": condition,
        "target_count": len(target_ids),
        "present_count": len(present_rows),
        "loop_success_count": sum(1 for r in present_rows if r["passed"]),
        "loop_success_rate": (
            sum(1 for r in present_rows if r["passed"]) / len(present_rows)
            if present_rows else None
        ),
        "round0_pass_count": sum(1 for r in present_rows if r["round0_passed"] is True),
        "round0_failed_count": len(round0_failed),
        "true_repair_count": len(true_repairs),
        "true_repair_rate": (
            len(true_repairs) / len(round0_failed)
            if round0_failed else None
        ),
        "missing_count": len(target_ids) - len(present_rows),
    }
    return summary, per_function


def main() -> int:
    p = argparse.ArgumentParser(description="Build feedback comparison summary.")
    p.add_argument(
        "--manifest",
        default=str(RESULTS_DIR / "benchmark_manifest_20260526.json"),
    )
    p.add_argument(
        "--output-json",
        default=str(RESULTS_DIR / "feedback_comparison_20260527.json"),
    )
    p.add_argument(
        "--output-csv",
        default=str(RESULTS_DIR / "feedback_comparison_20260527.csv"),
    )
    args = p.parse_args()

    target_ids = load_target_ids(Path(args.manifest))
    condition_summaries: list[dict] = []
    per_function_rows: list[dict] = []
    for condition, runs in CONDITION_RUNS.items():
        summary, rows = summarize_condition(condition, runs, target_ids)
        condition_summaries.append(summary)
        per_function_rows.extend(rows)

    payload = {
        "created_at_utc": utc_timestamp(),
        "target_count": len(target_ids),
        "target_ids": target_ids,
        "conditions": condition_summaries,
        "rows": per_function_rows,
    }

    out_json = Path(args.output_json)
    out_csv = Path(args.output_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "condition",
            "id",
            "present",
            "run_id",
            "artifact_tag",
            "round0_passed",
            "passed",
            "true_repair",
            "rounds_to_success",
            "feedback_rounds_budget",
            "final_error_summary",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(per_function_rows)

    print(f"comparison_json={out_json}")
    print(f"comparison_csv={out_csv}")
    for row in condition_summaries:
        print(
            f"{row['condition']}: loop={row['loop_success_count']}/{row['present_count']} "
            f"true_repair={row['true_repair_count']}/{row['round0_failed_count']} "
            f"missing={row['missing_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
