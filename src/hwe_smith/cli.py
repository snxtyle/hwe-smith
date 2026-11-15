"""HWE-Smith command line interface."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from hwe_smith.paths import ROOT, load_repository_config, repo_path


def cmd_discover(_args) -> None:
    cfg = load_repository_config()
    repo = repo_path()
    ok = repo.exists()
    head = ""
    if ok:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
        ).stdout.strip()
    print(
        json.dumps(
            {
                "repository": cfg["repository"],
                "pinned_commit": cfg["commit"],
                "cloned_head": head,
                "clone_matches_pin": head == cfg["commit"],
                "baseline_status": cfg.get("baseline_status"),
                "repo_path": str(repo),
            },
            indent=2,
        )
    )


def cmd_collect_prs(_args) -> None:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "collect_history.py")])
    sys.exit(r.returncode)


def cmd_generate(args) -> None:
    if args.strategy == "rules":
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_rules_pipeline.py")])
        sys.exit(r.returncode)
    if args.strategy == "llm":
        cands = ROOT / "data" / "generated" / "llm_candidates.jsonl"
        if not cands.exists():
            print(
                "No LLM candidates at data/generated/llm_candidates.jsonl. "
                "Offline mode requires this file; live generation needs "
                "HWE_SMITH_LLM_API_URL/KEY (see generators/llm_provider.py).",
                file=sys.stderr,
            )
            sys.exit(1)
        n = sum(1 for l in cands.read_text().splitlines() if l.strip())
        print(f"{n} LLM candidates staged; run: python -m hwe_smith validate --strategy llm")
        return
    if args.strategy == "history":
        print("History candidates are defined in scripts/run_history_pipeline.py; "
              "run: python -m hwe_smith validate --strategy history")
        return


def cmd_validate(args) -> None:
    script = {
        "rules": ROOT / "scripts" / "run_rules_pipeline.py",
        "llm": ROOT / "scripts" / "run_llm_pipeline.py",
        "history": ROOT / "scripts" / "run_history_pipeline.py",
    }[args.strategy]
    r = subprocess.run([sys.executable, str(script)])
    sys.exit(r.returncode)


def cmd_package(_args) -> None:
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "package_dataset.py")])
    sys.exit(r.returncode)


def cmd_report(_args) -> None:
    summary = {}
    for name, key_total, key_acc in [
        ("generation_report.json", "total_candidates", "accepted"),
        ("llm_validation_report.json", "total", "accepted"),
        ("history_validation_report.json", "total", "accepted"),
    ]:
        path = ROOT / "results" / name
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        summary[name] = {
            "total": d.get(key_total),
            "accepted": d.get(key_acc),
        }
    tasks = sorted(
        p.name for p in (ROOT / "data" / "validated" / "tasks").glob("hwe_*") if p.is_dir()
    )
    final = ROOT / "results" / "final_implementation_report.json"
    print(
        json.dumps(
            {
                "reports": summary,
                "validated_task_dirs": tasks,
                "final_report_present": final.exists(),
            },
            indent=2,
        )
    )


def main() -> None:
    p = argparse.ArgumentParser(prog="hwe_smith")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover").set_defaults(func=cmd_discover)
    sub.add_parser("collect-prs").set_defaults(func=cmd_collect_prs)
    g = sub.add_parser("generate")
    g.add_argument("--strategy", choices=["rules", "llm", "history"], default="rules")
    g.set_defaults(func=cmd_generate)
    v = sub.add_parser("validate")
    v.add_argument("--strategy", choices=["rules", "llm", "history"], default="rules")
    v.set_defaults(func=cmd_validate)
    sub.add_parser("package").set_defaults(func=cmd_package)
    sub.add_parser("report").set_defaults(func=cmd_report)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
