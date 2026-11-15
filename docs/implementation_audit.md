# HWE-Smith Implementation Audit (Phase 0)

**Audit date:** 2026-11-15  
**Git:** branch `main`, commit `15bed9f` (Initial commit only). **All project files are currently untracked** (`git status` shows `??` for `src/`, `scripts/`, `data/`, etc.).  
**Auditor method:** Inspected source, configs, data, results; ran pristine UART RX/TX sims; did **not** trust prior summaries without evidence.

---

## Environment (Phase 1 evidence)

| Check | Result |
|-------|--------|
| Python | 3.14.5 (`.venv`) |
| cocotb | 2.1.0 |
| pytest | 9.2.0 |
| Icarus Verilog | 13.0 (`/opt/homebrew/bin/iverilog`) |
| Verilator | 5.054 (available; not used by UART flow) |
| UART clone | `cache/verilog-uart` @ `1b867e53af738e4a8bc7c839ca2f1c07f40382dc` (matches pin) |
| License | MIT (`COPYING`) |
| Symlinks | Present under `example/*/fpga/lib/uart` → runner ignores `example/` |
| Baseline RX | **PASS** TESTS=2 PASS=2 (executed 2026-11-15) |
| Baseline TX | **PASS** TESTS=2 PASS=2 (executed 2026-11-15) |
| Data-integrity assert | Present in both TBs (`assert rx_data == test_data`) with HWE-Smith comment |

---

## Component inventory

### CLI — `src/hwe_smith/cli.py`

| Status | **PARTIAL** |
|--------|-------------|
| Evidence | `discover`, `collect-prs`, `generate --strategy rules`, `report` work structurally. `generate --strategy llm` only counts JSONL lines. **`validate --strategy llm` is ignored** — `cmd_validate` always runs rule mutations. Imports `from run_rules_pipeline import ...` requiring `scripts/` on `sys.path` (fragile). No history strategy in CLI. |

### Simulation runner — `src/hwe_smith/simulation/runner.py`

| Status | **COMPLETE** (with notes) |
|--------|---------------------------|
| Evidence | Fresh workspace via `copytree` ignoring `.git`/`example`; deletes `sim_build` before each run (mtime race fix present); `start_new_session=True` + pgid kill on timeout; parses `results.xml`; distinguishes PASS/FAIL/ERROR. Integration tests exercise it. |
| Notes | Hardcoded PATH insert to `~/Desktop/hwe-smith/.venv/bin`. Timeout default 60s vs `generation.yaml` 300s (**config drift**). Timeout→FAIL mixes possible infra hangs with RTL deadlocks (documented caveat). |

### Strategy A rules — `src/hwe_smith/generators/rules.py` + `scripts/run_rules_pipeline.py`

| Status | **COMPLETE** (operators partial vs config) |
|--------|--------------------------------------------|
| Evidence | Unique-substring mutations; `OPERATORS` has boundary/arithmetic/shift/reset/handshake/stop/overrun/data_corrupt/tx_framing. Pipeline validates + packages. `results/generation_report.json`: **12 candidates, 4 ACCEPT, 8 REJECT_SURVIVES**. Tasks on disk: `hwe_RULE_001/002/007/010`. |
| Gaps | `generation.yaml` lists `boundary_gt_ge`, `constant_bit_flip` which are **not** in `OPERATORS`. Validation lives in script, not package. Verdict string is `ACCEPT` not `ACCEPTED`. |

### Strategy B LLM — `src/hwe_smith/generators/llm.py` + `scripts/run_llm_pipeline.py`

| Status | **PARTIAL** |
|--------|-------------|
| Evidence | Schema, prompt template, parse/safety, `load_candidates`. `data/generated/llm_candidates.jsonl` has **6** lines. `results/llm_validation_report.json`: **4 ACCEPT, 2 REJECT_SURVIVES**. Tasks: `hwe_LLM_001/003/004/006`. |
| Gaps | **No live LLM API caller** (offline JSONL only). Hardcoded absolute `ROOT = Path("/Users/suraj.nagre/Desktop/hwe-smith")`. CLI not wired to this script. Referenced `scripts/generate_llm_candidates.md` **missing**. |

### Strategy C history — `scripts/collect_history.py` + `scripts/run_history_pipeline.py`

| Status | **PARTIAL** |
|--------|-------------|
| Evidence | `data/raw/pull_requests.jsonl` has **5** mined commits (3 RTL_BUG_FIX, 1 REFACTOR, 1 TEST_ONLY). History pipeline hard-codes **2** mutations for `db0017a` RX/TX. Report: **2/2 ACCEPT**. Tasks: `hwe_HIST_db0017a_rx/tx`. |
| Gaps | Mined ≠ executed. `62eb6f5` / `8a1df4c` not validated as reversals. Absolute ROOT path. Not in `run_demo.sh`. |

