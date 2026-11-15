#!/bin/bash
# End-to-end demo: discover -> mine history -> package existing validated set.
# Full re-validation of all strategies is expensive (~hours); use
# scripts/run_*_pipeline.py explicitly when regenerating candidates.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

$PY -m hwe_smith discover
$PY -m hwe_smith collect-prs

echo "== Packaging / dedup / difficulty over existing validated tasks =="
$PY scripts/package_dataset.py

echo "== Strategy availability =="
echo "rules:   python -m hwe_smith validate --strategy rules"
echo "llm:     python -m hwe_smith validate --strategy llm     # offline JSONL"
echo "history: python -m hwe_smith validate --strategy history"

$PY -m hwe_smith report
