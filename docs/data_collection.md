# HWE-Smith — Data Collection

## Repository selection

**Selected: alexforencich/verilog-uart @ `1b867e53af738e4a8bc7c839ca2f1c07f40382dc`**

| Criterion | Assessment |
|---|---|
| Source | Pure Verilog-2001 (uart_rx.v 120 lines, uart_tx.v 95 lines) |
| Verification | Two self-checking cocotb testbenches with data-integrity assertions |
| Simulator | Icarus 13.0 (installed) + Verilator 5.054 fallback; cocotb 2.1.0 |
| Baseline | PASS: uart_rx 2/2, uart_tx 2/2 tests on pinned commit |
| Size | Peripheral-sized; ~35 s compile+sim per TB |
| History | 51 commits, linear, genuine RTL fixes present |
| License | MIT (COPYING) — permits benchmark redistribution |
| Complexity | Supports counters, FSM, handshake, reset, framing bug classes |

Rejected alternatives: lowRISC/Ibex and PicoRV32 (SoC-scale, heavier
environment build than the 2 h budget warrants); repos needing commercial
simulators. The upstream repo is deprecated in favor of fpganinja/taxi but
the pinned commit is fully functional — for a benchmark, pinning matters
more than upstream activity.

## Historical PR/fix mining

GitHub API was unavailable in this environment (no token; web fetch blocked
by TLS). We mined the **local git history** instead — a deliberate fallback
recorded in `data/raw/pull_requests.jsonl` `source` field.

Mined commits (5 inspected, classified by inspection of diffs):

| Commit | Title | Classification |
|---|---|---|
| 8a1df4c | Register rxd input | RTL_BUG_FIX (synchronizer) |
| db0017a | Switch to LSB first bit ordering | RTL_BUG_FIX (protocol) |
| 62eb6f5 | Initialize status registers | RTL_BUG_FIX (reset) |
| 105bf94 | Convert to synchronous resets | REFACTOR |
| 229e5aa | Add cocotb testbenches | TEST_ONLY |

Three RTL_BUG_FIX commits are Strategy C (fix reversion) candidates. The
MSB/LSB-ordering fix (db0017a) is the most instructive: it corrupts every
byte and the modern cocotb TB catches it immediately.

## Registry

`data/raw/repositories.jsonl` — one record: owner, pinned SHA, RTL/TB paths,
simulator, build/test commands, baseline status. `configs/repository.yaml`
mirrors it in YAML for the tooling.
