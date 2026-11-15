# HWE-Smith — Synthetic Hardware Bug-Fix Task Generation (Prototype)

Executable prototype of a SWE-smith-style system for RTL: synthesize bugs in
an open-source UART, keep only candidates that **fail under cocotb/Icarus on
the buggy RTL and pass again on the fixed RTL**.

**Repo under study:** `alexforencich/verilog-uart` @ `1b867e53af738e4a8bc7c839ca2f1c07f40382dc`  
**Simulator:** Icarus Verilog · **TB:** cocotb 2.1.0

## What works today

| Capability | How |
|------------|-----|
| Baseline RX/TX sims | `make SIM=icarus` in `cache/verilog-uart/tb/uart_{rx,tx}` |
| Rule mutations + validation | `python -m hwe_smith validate --strategy rules` |
| Offline LLM candidates + validation | `python -m hwe_smith validate --strategy llm` |
| Historical `db0017a` reversals | `python -m hwe_smith validate --strategy history` |
| Dedup + difficulty + agent/evaluator exports | `python -m hwe_smith package` |
| Unit tests | `pytest tests/unit -q` |

**Measured (reconciled):** 20 candidates across strategies → 10 ACCEPT in reports → **10 unique** tasks after dedup (`hwe_INT_001` duplicates `hwe_RULE_001`). Details: `results/final_implementation_report.json`.

## What is not claimed

- Live LLM API generation (offline JSONL only unless `HWE_SMITH_LLM_API_*` is set).
- Full coding-agent evaluation harness (design doc only).
- Execution of all mined history commits (only `db0017a` RX/TX).
- Empirical calibration of difficulty tiers.

## Setup

```bash
brew install icarus-verilog verilator
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .

git clone https://github.com/alexforencich/verilog-uart cache/verilog-uart
git -C cache/verilog-uart checkout 1b867e53af738e4a8bc7c839ca2f1c07f40382dc
```

## Quickstart

```bash
# pristine baseline (must PASS)
(cd cache/verilog-uart/tb/uart_rx && PATH="$PWD/../../.venv/bin:$PATH" make SIM=icarus)
(cd cache/verilog-uart/tb/uart_tx && PATH="$PWD/../../.venv/bin:$PATH" make SIM=icarus)

# discover pin + package existing validated set
.venv/bin/python -m hwe_smith discover
.venv/bin/python -m hwe_smith package
.venv/bin/python -m hwe_smith report

# regenerate/validate a strategy (slow; real sims)
.venv/bin/python -m hwe_smith validate --strategy rules
.venv/bin/python -m hwe_smith validate --strategy llm
.venv/bin/python -m hwe_smith validate --strategy history

# tests
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m pytest tests/integration -q   # ~5 minutes
```

## Layout

```
configs/            repository + generation config (single source of truth)
src/hwe_smith/      schema, generators, simulation, validation contract,
                    packaging (leakage + agent/evaluator split), classification
scripts/            rules / llm / history pipelines, package_dataset, demo
data/validated/     raw accepted task records
data/exports/       agent/ and evaluator/ bundles per unique task
data/generated/     offline LLM JSONL candidates
docs/               audit, completion report, methodology
report/             Parts 1–2 take-home write-up
results/            validation + final implementation reports
tests/              unit + integration
```

## Validation contract (short)

Accepted only when: pristine PASS → mutation applies → behavioural FAIL
(compile-only errors rejected) → restore PASS → other-module regression PASS →
failure reproduces → intended file only. See `docs/validation_methodology.md`.

## Documentation map

| Doc | Purpose |
|-----|---------|
| `docs/implementation_audit.md` | Pre-change inventory with statuses |
| `docs/implementation_completion_report.md` | What was fixed / still open |
| `results/final_implementation_report.json` | Reconciled counts |
| `report/submission.md` | Chipforge Parts 1–2 write-up |
