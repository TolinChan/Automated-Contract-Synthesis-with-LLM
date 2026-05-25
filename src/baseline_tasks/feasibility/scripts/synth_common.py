"""Shared helpers for B1/B3/B6/B7 drivers.

The driver scripts share:
    - calling the configured LLM with system + user messages
    - extracting the body from the response
    - splicing into the workspace and verifying
    - writing per-function artifacts (prompt/response/extracted_body/verify.json)
    - aggregating per-baseline summary.json

Differences (prompt content, multi-round logic) live in the per-baseline scripts.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from body_fence import extract_body
from llm_client import chat
from metadata_extractor import FEASIBILITY_DIR
from verify_synth import verify

RESULTS_DIR = FEASIBILITY_DIR / "results"

SYSTEM_PROMPT = (
    "You are an expert in the Aptos Move language and the Move Prover. "
    "When asked, you produce Move source code that satisfies the given formal specification. "
    "You write nothing outside the requested output markers."
)


@dataclass
class FunctionInputs:
    id: str
    spec_block: str
    signature: str
    module_context: str
    reference_body: str

    @classmethod
    def load(cls, fn_id: str) -> "FunctionInputs":
        d = FEASIBILITY_DIR / "functions" / fn_id
        return cls(
            id=fn_id,
            spec_block=(d / "spec.txt").read_text(encoding="utf-8"),
            signature=(d / "signature.txt").read_text(encoding="utf-8"),
            module_context=(d / "module_context.txt").read_text(encoding="utf-8"),
            reference_body=(d / "reference_body.txt").read_text(encoding="utf-8"),
        )


def utc_run_id() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def call_llm_for_body(
    prompt: str,
    *,
    max_tokens: int,
    temperature: float = 0.2,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    return chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_sec=600,
    )


def write_round_artifacts(round_dir: Path, prompt: str, response: str, body: str | None) -> None:
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (round_dir / "response.txt").write_text(response, encoding="utf-8")
    (round_dir / "extracted_body.txt").write_text(body or "", encoding="utf-8")


def verify_or_extraction_failed(fn_id: str, body: str | None) -> dict:
    if body is None:
        return {
            "function_id": fn_id,
            "passed": False,
            "exit_code": -3,
            "stdout": "",
            "stderr": "Body extraction failed: no <<<BODY...BODY>>> or ```move``` block found.",
            "command": [],
            "prove_time_sec": 0.0,
            "splice_succeeded": False,
            "error_summary": "extraction_failed",
        }
    return verify(fn_id, body, timeout_sec=600).to_json()


def one_shot_run(
    fn_id: str,
    prompt: str,
    out_dir: Path,
    *,
    max_tokens: int,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """Single LLM call + verify; used by B1 and B3. Writes prompt/response/extracted_body/verify.json."""
    response = call_llm_for_body(prompt, max_tokens=max_tokens, provider=provider, model=model)
    body = extract_body(response)
    write_round_artifacts(out_dir, prompt, response, body)
    verify_payload = verify_or_extraction_failed(fn_id, body)
    (out_dir / "verify.json").write_text(json.dumps(verify_payload, indent=2), encoding="utf-8")
    line = (
        f"{fn_id}: passed={verify_payload['passed']} "
        f"exit={verify_payload['exit_code']} "
        f"time={verify_payload.get('prove_time_sec', 0)}s "
        f"summary={verify_payload.get('error_summary', '')!r}"
    )
    (out_dir / "summary.txt").write_text(line + "\n", encoding="utf-8")
    print(line)
    return {
        "id": fn_id,
        "passed": bool(verify_payload["passed"]),
        "exit_code": verify_payload["exit_code"],
        "prove_time_sec": verify_payload.get("prove_time_sec", 0),
        "error_summary": verify_payload.get("error_summary", ""),
        "extraction_failed": body is None,
    }


def write_baseline_summary(run_dir: Path, baseline: str, rows: list[dict]) -> Path:
    summary = {
        "run_id": run_dir.parent.name,
        "baseline": baseline,
        "total": len(rows),
        "passed": sum(1 for r in rows if r.get("passed")),
        "rows": rows,
    }
    out = run_dir / "summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{baseline} summary: {summary['passed']}/{summary['total']} passed -> {out}")
    return out
