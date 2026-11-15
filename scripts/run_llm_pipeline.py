"""Validate LLM candidates (offline JSONL) through the shared validation contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hwe_smith.generators.llm_provider import get_default_provider  # noqa: E402
from hwe_smith.generators.rules import Mutation  # noqa: E402
from hwe_smith.paths import repo_path, sim_timeout_s, work_path  # noqa: E402
from hwe_smith.schema import normalize_verdict  # noqa: E402
from hwe_smith.simulation.runner import SimRunner  # noqa: E402
from run_rules_pipeline import package, validate  # noqa: E402


def to_mutation(c) -> Mutation:
    return Mutation(
        mut_id=c.cand_id,
        file=c.file,
        category=c.category,
        original=c.original,
        modified=c.modified,
        expected_effect=c.expected_behavior,
    )


def main() -> None:
    jsonl = ROOT / "data" / "generated" / "llm_candidates.jsonl"
    provider = get_default_provider(jsonl)
    cands = provider.all()
    print(f"loaded {len(cands)} LLM candidates (offline JSONL)", flush=True)
    repo = repo_path()
    work = work_path()
    runner = SimRunner(repo, work, timeout_s=sim_timeout_s())
    results = []
    for i, c in enumerate(cands):
        rtl = (repo / c.file).read_text()
        safe, reason = provider.generate(
            cand_id=c.cand_id,
            file=c.file,
            rtl_text=rtl,
            context="uart peripheral",
            spec="UART LSB-first framing",
            category=c.category,
        )
        if safe is None:
            print(f"[{i+1}/{len(cands)}] {c.cand_id} SKIP safety: {reason}", flush=True)
            results.append(
                {
                    "cand_id": c.cand_id,
                    "verdict": "REJECT_INTEGRITY",
                    "status": "REJECT_INTEGRITY",
                    "reason": reason,
                    "strategy": "llm",
                }
            )
            continue
        m = to_mutation(safe)
        print(
            f"[{i+1}/{len(cands)}] {c.cand_id} {c.file} [{c.category}] {c.original[:50]!r}",
            flush=True,
        )
        rec = validate(m, runner, work / "logs", strategy="llm")
        rec["strategy"] = "llm"
        rec["model"] = c.model
        rec["expected_behavior"] = c.expected_behavior
        rec["exposing_condition"] = c.exposing_condition
        status = normalize_verdict(rec.get("status") or rec.get("verdict", ""))
        print(f"    -> {rec.get('verdict')} ({status})", flush=True)
        if status == "ACCEPTED" or rec.get("verdict") == "ACCEPT":
            package(rec)
        results.append(rec)
        (ROOT / "results" / "llm_validation_report.json").write_text(
            json.dumps(
                {
                    "total": len(results),
                    "accepted": sum(
                        1
                        for r in results
                        if r.get("verdict") == "ACCEPT" or r.get("status") == "ACCEPTED"
                    ),
                    "records": results,
                },
                indent=2,
            )
        )
    acc = sum(
        1 for r in results if r.get("verdict") == "ACCEPT" or r.get("status") == "ACCEPTED"
    )
    print(f"LLM DONE: {acc}/{len(cands)} validated", flush=True)


if __name__ == "__main__":
    main()
