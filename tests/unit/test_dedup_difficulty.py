import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from hwe_smith.classification.dedup import fingerprint, DedupDecision, dedupe_tasks
from hwe_smith.classification.difficulty import classify_difficulty, EASY, MEDIUM, HARD
from hwe_smith.schema import normalize_verdict, ACCEPTED


def test_normalize_accept():
    assert normalize_verdict("ACCEPT") == ACCEPTED
    assert normalize_verdict("REJECT_SURVIVES") == "REJECT_SURVIVES"
    assert normalize_verdict("REJECT_COMPILED_CLEAN") == "REJECT_COMPILE_ERROR"


def test_fingerprint_stable_and_sensitive():
    a = fingerprint(
        repo="r", commit="c", file="rtl/uart_rx.v", module="uart_rx",
        category="boundary", original="a <= b;", modified="a <= c;",
        fail_signature="FAIL|1",
    )
    b = fingerprint(
        repo="r", commit="c", file="rtl/uart_rx.v", module="uart_rx",
        category="boundary", original="a <= b;", modified="a <= c;",
        fail_signature="FAIL|1",
    )
    c = fingerprint(
        repo="r", commit="c", file="rtl/uart_rx.v", module="uart_rx",
        category="boundary", original="a <= b;", modified="a <= d;",
        fail_signature="FAIL|1",
    )
    assert a == b and a != c


def test_difficulty_tiers():
    easy = classify_difficulty(
        category="arithmetic", file="rtl/uart_rx.v",
        original="x-1", modified="x-2",
    )
    assert easy.tier == EASY and easy.reasons
    med = classify_difficulty(
        category="handshake", file="rtl/uart_tx.v",
        original="if (a)", modified="if (a || b)",
    )
    assert med.tier == MEDIUM
    hard = classify_difficulty(
        category="reset", file="rtl/uart_rx.v",
        original="a", modified="b", multi_file=True,
    )
    assert hard.tier == HARD


def test_dedupe_keeps_first(tmp_path):
    # synthesize two task dirs with identical mut metadata
    for name in ("hwe_A", "hwe_B"):
        d = tmp_path / name
        d.mkdir()
        (d / "metadata.json").write_text(
            '{"mut":{"file":"rtl/uart_rx.v","category":"boundary",'
            '"original":"x","modified":"y"},"mutated":{"status":"FAIL","exit_code":1,'
            '"tests_failed":1,"log":"AssertionError"}}'
        )
    decisions = dedupe_tasks([tmp_path / "hwe_A", tmp_path / "hwe_B"])
    assert decisions[0].keep and not decisions[1].keep
    assert decisions[1].duplicate_of == "hwe_A"
