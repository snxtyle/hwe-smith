"""Shared fail-to-pass validation contract for all strategies.

Checks:
  1. Baseline PASS on pristine RTL
  2. Mutation applies; compile errors => REJECT_COMPILE_ERROR (not a behavioural bug)
  3. Behavioural FAIL (or reproducible hang/timeout treated as FAIL by runner)
  4. Restore original => PASS
  5. Other module TB still PASS (regression)
  6. Re-apply mutation => FAIL again (reproducibility)
  7. Integrity: workspace file equals pristine+intended mutation only
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from hwe_smith.generators.rules import Mutation, apply_mutation
from hwe_smith.schema import (
    ACCEPTED,
    INFRASTRUCTURE_ERROR,
    normalize_verdict,
)
from hwe_smith.simulation.runner import ERROR, FAIL, PASS, SimRunner

TB_MAP = {
    "rtl/uart_rx.v": "tb/uart_rx",
    "rtl/uart_tx.v": "tb/uart_tx",
}


def apply_to_workspace(ws: Path, mut: Mutation) -> bool:
    f = ws / mut.file
    new = apply_mutation(f.read_text(), mut)
    if new is None:
        return False
    f.write_text(new)
    return True


def restore(ws: Path, mut: Mutation, repo: Path) -> bool:
    """Restore pristine RTL only if current == pristine with intended mutation."""
    f = ws / mut.file
    pristine = (repo / mut.file).read_text()
    current = f.read_text()
    expected = pristine.replace(mut.original, mut.modified, 1)
    if current != expected:
        return False
    f.write_text(pristine)
    return True


def validate(
    mut: Mutation,
    runner: SimRunner,
    log_root: Path,
    repo: Path,
    strategy: str = "rules",
) -> dict:
    """Run the full contract. Returns a record with legacy + normalized verdicts."""
    rec: dict = {
        "mut": mut.to_dict(),
        "strategy": strategy,
        "cand_id": mut.mut_id,
    }
    if mut.file not in TB_MAP:
        rec["verdict"] = "REJECT_INTEGRITY"
        rec["status"] = "REJECT_INTEGRITY"
        rec["reason"] = f"no TB mapping for {mut.file}"
        return rec

    ws = runner.make_workspace(f"cand_{mut.mut_id}")
    tb = TB_MAP[mut.file]

    # Check 1
    base = runner.run_test(ws, tb, log_root / mut.mut_id, tag="baseline")
    rec["baseline"] = base.to_dict()
    if base.status == ERROR:
        rec["verdict"] = "REJECT_BASELINE"
        rec["status"] = INFRASTRUCTURE_ERROR
        rec["reason"] = "baseline environment/compile error"
        return rec
    if base.status != PASS:
        rec["verdict"] = "REJECT_BASELINE"
        rec["status"] = INFRASTRUCTURE_ERROR
        rec["reason"] = "pristine RTL did not PASS"
        return rec

    # Check 2+3
    if not apply_to_workspace(ws, mut):
        rec["verdict"] = "REJECT_NONUNIQUE"
        rec["status"] = "REJECT_INTEGRITY"
        return rec
    mutres = runner.run_test(ws, tb, log_root / mut.mut_id, tag="mutated")
    rec["mutated"] = mutres.to_dict()
    if mutres.status == ERROR:
        # compilation / env failure is not a behavioural hardware bug
        rec["verdict"] = "REJECT_COMPILED_CLEAN"
        rec["status"] = "REJECT_COMPILE_ERROR"
        rec["reason"] = "modified RTL failed to compile or environment error"
        return rec
    if mutres.status != FAIL:
        rec["verdict"] = "REJECT_SURVIVES"
        rec["status"] = "REJECT_SURVIVES"
        rec["reason"] = "mutation did not cause observable test failure"
        return rec

    # Check 4
    if not restore(ws, mut, repo):
        rec["verdict"] = "REJECT_RESTORE_FAILED"
        rec["status"] = "REJECT_INTEGRITY"
        return rec
    restored = runner.run_test(ws, tb, log_root / mut.mut_id, tag="restored")
    rec["restored"] = restored.to_dict()
    if restored.status != PASS:
        rec["verdict"] = "REJECT_RESTORE_NOT_CLEAN"
        rec["status"] = "REJECT_INTEGRITY"
        return rec

    # Check 5
    other = "tb/uart_tx" if tb == "tb/uart_rx" else "tb/uart_rx"
    reg = runner.run_test(ws, other, log_root / mut.mut_id, tag="regression")
    rec["regression"] = reg.to_dict()
    if reg.status != PASS:
        rec["verdict"] = "REJECT_REGRESSION"
        rec["status"] = "REJECT_REGRESSION"
        return rec

    # Check 6
    if not apply_to_workspace(ws, mut):
        rec["verdict"] = "REJECT_REAPPLY_FAILED"
        rec["status"] = "REJECT_INTEGRITY"
        return rec
    mut2 = runner.run_test(ws, tb, log_root / mut.mut_id, tag="mutated_rerun")
    rec["mutated_rerun"] = mut2.to_dict()
    if mut2.status != FAIL:
        rec["verdict"] = "REJECT_FLAKY"
        rec["status"] = "REJECT_NON_REPRODUCIBLE"
        return rec
    restore(ws, mut, repo)

    rec["verdict"] = "ACCEPT"  # legacy compatibility
    rec["status"] = ACCEPTED
    return rec


def is_accepted(rec: dict) -> bool:
    return normalize_verdict(rec.get("status") or rec.get("verdict", "")) == ACCEPTED
