"""Task packaging: agent-visible bundle vs evaluator-only answer key."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from hwe_smith.classification.difficulty import classify_difficulty
from hwe_smith.packaging.leakage import check_leakage
from hwe_smith.schema import ACCEPTED, normalize_verdict
from hwe_smith.validation.contract import TB_MAP


def _problem_statement(mut: dict, rec: dict) -> str:
    tb = TB_MAP.get(mut["file"], "tb/")
    dur = (rec.get("mutated") or {}).get("duration_s", "?")
    code = (rec.get("mutated") or {}).get("exit_code", "?")
    return (
        f"# Fix the {Path(mut['file']).stem} module\n\n"
        f"The cocotb testbench `{tb}` fails on this repository.\n\n"
        f"Observed: the test suite fails with the module in its current state "
        f"(mutated run ~{dur}s, exit code {code}).\n"
        f"Category hint: {mut['category']}-related functional defect in `{mut['file']}`.\n\n"
        "Investigate the RTL, find the functional defect, and correct it while\n"
        "preserving the module interface and all passing behavior.\n"
    )


def _reference_patch(mut: dict) -> str:
    # Patch that transforms buggy -> fixed (agent must produce something equivalent)
    return (
        f"--- a/{mut['file']}\n"
        f"+++ b/{mut['file']}\n"
        f"@@\n"
        f"-{mut['modified']}\n"
        f"+{mut['original']}\n"
    )


def package_task(
    rec: dict,
    *,
    repo: Path,
    validated_root: Path,
    export_root: Path | None = None,
) -> dict:
    """Write raw task record + optional agent/evaluator export bundles.

    Returns packaging summary including leakage + difficulty.
    """
    if normalize_verdict(rec.get("status") or rec.get("verdict", "")) != ACCEPTED:
        raise ValueError("refusing to package non-accepted record")

    mut = rec["mut"]
    task_id = f"hwe_{mut['mut_id']}"
    td = validated_root / task_id
    td.mkdir(parents=True, exist_ok=True)

    src = repo / mut["file"]
    pristine = src.read_text()
    buggy = pristine.replace(mut["original"], mut["modified"], 1)
    if buggy == pristine:
        raise ValueError("mutation did not change RTL text")

    (td / (src.name + ".orig")).write_text(pristine)
    (td / src.name).write_text(buggy)
    patch = _reference_patch(mut)
    (td / "reference_patch.patch").write_text(patch)

    ps = _problem_statement(mut, rec)
    leaks = check_leakage(ps, mut["original"], mut["modified"], patch_text=patch)
    if leaks:
        # rewrite without category leaking expressions; keep generic
        ps = (
            f"# Fix the {Path(mut['file']).stem} module\n\n"
            f"The cocotb testbench fails on the current RTL. "
            f"Observe the failing simulation log, locate the functional defect, "
            f"and restore correct UART behaviour without changing the module interface.\n"
        )
        leaks = check_leakage(ps, mut["original"], mut["modified"], patch_text=patch)
    (td / "problem_statement.md").write_text(ps)

    fail_timeout = "TIMEOUT" in ((rec.get("mutated") or {}).get("log") or "")
    diff = classify_difficulty(
        category=mut.get("category", ""),
        file=mut["file"],
        original=mut["original"],
        modified=mut["modified"],
        strategy=rec.get("strategy", ""),
        fail_is_timeout=fail_timeout,
    )
    rec = dict(rec)
    rec["difficulty"] = diff.to_dict()
    rec["leakage_violations"] = leaks
    rec["task_id"] = task_id
    rec["status"] = ACCEPTED
    (td / "metadata.json").write_text(json.dumps(rec, indent=2))

    summary = {
        "task_id": task_id,
        "task_dir": str(td),
        "leakage_violations": leaks,
        "difficulty": diff.to_dict(),
    }

    if export_root is not None:
        summary["exports"] = export_bundles(td, export_root / task_id, mut, ps, patch, rec)

    return summary


def export_bundles(
    task_dir: Path,
    out_root: Path,
    mut: dict,
    problem_statement: str,
    patch: str,
    meta: dict,
) -> dict:
    """Split agent-visible vs evaluator-only views without deleting raw tasks."""
    agent = out_root / "agent"
    evalb = out_root / "evaluator"
    if out_root.exists():
        shutil.rmtree(out_root)
    agent.mkdir(parents=True)
    evalb.mkdir(parents=True)

    rtl_name = Path(mut["file"]).name
    # Agent: buggy RTL + statement + build hint only
    shutil.copy(task_dir / rtl_name, agent / rtl_name)
    (agent / "problem_statement.md").write_text(problem_statement)
    (agent / "README.md").write_text(
        "# Agent task bundle\n\n"
        "Edit the RTL to fix the failing behaviour. Do not modify tests.\n"
        "Build/test (from repo root after placing this RTL):\n\n"
        "```bash\nmake -C tb/uart_rx SIM=icarus   # or tb/uart_tx\n```\n"
    )
    (agent / "manifest.json").write_text(
        json.dumps(
            {
                "task_id": meta.get("task_id"),
                "file": mut["file"],
                "visible": ["problem_statement.md", rtl_name, "README.md"],
                "forbidden": ["*.orig", "reference_patch.patch", "metadata.json"],
            },
            indent=2,
        )
        + "\n"
    )

    # Evaluator: answer key + full provenance
    shutil.copy(task_dir / (rtl_name + ".orig"), evalb / (rtl_name + ".orig"))
    shutil.copy(task_dir / rtl_name, evalb / (rtl_name + ".buggy"))
    (evalb / "reference_patch.patch").write_text(patch)
    (evalb / "metadata.json").write_text(json.dumps(meta, indent=2))
    (evalb / "problem_statement.md").write_text(problem_statement)

    return {"agent": str(agent), "evaluator": str(evalb)}
