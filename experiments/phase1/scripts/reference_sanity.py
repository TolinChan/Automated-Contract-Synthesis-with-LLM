"""Batch reference-body sanity checks for Phase 1 benchmark functions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from metadata_extractor import FEASIBILITY_DIR, load_registry
from synth_common import utc_timestamp
from verify_synth import verify


def parse_ids(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    ids = {item.strip() for item in raw.split(",") if item.strip()}
    return ids or None


def main() -> int:
    p = argparse.ArgumentParser(description="Verify reference bodies and write structured sanity results.")
    p.add_argument("--ids", help="Comma-separated function ids. Omit to verify every registry entry.")
    p.add_argument(
        "--output",
        default=str(FEASIBILITY_DIR / "results" / "reference_sanity_20260526.json"),
        help="JSON output path.",
    )
    args = p.parse_args()

    requested_ids = parse_ids(args.ids)
    registry = load_registry()
    selected = [
        fn for fn in registry
        if requested_ids is None or fn.id in requested_ids
    ]
    if not selected:
        raise SystemExit("No functions matched requested ids.")

    missing = (requested_ids or set()) - {fn.id for fn in selected}
    if missing:
        raise SystemExit(f"Unknown function id(s): {', '.join(sorted(missing))}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    payload = {
        "created_at_utc": utc_timestamp(),
        "total": 0,
        "passed": 0,
        "rows": rows,
    }

    for fn in selected:
        body_path = FEASIBILITY_DIR / "functions" / fn.id / "reference_body.txt"
        body = body_path.read_text(encoding="utf-8") if body_path.is_file() else ""
        if not body:
            row = {
                "id": fn.id,
                "passed": False,
                "exit_code": None,
                "prove_time_sec": 0.0,
                "error_summary": "reference_body_missing",
            }
        else:
            res = verify(fn.id, body, timeout_sec=600)
            row = {
                "id": fn.id,
                "passed": bool(res.passed),
                "exit_code": res.exit_code,
                "prove_time_sec": res.prove_time_sec,
                "error_summary": res.error_summary,
            }
        rows.append(row)
        payload["total"] = len(rows)
        payload["passed"] = sum(1 for r in rows if r["passed"])
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(
            f"{fn.id}: passed={row['passed']} exit={row['exit_code']} "
            f"time={row['prove_time_sec']}s summary={row['error_summary']!r}"
        )

    return 0 if payload["passed"] == payload["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
