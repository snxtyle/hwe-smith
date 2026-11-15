"""Integration tests: real compile/simulate/validate round trip.
These run actual Icarus simulations (~1-2 min each) and are marked slow;
run with: pytest tests/integration -q"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(
    not (ROOT / "cache" / "verilog-uart").exists(),
    reason="cache/verilog-uart not cloned; run setup first")


@pytest.fixture(scope="module")
def runner(tmp_path_factory):
    from hwe_smith.simulation.runner import SimRunner
    return SimRunner(ROOT / "cache" / "verilog-uart",
                     tmp_path_factory.mktemp("ws"), timeout_s=90)


def test_1_clean_repo_compiles_and_passes(runner):
    ws = runner.make_workspace("integ_pristine")
    res = runner.run_test(ws, "tb/uart_rx", tag="pristine")
    assert res.status == "PASS", res.log[-500:]
    assert res.tests_passed >= 1


def test_2_mutation_makes_it_fail(runner):
    ws = runner.make_workspace("integ_mutated")
    f = ws / "rtl" / "uart_rx.v"
    orig = f.read_text()
    old = "if (bit_cnt > DATA_WIDTH+1) begin"
    assert orig.count(old) == 1
    f.write_text(orig.replace(old, "if (bit_cnt > DATA_WIDTH) begin"))
    res = runner.run_test(ws, "tb/uart_rx", tag="mutated")
    assert res.status == "FAIL", f"expected functional failure, got {res.status}"


def test_3_restore_makes_it_pass_again(runner):
    ws = runner.make_workspace("integ_restore")
    f = ws / "rtl" / "uart_rx.v"
    orig = f.read_text()
    old = "if (bit_cnt > DATA_WIDTH+1) begin"
    f.write_text(orig.replace(old, "if (bit_cnt > DATA_WIDTH) begin"))
    f.write_text(f.read_text().replace("if (bit_cnt > DATA_WIDTH) begin", old))
    assert f.read_text() == orig
    res = runner.run_test(ws, "tb/uart_rx", tag="restored")
    assert res.status == "PASS", res.log[-500:]


def test_4_full_validation_accepts_known_bug(runner, tmp_path):
    from run_rules_pipeline import validate, package
    from hwe_smith.generators.rules import Mutation
    m = Mutation("INT_001", "rtl/uart_rx.v", "boundary",
                 "if (bit_cnt > DATA_WIDTH+1) begin",
                 "if (bit_cnt > DATA_WIDTH) begin",
                 "start-bit FSM entered one count early")
    rec = validate(m, runner, tmp_path)
    assert rec["verdict"] == "ACCEPT", rec
    package(rec)
    td = ROOT / "data" / "validated" / "tasks" / "hwe_INT_001"
    assert (td / "metadata.json").exists()
    assert (td / "reference_patch.patch").exists()
    assert (td / "problem_statement.md").exists()
    meta = (td / "metadata.json").read_text()
    # leakage check: problem statement must not contain the exact fix
    ps = (td / "problem_statement.md").read_text()
    assert "bit_cnt > DATA_WIDTH+1" not in ps
