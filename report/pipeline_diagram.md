# HWE-Smith Pipeline Diagram

```
Open-source RTL repositories (pinned commits)
             |
             v
Repository + environment discovery
(baseline MUST pass: uart_rx 2/2, uart_tx 2/2  ✓ measured)
             |
             v
Historical PR / fix collection  [git-history mining; 5 inspected]
             |
             v
Bug candidate classification
(3 RTL_BUG_FIX | 1 REFACTOR | 1 TEST_ONLY  ✓ measured)
             |
   +---------+------------------+
   |         |                  |
   v         v                  v
Historical   Strategy A       Strategy B
fix          rule-based       LLM-written
reversion    mutation         single-edit
(3 mined,    (7 generated     (6 generated,
 not yet      ✓ measured)      ✓ measured)
 executed)
   |         |                  |
   |         +--------+---------+
   |                  |
   |                  v
   |         Independent simulation (cocotb + Icarus, 60s timeout)
   |                  |
   |                  v
   |         Fail-to-pass validation (7 checks)
   |                  |
   |         +--------+--------+
   |         |                 |
   |         v                 v
   |      REJECT (logged    ACCEPT
   |      with reason)        |
   |      6/7 rules ✓         v
   |      (measured)    Quality filter +
   |                    dedup fingerprint
   |                        |
   |                        v
   |                  Task packaging
   |                  (buggy RTL + statement + ref patch + logs)
   |                        |
   |                        v
   |                 HWE-Smith dataset
   |                  (data/validated/tasks/)
   |                        |
   |                        v
   |                  Agent evaluation
   |                  (hidden tests, clean checkout)
   |                        |
   |                        v
   |                  SFT / rejection sampling / RL
   |                  (correctness-gated)
   v
(dashed future path: reconstructed historical
 testbenches enable Strategy C execution)

MEASURED (prototype, verilog-uart @ 1b867e5):
  candidates in:  12 (rules) + 6 (llm) + 2 (history) = 20
  validated out:  10  (rules 4, llm 4, history 2)
  rejected:       10, every one with a recorded reason
  tests:          12 unit + 4 integration PASS

PROJECTION (hypothetical, 100 repos, labeled as estimate):
  100 repos -> ~60 buildable -> ~30 usable TBs
  -> ~30k candidates -> ~30% fail-to-pass -> ~9k tasks
```
