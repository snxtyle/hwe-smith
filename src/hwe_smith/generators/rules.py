"""Strategy A: rule-based RTL mutation engine.

Operators are applied as exact, unique text replacements on RTL files.
Each mutation records original/modified expressions for provenance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Mutation:
    mut_id: str
    file: str
    category: str
    original: str
    modified: str
    expected_effect: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _unique_sub(text: str, old: str, new: str) -> str | None:
    """Replace iff `old` occurs exactly once. Returns new text or None."""
    n = text.count(old)
    if n != 1:
        return None
    return text.replace(old, new)


OPERATORS = {
    "boundary_lt_le": [
        # RX start-bit detection counter thresholds
        ("if (bit_cnt > DATA_WIDTH+1) begin", "if (bit_cnt > DATA_WIDTH) begin",
         "boundary", "Start-bit state entered one count early; last data bit window shifted"),
        ("end else if (bit_cnt > 1) begin", "end else if (bit_cnt > 0) begin",
         "boundary", "Data shift continues into stop-bit position"),
    ],
    "off_by_one_arith": [
        ("prescale_reg <= (prescale << 3)-1;", "prescale_reg <= (prescale << 3)-2;",
         "arithmetic", "Bit-period counter one clock short; sampling point drifts per bit"),
        ("prescale_reg <= (prescale << 2)-2;", "prescale_reg <= (prescale << 2)-1;",
         "arithmetic", "Start-bit detection delayed by one clock"),
    ],
    "shift_width": [
        ("prescale_reg <= (prescale << 3)-1;", "prescale_reg <= (prescale << 2)-1;",
         "width/rate", "Baud rate generator shifted by wrong factor: 8x instead of 16x oversampling"),
    ],
    "reset_polarity": [
        ("        rxd_reg <= 1;\n", "        rxd_reg <= 0;\n",
         "reset", "rxd synchronizer resets to 0, spurious start bit after reset"),
        ("        busy_reg <= 0;\n        overrun_error_reg <= 0;\n        frame_error_reg <= 0;\n",
         "        busy_reg <= 1;\n        overrun_error_reg <= 0;\n        frame_error_reg <= 0;\n",
         "reset", "busy asserted out of reset"),
    ],
    "handshake": [
        # TX: accept word when busy (double-load corruption)
        ("            if (s_axis_tvalid) begin", "            if (s_axis_tvalid || s_axis_tready) begin",
         "handshake", "TX reloads while already shifting: corrupted output byte"),
    ],
    "stop_bit": [
        # TX stop-bit timing: return to idle one bit early
        ("            else if (bit_cnt == 1) begin\n                bit_cnt <= bit_cnt - 1;\n                prescale_reg <= (prescale << 3);\n                txd_reg <= 1;\n            end",
         "            else if (bit_cnt == 1) begin\n                bit_cnt <= bit_cnt - 1;\n                prescale_reg <= (prescale << 3);\n                txd_reg <= data_reg[0];\n            end",
         "framing", "Stop bit driven with data bit value instead of 1: framing error at receiver"),
    ],
    "overrun": [
        ("overrun_error_reg <= m_axis_tvalid_reg;", "overrun_error_reg <= 0;",
         "status", "Overrun error flag never asserted on word overwrite"),
    ],
    "data_corrupt": [
        # RX data shift: swap bit order within the byte (LSB-first protocol violation)
        ("data_reg <= {rxd_reg, data_reg[DATA_WIDTH-1:1]};",
         "data_reg <= {data_reg[DATA_WIDTH-1:1], rxd_reg};",
         "protocol", "Bit ordering reversed: every received byte arrives bit-reversed"),
        # RX stop-bit handling: treat bad stop bit as good (mask framing errors)
        ("                if (rxd_reg) begin\n                    m_axis_tdata_reg <= data_reg;\n                    m_axis_tvalid_reg <= 1;\n                    overrun_error_reg <= m_axis_tvalid_reg;\n                end else begin\n                    frame_error_reg <= 1;\n                end",
         "                if (rxd_reg || !rxd_reg) begin\n                    m_axis_tdata_reg <= data_reg;\n                    m_axis_tvalid_reg <= 1;\n                    overrun_error_reg <= m_axis_tvalid_reg;\n                end else begin\n                    frame_error_reg <= 1;\n                end",
         "framing", "Frame error masking: bytes accepted even with invalid stop bit"),
    ],
    "tx_framing": [
        # TX: send 7 bits instead of 8 (short character)
        ("                bit_cnt <= DATA_WIDTH+1;\n                data_reg <= {1'b1, s_axis_tdata};",
         "                bit_cnt <= DATA_WIDTH;\n                data_reg <= {1'b1, s_axis_tdata};",
         "counter", "TX sends one data bit short: every byte truncated, framing broken"),
        # TX: never assert ready after load (stall)
        ("        end else if (bit_cnt == 0) begin\n            s_axis_tready_reg <= 1;",
         "        end else if (bit_cnt == 0) begin\n            s_axis_tready_reg <= 0;",
         "handshake", "TX ready never re-asserted after first byte: pipeline stalls after one word"),
    ],
}


def generate_mutations(rtl_files: dict[str, str], max_per_file: int = 20) -> list[Mutation]:
    """Return all applicable unique-match mutations across rtl files."""
    out: list[Mutation] = []
    idx = 0
    for fname, text in rtl_files.items():
        count = 0
        for op_name, rules in OPERATORS.items():
            for old, new, cat, effect in rules:
                if count >= max_per_file:
                    break
                if _unique_sub(text, old, new) is not None:
                    idx += 1
                    out.append(Mutation(
                        mut_id=f"RULE_{idx:03d}",
                        file=fname,
                        category=cat,
                        original=old.strip(),
                        modified=new.strip(),
                        expected_effect=effect,
                    ))
                    count += 1
    return out


def apply_mutation(text: str, mut: Mutation) -> str | None:
    """Apply one mutation to file text; None if original no longer unique."""
    padded_old = mut.original
    # we stripped the originals for storage; match against stripped content
    if text.count(mut.original) != 1:
        return None
    return text.replace(mut.original, mut.modified)
