"""Re-package existing validated tasks: dedup, difficulty, agent/evaluator exports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hwe_smith.classification.dedup import dedupe_tasks  # noqa: E402
from hwe_smith.classification.difficulty import classify_difficulty  # noqa: E402
from hwe_smith.packaging.leakage import check_leakage  # noqa: E402
from hwe_smith.packaging.package import export_bundles  # noqa: E402
from hwe_smith.paths import repo_path  # noqa: E402


def main() -> None:
    tasks_root = ROOT / "data" / "validated" / "tasks"
    export_root = ROOT / "data" / "exports"
    export_root.mkdir(parents=True, exist_ok=True)

    task_dirs = sorted(p for p in tasks_root.glob("hwe_*") if p.is_dir())
    decisions = dedupe_tasks(task_dirs)

    dataset = {
        "tasks": [],
        "dedup": [d.to_dict() for d in decisions],
        "unique_kept": [],
        "duplicates": [],
    }

    for d in decisions:
        td = tasks_root / d.task_id
        meta_path = td / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        mut = meta.get("mut") or {}
        ps = (td / "problem_statement.md").read_text() if (td / "problem_statement.md").exists() else ""
        patch = (
            (td / "reference_patch.patch").read_text()
            if (td / "reference_patch.patch").exists()
            else ""
        )
        leaks = check_leakage(
            ps, mut.get("original", ""), mut.get("modified", ""), patch_text=patch
        )
        fail_timeout = "TIMEOUT" in ((meta.get("mutated") or {}).get("log") or "")
        diff = classify_difficulty(
            category=mut.get("category", ""),
            file=mut.get("file", ""),
            original=mut.get("original", ""),
            modified=mut.get("modified", ""),
            strategy=meta.get("strategy", ""),
            fail_is_timeout=fail_timeout,
        )
        meta["difficulty"] = diff.to_dict()
        meta["fingerprint"] = d.fingerprint
        meta["dedup_keep"] = d.keep
        meta["dedup_reason"] = d.reason
        meta["leakage_violations"] = leaks
        meta_path.write_text(json.dumps(meta, indent=2))

        entry = {
            "task_id": d.task_id,
            "strategy": meta.get("strategy"),
            "category": mut.get("category"),
            "file": mut.get("file"),
            "fingerprint": d.fingerprint,
            "keep": d.keep,
            "duplicate_of": d.duplicate_of,
            "difficulty": diff.to_dict(),
            "leakage_violations": leaks,
        }
        dataset["tasks"].append(entry)

        if d.keep:
            dataset["unique_kept"].append(d.task_id)
            export_bundles(td, export_root / d.task_id, mut, ps, patch, meta)
        else:
            dataset["duplicates"].append(
                {"task_id": d.task_id, "duplicate_of": d.duplicate_of, "reason": d.reason}
            )

    # difficulty distribution over unique kept
    dist = {"easy": 0, "medium": 0, "hard": 0}
    for t in dataset["tasks"]:
        if t["keep"]:
            dist[t["difficulty"]["tier"]] = dist.get(t["difficulty"]["tier"], 0) + 1
    dataset["difficulty_distribution"] = dist
    dataset["repo_commit"] = {
        "path": str(repo_path()),
    }

    out = ROOT / "results" / "dataset_package_report.json"
    out.write_text(json.dumps(dataset, indent=2))
    print(
        json.dumps(
            {
                "task_dirs": len(task_dirs),
                "unique_kept": len(dataset["unique_kept"]),
                "duplicates": len(dataset["duplicates"]),
                "difficulty_distribution": dist,
                "exports": str(export_root),
                "report": str(out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
