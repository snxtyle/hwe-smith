import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from hwe_smith.packaging.leakage import check_leakage


def test_clean_statement():
    ps = "The UART receiver drops or corrupts bytes under some input conditions."
    assert check_leakage(ps, "if (bit_cnt > DATA_WIDTH+1) begin",
                         "if (bit_cnt > DATA_WIDTH) begin") == []


def test_original_expression_leak():
    ps = "Fix the bug: change `if (bit_cnt > DATA_WIDTH+1) begin` to something else."
    leaks = check_leakage(ps, "if (bit_cnt > DATA_WIDTH+1) begin",
                          "if (bit_cnt > DATA_WIDTH) begin")
    assert "original_expression" in leaks


def test_modified_expression_leak():
    ps = "The fix should make the counter use DATA_WIDTH instead."
    leaks = check_leakage(ps, "orig expr here", "use DATA_WIDTH instead")
    assert any(l == "modified_expression" for l in leaks)


def test_patch_hunk_leak():
    patch = '--- a/x.v\n+++ b/x.v\n-        bit_cnt <= DATA_WIDTH+1;\n+        bit_cnt <= DATA_WIDTH;\n'
    ps = "The counter should count one fewer state: bit_cnt <= DATA_WIDTH; is wrong."
    leaks = check_leakage(ps, "old = 1;", "other", patch_text=patch)
    assert "patch_hunk" in leaks


def test_hidden_test_token():
    ps = "Make sure test_overrun_special_case passes."
    leaks = check_leakage(ps, "orig", "mod",
                          hidden_test_tokens=["test_overrun_special_case"])
    assert any(l.startswith("hidden_test_token") for l in leaks)
