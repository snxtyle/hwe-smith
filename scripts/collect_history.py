"""Mine real historical bug-fix commits from the pinned repo's git history."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "cache" / "verilog-uart"
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()


repo_rec = {
    "owner": "alexforencich",
    "name": "verilog-uart",
    "git_url": "https://github.com/alexforencich/verilog-uart",
    "commit": "1b867e53af738e4a8bc7c839ca2f1c07f40382dc",
    "language": "verilog-2001",
    "license": "MIT",
    "rtl_paths": ["rtl/uart_rx.v", "rtl/uart_tx.v", "rtl/uart.v"],
    "testbench_paths": ["tb/uart_rx/test_uart_rx.py", "tb/uart_tx/test_uart_tx.py"],
    "simulator": "icarus",
    "baseline_status": "PASS",
}
(RAW / "repositories.jsonl").write_text(json.dumps(repo_rec) + "\n")

fixes = {
    "8a1df4c215731ea6704c18e6e4009e7603dcf748": {
        "title": "Register rxd input",
        "classification": "RTL_BUG_FIX",
        "category": "synchronizer",
        "fix_summary": "Double-flop register the asynchronous rxd input before use",
        "has_executable_test": False,
        "executed_as_reversal": False,
    },
    "db0017a22c57731d69a4a2844bc1e4f3f36abd10": {
        "title": "Switch to LSB first bit ordering",
        "classification": "RTL_BUG_FIX",
        "category": "protocol",
        "fix_summary": "UART sends LSB first; original code shifted MSB-first",
        "has_executable_test": True,
        "executed_as_reversal": True,
    },
    "62eb6f5d45b62be3029308da58c64bafbdb3aac6": {
        "title": "Initialize status registers",
        "classification": "RTL_BUG_FIX",
        "category": "reset",
        "fix_summary": "busy/overrun/frame_error regs had no reset/init value",
        "has_executable_test": True,
        "executed_as_reversal": False,
    },
    "105bf94": {
        "title": "Convert to synchronous resets",
        "classification": "REFACTOR",
        "category": "reset",
        "fix_summary": "Async resets converted to sync; classified refactor not bug",
        "has_executable_test": True,
        "executed_as_reversal": False,
    },
    "229e5aa": {
        "title": "Add cocotb testbenches",
        "classification": "TEST_ONLY",
        "category": "verification",
        "fix_summary": "Initial cocotb testbench addition",
        "has_executable_test": True,
        "executed_as_reversal": False,
    },
}

prs = []
for sha, meta in fixes.items():
    changed = [l for l in git("show", "--name-only", "--format=", sha).splitlines() if l]
    prs.append(
        {
            "commit": sha,
            "title": meta["title"],
            "classification": meta["classification"],
            "category": meta["category"],
            "changed_files": changed,
            "fix_summary": meta["fix_summary"],
            "has_executable_test": meta["has_executable_test"],
            "executed_as_reversal": meta["executed_as_reversal"],
            "source": "git-history (local clone; no GitHub API)",
        }
    )
(RAW / "pull_requests.jsonl").write_text("\n".join(json.dumps(p) for p in prs) + "\n")
executed = sum(1 for p in prs if p["executed_as_reversal"])
print(f"wrote {len(prs)} PR records (executed_as_reversal={executed}), 1 repo record")
