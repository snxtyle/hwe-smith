import sys
from pathlib import Path
ROOT = Path("/Users/suraj.nagre/Desktop/hwe-smith")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hwe_smith.simulation.runner import SimRunner
from hwe_smith.generators.rules import generate_mutations
from run_rules_pipeline import validate, package, REPO, WORK, RTL_FILES

runner = SimRunner(REPO, WORK)
rtl_texts = {rel: p.read_text() for rel, p in RTL_FILES.items()}
muts = generate_mutations(rtl_texts)
print(f"total generated: {len(muts)}")
for m in muts:
    print(f"  {m.mut_id} {m.file}: {m.original[:50]!r} -> {m.modified[:50]!r}")

# validate just the first one as smoke test
m = muts[0]
print(f"\nsmoke-validating {m.mut_id}...")
rec = validate(m, runner, WORK / "logs")
print("verdict:", rec["verdict"])
for k in ("baseline", "mutated", "restored", "regression", "mutated_rerun"):
    if k in rec:
        r = rec[k]
        print(f"  {k}: {r['status']} passed={r['tests_passed']} failed={r['tests_failed']} {r['duration_s']}s")
if rec["verdict"] == "ACCEPT":
    package(rec)
    print("packaged to", rec["task_dir"])
