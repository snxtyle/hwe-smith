# HWE-Smith — Validation Methodology

**Implementation:** shared code lives in [`src/hwe_smith/validation/contract.py`](../src/hwe_smith/validation/contract.py) and is reused by rules / LLM / history pipelines.

**Status vocabulary:** records keep a legacy `verdict` (`ACCEPT`, `REJECT_*`) for backward compatibility and a normalized `status` (`ACCEPTED`, `REJECT_SURVIVES`, `REJECT_COMPILE_ERROR`, `REJECT_NON_REPRODUCIBLE`, `REJECT_REGRESSION`, `REJECT_INTEGRITY`, `INFRASTRUCTURE_ERROR`). Compilation / environment failures are **not** counted as behavioural bugs.

## The validation contract

Every candidate passes through a 7-check pipeline before it counts as a task.
A candidate that fails any check is recorded in `data/rejected/` with the
reason — rejected candidates are evidence, not garbage.

| # | Check | Property | Command path |
|---|-------|----------|--------------|
| 1 | Baseline | pristine repo passes its cocotb TB | `run_test(ws, tb)` on untouched copy |
| 2 | Mutated compile | mutation compiles (not just lexes) | same run, exit-code + results.xml |
| 3 | Functional fail | mutated TB fails or hangs | timeout (60s) counts as FAIL |
| 4 | Restoration | reverts cleanly and passes again | reverse-replace, rerun |
| 5 | Regression | *other* module's TB still passes | cross-module run |
| 6 | Reproducibility | mutated fail repeats deterministically | second mutated run |
| 7 | Integrity | mutation touches only the target RTL file | single-file exact-match edit by construction |

Acceptance requires all seven. The measured verdict distribution is in
`results/generation_report.json`.

## Design decisions and why

**Timeout-as-failure.** A corrupted UART stream never terminates a cocotb
`await sink.read()`, so several real bugs manifest as hangs, not assertion
failures. We treat a 60 s timeout as FAIL (with the duration recorded) rather
than excluding hangs, because "test never completes" is exactly how a hardware
engineer experiences these bugs.

**Exact-match single edit.** Mutations are applied via `str.replace` requiring
count==1 in the target file. A mutation whose anchor is not unique is rejected
before any simulation (REJECT_NONUNIQUE), which guarantees Check 7 (integrity)
by construction: no other file is ever opened.

**Restore-by-reverse-replacement.** Rather than re-copying the pristine
workspace (which would mask incomplete reverts), restoration replaces the
mutation text back and is verified by re-running the test. If the original
text does not appear exactly once after mutation, restoration fails loudly.

**Cross-module regression.** uart_rx and uart_tx share the same interface
convention; a fix to one must not be accompanied by a change to the other.
The regression run catches mutated files that were not fully restored.

## Known gaps (honest limitations)

- No *hidden* test suite: validation uses the repo's own TBs. In production
  HWE-Smith would generate held-out directed tests per bug category and keep
  them out of the agent-facing package.
- Bugs that manifest only under backpressure (m_axis_tready low) are
  invisible to the current TBs, which never apply backpressure.
- Verilator lint is not run pre-validation; a candidate that only triggers a
  width warning but is functionally equivalent wastes one simulation slot
  (recorded as REJECT_SURVIVES).
