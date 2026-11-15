# HWE-Smith — Evaluation Design (Part 2, assuming 2,000 validated tasks)

## 1. Agent loop

Each task exposes: buggy repo checkout, problem statement, build/test commands.
The agent runs in a sandbox with the repo, a simulator, and shell access; it
edits RTL, runs the visible test, and submits a patch. Final grading uses a
**hidden test set** (directed tests per bug category, not shown to the agent)
on a **clean checkout** of the buggy repo with only the agent's RTL patch
applied.

## 2. Metrics

| Metric | Definition |
|---|---|
| Resolved rate | hidden tests pass after repair / total tasks (baseline) |
| Compile success | agent patch compiles / total (floor capability) |
| Localization accuracy | agent's patch touches the true faulty module/file |
| Patch precision | changed lines that are in the faulty region / total changed lines (HWE-Bench's file-precision, finer) |
| Regression rate | tasks where hidden tests passed pre-repair but fail post-repair |
| Iterations | simulator invocations per task (proxy for agent "debug cycles") |
| Time & cost per task | wall clock; $ per resolved task |
| Pass@1 / Pass@k | per-task and per-category |
| Failure categories | distribution over mislocalization / wrong-protocol / syntax / test-misread / trial-and-error |

**Partial vs. real fixes.** A fix counts only if hidden tests pass AND
regression rate is zero. We track "resolved-with-regressions" separately; an
agent that fixes the bug by breaking the stop-bit check is not resolved.

## 3. Trust: does synthetic performance track real bug repair?

Design: run the same agent on HWE-Smith (synthetic) and HWE-Bench (real,
417 tasks) and compare resolved rates **stratified by bug category and
difficulty**. Claims require the experiment; a priori we hypothesize
correlation per category (e.g. off-by-one counters should transfer) but not
necessarily for environment-specific skills (repo navigation in huge SoCs).

If scores do NOT correlate, the likely causes are (a) synthetic bugs are too
local (single-edit, no cross-module interaction), (b) TBs too weak (bugs
findable by grep), or (c) distribution shift in repo style. The response is
to add Strategy C (historical fix reversion) tasks and multi-module bugs to
the synthetic mix, not to tune the agent.

## 4. Reward hacking prevention

- **Hidden tests are immutable and outside the agent workspace.**
- Grading runs on a **clean checkout + agent RTL patch only**; edits to
  testbenches, build scripts, or sim config are discarded (patch allowlist:
  `rtl/**` only).
- File hashes of TB/build files verified pre/post-run; any mismatch = task
  failed with category `environment_tamper`.
- Post-hoc detectors: patch touches test-facing names (`tb/`, `results.xml`),
  special-cases stimulus constants, or deletes assertions.
- A fraction of tasks get a **canary variant**: same bug, different stimulus;
  a solution passing only the visible test fails the canary.

## 5. Splits and contamination

Split by **root cause**, not by task ID: all tasks derived from the same
mutation operator instance, same module, or same underlying historical fix
stay in one split. Recommended: 70% train / 10% val / 20% eval, plus
HWE-Bench as an external real-world eval set. Repository-level splitting
(second repo held out entirely) tests generalization to unseen codebases.

## 6. Trajectory analysis

Log per task: files opened, grep ops, simulator invocations, compile errors,
patch revisions, test outcomes, token usage, cost, time. Classify failures
with a rubric: (1) wrong file, (2) right file wrong line, (3) wrong protocol
model, (4) syntax/compile fail, (5) test misinterpretation, (6) regression
introduced, (7) >10 simulator runs without hypothesis revision (trial-and-error
signature). Aggregate rubric distributions by agent and category.

## 7. Training use

- **SFT**: verified agent trajectories that resolve tasks (hidden tests pass,
  no regressions) become demonstrations. Correctness gate applies before
  trajectory is admitted.
- **Rejection sampling**: sample k attempts per training task; keep only
  resolved runs; dedupe near-identical patches.
- **RL**: reward = resolved(0/1) − λ·regressions − μ·iterations, with the
  hidden-test gate making reward hacking unprofitable by construction.
- **Tool-use training**: simulator command sequences are first-class tokens;
  train the agent when to run simulation vs. read code.

Correctness (hidden tests) is the dominant signal; LLM-judged "plausibility"
is never used as reward.