### Validation contract

| Status | **PARTIAL** (logic present, packaging incomplete) |
|--------|---------------------------------------------------|
| Evidence | `scripts/run_rules_pipeline.validate()` implements checks 1–6 (baseline, apply, fail, restore, regression, repro). Check 7 integrity via `restore()` comparing pristine+mutation. Reused by LLM/history scripts. |
| Gaps | Not a shared package module. Compile ERROR labeled `REJECT_COMPILED_CLEAN` (misleading). No `INFRASTRUCTURE_ERROR` status. Rejection log (`data/rejected/rejected_candidates.jsonl`) **out of date** vs current ACCEPT tasks (e.g. RULE_002). No structured status enum shared across strategies. |

### Packaging / leakage

| Status | **PARTIAL** |
|--------|-------------|
| Evidence | `package()` writes buggy RTL, `.orig`, patch, statement, metadata into one folder. `leakage.py` + unit tests exist (`tests/unit/test_leakage.py`). Integration asserts statement lacks exact original expr. |
| Gaps | **No agent-visible vs evaluator-only split** — answer key co-located with agent files. `package()` does **not** call `check_leakage`. Patch format is synthetic one-hunk. |

### Dedup / difficulty

| Status | **DESIGN ONLY** |
|--------|-----------------|
| Evidence | Described in `report/submission.md` / diagram. **No code** under `src/hwe_smith/classification/` (empty `__init__.py`). |

### Discovery / collection / classification / validation packages

| Status | **STUB** |
|--------|----------|
| Evidence | `src/hwe_smith/{discovery,collection,classification,validation}/__init__.py` are **0-byte**. Behavior lives in CLI + scripts. |

### Tests

| Status | **PARTIAL / previously reported COMPLETE** |
|--------|--------------------------------------------|
| Evidence | Unit: mutation uniqueness, LLM parse/safety, leakage, results.xml. Integration: pristine PASS, mutate FAIL, restore PASS, full validate ACCEPT. `results/test_summary.json` claims 16/16 dated 2026-11-13 — **must be re-run** before citing. |
| Gaps | `test_leakage.py` inserts `tests/src` on path (likely relies on other path hacks). No tests for dedup/difficulty/CLI strategy routing/agent-eval split. |

### Documentation vs code

| File | Status |
|------|--------|
| `README.md` | Mostly accurate quickstart; overstates “CLI validate runs rules+llm”. |
| `docs/*.md` | Architecture/validation/eval design present; eval design = DESIGN ONLY for harness. |
| `report/submission.md` | Parts 1–2 + Part 3 numbers; must reconcile task IDs (11 dirs including INT_001). |
| Early FIFO/Verilator prototype | **Not in this tree** — separate historical experiment; do not merge counts. |

---

## Validated task reconciliation (disk evidence)

| ID | Strategy | Notes |
|----|----------|-------|
| `hwe_RULE_001` | rules | ACCEPT in generation_report |
| `hwe_RULE_002` | rules | ACCEPT in generation_report; **contradicts** older rejected_candidates.jsonl entry |
| `hwe_RULE_007` | rules | ACCEPT |
| `hwe_RULE_010` | rules | ACCEPT |
| `hwe_LLM_001` | llm | ACCEPT |
| `hwe_LLM_003` | llm | ACCEPT |
| `hwe_LLM_004` | llm | ACCEPT |
| `hwe_LLM_006` | llm | ACCEPT |
| `hwe_HIST_db0017a_rx` | history | ACCEPT |
| `hwe_HIST_db0017a_tx` | history | ACCEPT |
| `hwe_INT_001` | integration test | Same mutation family as RULE_001 (boundary); **duplicate of RULE_001 bug** for dataset uniqueness |

**Reported 20 in / 10 out:** Supported by reports (12+6+2 = 20 candidates; 4+4+2 = 10 ACCEPT) **excluding** INT_001.  
**Unique behavioural tasks if INT_001 deduped against RULE_001:** **9 unique** + 1 duplicate packaging artifact.

---

## Highest-priority gaps (for subsequent phases)

1. Extract shared validation + candidate schema into package; fix CLI strategy routing.  
2. Agent/evaluator package separation + leakage in packaging path.  
3. Dedup + difficulty classification with recorded reasons.  
4. Align configs; relative paths; demo includes history or explains skip.  
5. Honest status vocabulary (`REJECT_COMPILE_ERROR`, `INFRASTRUCTURE_ERROR`).  
6. Re-run pytest; produce `results/final_implementation_report.json`.  
7. Do **not** invent candidates to inflate counts; do **not** merge FIFO prototype numbers.

---

## Status legend used above

COMPLETE / PARTIAL / DESIGN ONLY / STUB / BROKEN / NOT IMPLEMENTED — as defined in the user brief.
