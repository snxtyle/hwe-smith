"""Unit tests for pure logic: mutation engine, patch application, packaging,
classification schema. No simulation involved (integration tests cover that)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hwe_smith.generators.rules import generate_mutations, apply_mutation, Mutation
from hwe_smith.generators.llm import parse_llm_response, make_candidate
from hwe_smith.simulation.runner import _parse_results_xml


RTL_RX = (ROOT / "cache" / "verilog-uart" / "rtl" / "uart_rx.v")
RTL_TX = (ROOT / "cache" / "verilog-uart" / "rtl" / "uart_tx.v")

pytestmark = pytest.mark.skipif(
    not RTL_RX.exists(), reason="cache/verilog-uart not cloned; run setup first")


def test_generate_mutations_unique_only():
    texts = {"rtl/uart_rx.v": RTL_RX.read_text(), "rtl/uart_tx.v": RTL_TX.read_text()}
    muts = generate_mutations(texts)
    assert len(muts) >= 5
    # every mutation anchor must be unique in its file by construction
    for m in muts:
        assert texts[m.file].count(m.original) == 1
        assert m.mut_id.startswith("RULE_")
        assert m.category and m.expected_effect


def test_apply_mutation_roundtrip():
    text = RTL_RX.read_text()
    muts = generate_mutations({"rtl/uart_rx.v": text})
    assert muts
    m = muts[0]
    mutated = apply_mutation(text, m)
    assert mutated is not None and mutated != text
    # restore: reverse replacement must work when anchor still unique
    restored = mutated.replace(m.modified, m.original)
    assert restored == text


def test_apply_mutation_nonunique_anchor_rejected():
    m = Mutation("X", "f.v", "boundary", "begin", "end", "effect")
    assert apply_mutation("begin end begin end", m) is None


def test_parse_llm_response_json():
    raw = '''Sure! Here is the bug:
{"original": "a <= b;", "modified": "a <= ~b;", "category": "reset",
 "expected_behavior": "x", "exposing_condition": "y"}'''
    obj = parse_llm_response(raw)
    assert obj and obj["category"] == "reset"
    assert parse_llm_response("no json here") is None
    assert parse_llm_response('{"original": "a"}') is None  # missing keys


def test_make_candidate_safety_checks():
    rtl = "assign x = y;\nassign z = w;\n"
    ok, reason = make_candidate("L1", "f.v", "test-model", {
        "original": "assign x = y;", "modified": "assign x = ~y;",
        "category": "reset", "expected_behavior": "e", "exposing_condition": "c",
    }, rtl)
    assert ok is not None and reason == "ok"
    # non-unique anchor rejected
    ok2, reason2 = make_candidate("L2", "f.v", "m", {
        "original": "assign", "modified": "assign2", "category": "c",
        "expected_behavior": "e", "exposing_condition": "x",
    }, rtl)
    assert ok2 is None and "unique" in reason2
    # no-op rejected
    ok3, reason3 = make_candidate("L3", "f.v", "m", {
        "original": "assign x = y;", "modified": "assign x = y;", "category": "c",
        "expected_behavior": "e", "exposing_condition": "x",
    }, rtl)
    assert ok3 is None and "no-op" in reason3


def test_results_xml_parser(tmp_path):
    xml = tmp_path / "results.xml"
    xml.write_text("""<testsuite>
  <testcase name="t1" time="1"/>
  <testcase name="t2" time="1"><failure msg="x"/></testcase>
  <testcase name="t3" time="1"><skipped/></testcase>
</testsuite>""")
    passed, failed = _parse_results_xml(xml)
    assert passed == 1 and failed == 1


def test_raw_data_schema():
    prs = ROOT / "data" / "raw" / "pull_requests.jsonl"
    repos = ROOT / "data" / "raw" / "repositories.jsonl"
    if not prs.exists():
        pytest.skip("raw data not collected yet")
    for line in prs.read_text().splitlines():
        d = json.loads(line)
        assert d["classification"] in {
            "RTL_BUG_FIX", "INTERFACE_BUG", "PROTOCOL_BUG", "TEST_ONLY",
            "FEATURE", "REFACTOR", "DOCUMENTATION", "CI_OR_BUILD", "UNCLASSIFIED"}
        assert "commit" in d and "title" in d
    r = json.loads(repos.read_text().splitlines()[0])
    assert len(r["commit"]) == 40  # pinned SHA
