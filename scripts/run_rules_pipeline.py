"""End-to-end rules pipeline: mutate -> validate -> package."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hwe_smith.generators.rules import Mutation, generate_mutations  # noqa: E402
from hwe_smith.packaging.package import package_task  # noqa: E402
from hwe_smith.paths import repo_path, sim_timeout_s, work_path  # noqa: E402
from hwe_smith.schema import normalize_verdict  # noqa: E402
from hwe_smith.simulation.runner import SimRunner  # noqa: E402
from hwe_smith.validation import contract as _contract  # noqa: E402

REPO = repo_path()
WORK = work_path()
VALIDATED = ROOT / "data" / "validated" / "tasks"
REJECTED = ROOT / "data" / "rejected"
EXPORT = ROOT / "data" / "exports"
REPORT = ROOT / "results" / "generation_report.json"

RTL_FILES = {
    "rtl/uart_rx.v": REPO / "rtl" / "uart_rx.v",
    "rtl/uart_tx.v": REPO / "rtl" / "uart_tx.v",
}
TB_MAP = _contract.TB_MAP


def validate(mut, runner, log_root, repo=None, strategy="rules"):
    """Back-compat wrapper used by LLM/history pipelines and integration tests."""
    return _contract.validate(mut, runner, log_root, repo or REPO, strategy=strategy)


def package(rec: dict) -> dict:
    return package_task(
        rec,
        repo=REPO,
        validated_root=VALIDATED,
        export_root=EXPORT,
    )


def _append_rejected(rec: dict) -> None:
    REJECTED.mkdir(parents=True, exist_ok=True)
    path = REJECTED / "rejected_candidates.jsonl"
    with path.open("a") as f:
        f.write(
            json.dumps(
                {
                    "mut_id": rec.get("cand_id") or (rec.get("mut") or {}).get("mut_id"),
                    "verdict": rec.get("verdict"),
                    "status": normalize_verdict(rec.get("status") or rec.get("verdict", "")),
                    "reason": rec.get("reason"),
                    "strategy": rec.get("strategy", "rules"),
                }
            )
            + "\n"
        )


def main() -> None:
    runner = SimRunner(REPO, WORK, timeout_s=sim_timeout_s())
    rtl_texts = {rel: p.read_text() for rel, p in RTL_FILES.items()}
    muts = generate_mutations(rtl_texts)
    print(f"generated {len(muts)} rule mutations", flush=True)

    results = []
    for i, m in enumerate(muts):
        print(f"[{i+1}/{len(muts)}] {m.mut_id} {m.file} :: {m.original[:60]!r}", flush=True)
        rec = validate(m, runner, WORK / "logs", strategy="rules")
        status = normalize_verdict(rec.get("status") or rec.get("verdict", ""))
        print(f"    -> {rec.get('verdict')} ({status})", flush=True)
        if _contract.is_accepted(rec):
            package(rec)
        else:
            _append_rejected(rec)
        results.append(rec)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(
                {
                    "total_candidates": len(results),
                    "accepted": sum(1 for r in results if _contract.is_accepted(r)),
                    "records": results,
                },
                indent=2,
            )
        )
    acc = sum(1 for r in results if _contract.is_accepted(r))
    print(f"DONE: {acc}/{len(results)} validated", flush=True)


if __name__ == "__main__":
    main()
