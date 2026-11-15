"""Strategy C: historical fix reversion (executed subset of mined commits)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hwe_smith.generators.rules import Mutation  # noqa: E402
from hwe_smith.paths import repo_path, sim_timeout_s, work_path  # noqa: E402
from hwe_smith.schema import normalize_verdict  # noqa: E402
from hwe_smith.simulation.runner import SimRunner  # noqa: E402
from run_rules_pipeline import package, validate  # noqa: E402


def main() -> None:
    repo = repo_path()
    work = work_path()
    runner = SimRunner(repo, work, timeout_s=max(90, sim_timeout_s()))

    # Only reversions that are known to apply cleanly to the pinned HEAD RTL
    # and for which the current TB can observe the old behaviour.
    # Mined-but-not-executed commits remain documented in data/raw/pull_requests.jsonl.
    hist_mutations = [
        Mutation(
            mut_id="HIST_db0017a_rx",
            file="rtl/uart_rx.v",
            category="protocol",
            original="data_reg <= {rxd_reg, data_reg[DATA_WIDTH-1:1]};",
            modified="data_reg <= {data_reg[DATA_WIDTH-2:0], rxd_reg};",
            expected_effect="MSB-first sampling of an LSB-first protocol: every byte bit-reversed",
        ),
        Mutation(
            mut_id="HIST_db0017a_tx",
            file="rtl/uart_tx.v",
            category="protocol",
            original="{data_reg, txd_reg} <= {1'b0, data_reg};",
            modified="{txd_reg, data_reg} <= {data_reg, 1'b0};",
            expected_effect="MSB-first transmission: every byte bit-reversed on the wire",
        ),
    ]

    results = []
    for m in hist_mutations:
        print(f"{m.mut_id}: {m.original[:50]!r}", flush=True)
        # confirm anchor exists on pinned HEAD
        text = (repo / m.file).read_text()
        if text.count(m.original) != 1:
            rec = {
                "mut": m.to_dict(),
                "verdict": "REJECT_NONUNIQUE",
                "status": "REJECT_INTEGRITY",
                "strategy": "history",
                "reason": "historical pattern not uniquely present on pinned commit",
            }
            print(f"    -> SKIP {rec['status']}", flush=True)
            results.append(rec)
            continue
        rec = validate(m, runner, work / "logs", strategy="history")
        rec["strategy"] = "history"
        rec["historical_fix"] = "db0017a22c57731d69a4a2844bc1e4f3f36abd10"
        status = normalize_verdict(rec.get("status") or rec.get("verdict", ""))
        print(f"    -> {rec.get('verdict')} ({status})", flush=True)
        if rec.get("verdict") == "ACCEPT" or status == "ACCEPTED":
            package(rec)
        results.append(rec)

    out = ROOT / "results" / "history_validation_report.json"
    out.write_text(
        json.dumps(
            {
                "total": len(results),
                "accepted": sum(
                    1
                    for r in results
                    if r.get("verdict") == "ACCEPT" or r.get("status") == "ACCEPTED"
                ),
                "executed_mutations": [m.mut_id for m in hist_mutations],
                "note": "Other mined commits in data/raw/pull_requests.jsonl were not executed",
                "records": results,
            },
            indent=2,
        )
    )
    print(
        f"HISTORY DONE: {sum(1 for r in results if r.get('verdict')=='ACCEPT' or r.get('status')=='ACCEPTED')}/{len(results)}"
    )


if __name__ == "__main__":
    main()
