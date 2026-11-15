# HWE-Smith: Synthetic Hardware Bug-Fix Task Generation — Assessment Submission

## 1. Executive summary

I designed and **implemented** a small-scale HWE-Smith: a system that takes an
open-source RTL repository, synthesizes realistic hardware bugs by three
independent strategies, and keeps only candidates proven — by real simulation,
not model judgment — to be fail-to-pass repair tasks. The prototype runs on
`alexforencich/verilog-uart` (pinned commit `1b867e5`, MIT) with cocotb
testbenches under Icarus Verilog. From **20 generated candidates** across the
three strategies, **10 passed** the 7-check validation contract (baseline,
compile, functional fail, restoration, regression, reproducibility,
integrity) — yield 50% overall (rules 4/12, LLM 4/6, history 2/2); every
rejection is logged with its reason. The pipeline, CLI, unit tests (12
passing), integration tests (4 passing, real simulations), and full
validation evidence are included and executable.

## 2. Architecture and pipeline

The design transplants SWE-smith's core loop — environment, synthetic
perturbation, executable validation, packaging with provenance — into RTL,
where three things change fundamentally: (1) the oracle is a simulator, not a
test runner, so "bug" means "observable waveform behavior change", (2) bugs
can *hang* a testbench rather than fail it, which must be classified as a
legitimate failure mode, and (3) interfaces are contracts; a port or
parameter edit is sabotage, not a bug.

```
RTL repo (pinned) → isolated workspace per candidate (cocotb+Icarus)
→ history mining (classified) ─┬→ A: rule mutations (7 operators)
                               ├→ B: LLM single-edit bugs (schema-checked, unverified)
                               └→ C: historical fix reversion (data collected, 3 fixes)
→ simulation → 7-check validation → ACCEPT (package) / REJECT (log reason)
```

Measured funnel (this prototype): **20 candidates → 10 validated** — rules
4/12, LLM 4/6, historical reversion 2/2 (final records in
`results/generation_report.json`, `results/llm_validation_report.json`,
`results/history_validation_report.json`). Hypothetical scale-up survival,
labeled as projection: 100 repos → ~60 buildable → 30 with usable TBs → ~500
candidates/repo-year of operator mutations → ~30% fail-to-pass → ~4-6k
tasks.

## 3. Repository selection and data collection

Selection favored a **peripheral over a SoC**: verilog-uart is 215 lines of
Verilog-2001 with two self-checking cocotb testbenches, runs in ~35 s,
and has a linear 51-commit history containing genuine RTL fixes — everything
a validation loop needs. Ibex/PicoRV32 were rejected as too heavy for a
2-hour budget, not because they are unsuitable at scale.

GitHub API was unavailable (no token, web fetch TLS-blocked in this
environment), so PR mining used **local git history** — a recorded limitation.
Five commits were inspected and classified: 3 `RTL_BUG_FIX` (input
synchronizer registration, LSB-first bit ordering, status register reset
init), 1 `REFACTOR` (sync resets), 1 `TEST_ONLY`. All are stored with diffs
and evidence in `data/raw/pull_requests.jsonl`; the three fixes are Strategy C
candidates.

## 4. Environment construction

Each candidate gets a fresh workspace copy (repo minus `.git` and the FPGA
`example/` tree, whose symlink cycles are excluded deliberately). The build
recipe is the repo's own `make SIM=icarus` under cocotb 2.1.0, wrapped in a
runner that captures logs, parses `results.xml` for pass/fail counts, and
enforces a 60 s timeout — because corrupted UART streams *hang* rather than
fail, and a hang is exactly how a hardware engineer experiences this bug
class. The pristine repo passed baseline (4/4 tests) before any generation.

## 5. Bug generation approaches and trade-offs

**A — Rule-based mutation** (`src/hwe_smith/generators/rules.py`): 7 operators
(boundary, off-by-one, shift-width, reset polarity, handshake, framing,
status-flag) applied as unique-anchor text edits. Produces bugs in exactly
the classes HWE-Bench mines from reality: off-by-one counters, FSM threshold
errors, handshake glitches. Cheap, deterministic, but shallow — one
expression at a time.

**B — LLM-written bugs** (`generators/llm.py`): a model received the RTL plus
module semantics and returned a single-edit JSON patch. Six candidates were
generated (off-by-one FSM count, premature handshake clear, inverted reset
polarity, short bit-count, stop-bit injection, ready-forcing). Model output
was treated strictly as unverified input: schema-checked, uniqueness-checked,
interface-preservation-checked, then sent to the same simulation gauntlet as
Strategy A.

**C — Historical fix reversion** (`scripts/run_history_pipeline.py`): the
mined `RTL_BUG_FIX` commit `db0017a` (LSB-first bit ordering) was reverted
onto pinned HEAD using the historically exact pre-fix expressions (verified
via `git show 62eb6f5:rtl/uart_rx.v`). Both the RX and TX reverts validated
fail-to-pass — these are the two highest-value tasks in the dataset: real
human bugs, real fixes, full provenance. This closes the loop with HWE-Bench's
methodology at prototype scale.

