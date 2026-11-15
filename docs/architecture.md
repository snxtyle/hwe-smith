# HWE-Smith — Architecture

## Pipeline

```
Open-source RTL repos (pinned commits)
        |
        v
Environment build: repo clone -> per-candidate isolated workspace
        |           (cocotb + Icarus; baseline must PASS before use)
        v
Historical PR/fix mining (git history, classified)
        |
        +---------------------+
        |                     |
        v                     v
Strategy A: rule-based   Strategy B: LLM-written bugs
mutation engine          (single-edit, schema-checked,
 (~7 operators)           model output UNVERIFIED)
        |                     |
        +----------+----------+
                   |
                   v
        Independent simulation (cocotb/Icarus, 60s timeout)
                   |
                   v
        7-check validation contract
        baseline / compile / fail-to-pass / restore /
        regression / reproducibility / integrity
           |                |
           v                v
        REJECT           ACCEPT
        (logged with      |
         reason)          v
                   Task packaging: buggy RTL + problem
                   statement + reference patch + logs
                          |
                          v
                   data/validated/tasks/hwe_XXX/
```

## What we borrowed, verified from source

**SWE-smith** (cloned, `cache/SWE-smith`): the core loop — build an execution
environment per repo, synthesize perturbations that break existing tests, keep
only verified fail-to-pass instances, package with provenance. Also its lesson
that mutation *operators* are more scalable than LLM freeform edits.

**HWE-Bench** (cloned, `cache/HWE-Bench`): the fail-to-pass acceptance
criterion (test fails on buggy, passes on fixed), per-task Docker-style
environment reproducibility, and structured task metadata.

**CVDP** (cloned, `cache/cvdp_benchmark`): category taxonomy for hardware
problems and the observation that component-level design tasks differ from
repository-level bug repair — CVDP is authored problems; HWE-Smith mines or
synthesizes them.

## What must differ for hardware

1. **The oracle is a simulator, not pytest.** Compile+simulate is the only
   truth; LLM claims are unverified inputs.
2. **Bugs can hang, not just fail.** A protocol bug deadlocks the testbench.
   Timeout is a failure mode that must be classified, not an error.
3. **Interfaces are contracts.** Port/parameter changes are sabotage, not
   bugs; the validator must preserve interface hashes.
4. **Testbench quality is the bottleneck.** Existing TBs miss backpressure,
   corner cases; coverage-directed hidden tests matter more than in software.
5. **Reproducibility is easier** (no network, no flaky services) but compile
   time dominates runtime; workspace caching matters at scale.
