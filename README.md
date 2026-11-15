# HWE-Smith

**SWE-smith for hardware.** Automatically generate verifiable RTL bug-fix tasks — only keep bugs that fail in simulation and pass again after the fix.

> Study target: [`alexforencich/verilog-uart`](https://github.com/alexforencich/verilog-uart) · Icarus + cocotb · Chipforge AI/ML take-home

---

## Results

| Metric | Value |
|--------|------:|
| Candidates generated | **20** |
| Accepted (fail → pass) | **10** |
| Unique after dedup | **10** |
| Overall yield | **50%** |
| Unit tests | **16 / 16** |
| Baseline RX / TX | **PASS / PASS** |

### By strategy

| Strategy | In | Out | Yield |
|----------|---:|----:|------:|
| Rule mutations | 12 | 4 | 33% |
| LLM bugs (offline) | 6 | 4 | 67% |
| History reversal | 2 | 2 | 100% |

Most rejections: **`REJECT_SURVIVES`** — the testbench never observed the bug.

Difficulty on unique tasks: **7 medium · 3 hard**

---

## Why it matters

A task is accepted **only** when all of this holds:

1. Clean RTL **passes**
2. Bug makes the sim **fail** (compile-only ≠ bug)
3. Restoring the fix makes it **pass** again
4. The other UART module still **passes**
5. The failure **reproduces**
6. Only the intended RTL file changed

Agent sees buggy RTL + problem statement.  
Evaluator keeps the gold fix, patch, and full logs separately (`data/exports/`).

---

## Highlights

- **3 generators** — rules, LLM candidates, real historical fix reversals  
- **Real sim oracle** — cocotb under Icarus, not model judgment  
- **Leak-checked** problem statements  
- **Dedup + difficulty** packaging  
- Design write-up: [`report/submission.md`](report/submission.md)

---

## Quick start

```bash
brew install icarus-verilog
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -e .

git clone https://github.com/alexforencich/verilog-uart cache/verilog-uart
git -C cache/verilog-uart checkout 1b867e53af738e4a8bc7c839ca2f1c07f40382dc

.venv/bin/python -m hwe_smith discover
.venv/bin/python -m hwe_smith package
.venv/bin/python -m hwe_smith report
.venv/bin/python -m pytest tests/unit -q
```

Validate a strategy (slow — real sims):

```bash
.venv/bin/python -m hwe_smith validate --strategy rules    # or llm | history
```

---

## Layout

```
src/hwe_smith/     pipeline code
scripts/           rules / llm / history runners
data/validated/    accepted tasks
data/exports/      agent/ + evaluator/ bundles
report/            Parts 1–2 write-up
results/           measured reports
docs/              methodology + audit
```

---

## Docs

| | |
|--|--|
| [`report/submission.md`](report/submission.md) | Design assessment |
| [`results/final_implementation_report.json`](results/final_implementation_report.json) | Full numbers |
| [`docs/validation_methodology.md`](docs/validation_methodology.md) | 7-check contract |
| [`docs/implementation_completion_report.md`](docs/implementation_completion_report.md) | What works / what’s next |