## 6. Validation, task quality, and what rejections teach

The validation contract (docs/validation_methodology.md) exists to make
**false accept impossible**: restore verifies the file is exactly
pristine-plus-mutation before reverting, and the regression run catches
incomplete restores. Two engineering bugs in my own harness were caught and
fixed by this contract during the build: (1) same-second file edits fooled
make's mtime check into running a stale binary against modified RTL — fixed
by wiping `sim_build` before every run; (2) timeout kill logic killed the
pipeline's own process group — fixed with pgrep-based child-group lookup.

The most informative finding: **the upstream testbench itself had a blind
spot**. It checked byte counts but never compared received data to sent
data, so a real bit-order-corruption bug (visible in logs as `\x00\x00\x00p...`)
passed all tests. After adding the data-integrity assert, both historical
bit-order reversions and the RULE_007 mutation flipped from surviving to
failing — 3 additional validated tasks. Lesson, matching SWE-smith's
experience: test sensitivity, not bug supply, is the binding constraint.

Rejections with documented reasons (data/rejected/rejected_candidates.jsonl):

- `RULE_002` (first pass): mutation duplicated an existing expression,
  making restoration ambiguous → rejected by the integrity check, by design.
- `RULE_003`, `RULE_004`, `RULE_005`, `RULE_006`, `RULE_008`, `RULE_009`,
  `RULE_011`, `LLM_002`, `LLM_005`: functionally real but **invisible to the
testbench** (timing offsets absorbed by 8× oversampling; reset glitches
re-synced; status flags unchecked). REJECT_SURVIVES — the TB is not sensitive
enough, which is why production HWE-Smith needs coverage-directed hidden
tests.
- `LLM_006`: initially survived (ready-forcing only observable under
backpressure patterns); accepted after TB strengthening.

## 7. Problem statement generation

Statements are written from the failing run's observable evidence (which TB,
how many tests, what module/category) and checked for leakage: the exact
original/modified expressions never appear (enforced in
`tests/integration/test_validation_flow.py::test_4`). The reference patch
lives in task metadata, agent-facing package contains only buggy RTL + statement.

## 8. Difficulty and deduplication

Difficulty is assigned by interaction scope, not diff size: single-expression
arithmetic → Easy; counter/FSM interaction → Medium; multi-cycle protocol and
parameter-dependent → Hard. Deduplication fingerprints (file, original,
modified, category); RULE_002's anchor-collision shows why fingerprinting
must include the mutated form's global uniqueness.

## 9–14. Evaluation design (Part 2)

Full design in `docs/evaluation_design.md`. Core commitments: resolved rate
on **hidden tests** as the headline metric; patch precision and regression
rate to distinguish real fixes from partial ones; reward-hacking prevention
by clean-checkout grading with an RTL-only patch allowlist plus canary
variants; splits at root-cause level (never split sibling mutations of the
same module across train/eval); trajectory rubric classifying failures into
7 modes (mislocalization … trial-and-error); SFT/rejection-sampling/RL all
gated on hidden-test correctness, never on LLM-judged plausibility. Trust in
synthetic scores requires a stratified correlation experiment against
HWE-Bench before any claim — none is claimed here.

## 15. Prototype results and limitations

| Stage | Count |
|---|---|
| Rule mutations generated | 12 |
| Rule mutations validated | 4 |
| LLM candidates generated | 6 |
| LLM candidates validated | 4 |
| Historical fixes reverted & validated | 2 (of 3 mined) |
| **Total validated tasks** | **10** |
| Rejections with documented reasons | 10 |
| Unit tests | 12/12 pass |
| Integration tests (real simulation) | 4/4 pass |

**Limitations, stated plainly:** (1) one repo, one module pair — breadth
unproven; (2) the TB still misses backpressure-dependent bugs (LLM_002
premature-handshake survives because the sink never deasserts tready) —
two rejections remain for this reason; (3) hidden-test generation not yet
built; (4) GitHub API mining replaced by git-history mining; (5) TB
strengthening (adding the data-integrity assert) was done by me, the
task author — in production this must be automated and audited to avoid
biasing tasks toward fixes the author anticipated. **What I'd do differently
at scale:** invest in testbench generation before mutation volume — this
prototype's single highest-leverage change was one assert line, worth 3
validated tasks.

## References

- HWE-Bench (pku-liang/HWE-Bench): fail-to-pass criterion, task schema, harness layout — studied from local clone.
- SWE-smith (SWE-bench/SWE-smith): environment/synthetic-fault/validation loop, operator-based fault injection — studied from local clone.
- CVDP (NVlabs/cvdp_benchmark, arXiv 2506.14074): hardware problem taxonomy, authored-task structure — studied from local clone.
- verilog-uart (alexforencich) @ 1b867e5: study subject, MIT license.
