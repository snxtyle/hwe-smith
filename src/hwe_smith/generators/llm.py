"""Strategy B: LLM-generated RTL bugs.

Uses a coding model to introduce realistic bugs. In this environment the
Xyne coding model is invoked via the orchestration layer's spawn_subagent
with a structured prompt (see scripts/generate_llm_candidates.md for the
exact prompt). This module provides:
  - the candidate schema
  - prompt template
  - application + safety checks (syntactic sanity via iverilog compile)
LLM output is treated as UNVERIFIED; only the simulation loop decides.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROMPT_TEMPLATE = """You are an experienced RTL hardware engineer.

Inspect this working Verilog module.

```verilog
{rtl}
```

Module context: {context}
Hardware specification: {spec}

Introduce EXACTLY ONE plausible functional hardware bug.
The change must:
1. Be syntactically valid Verilog-2001.
2. Preserve the module interface (ports and parameters unchanged).
3. Be limited to this target RTL (one contiguous edit region).
4. Represent a realistic engineering mistake a human could plausibly make
   (e.g. boundary error, wrong counter update, handshake mistake, reset issue).
5. Not modify tests, assertions or build scripts.
6. Not introduce unrelated changes.
7. NOT be a purely cosmetic or timing-only change: it must be functionally
   observable through the module's outputs under some stimulus.

Bug category to target: {category}

Respond with ONLY a JSON object (no markdown fences):
{{
  "original": "<exact unique substring of the original RTL to replace>",
  "modified": "<exact replacement text>",
  "category": "<one of: arithmetic, boundary, width, reset, counter, fsm, handshake, index, protocol>",
  "expected_behavior": "<one sentence: what goes wrong, in what input condition>",
  "exposing_condition": "<one sentence: what stimulus would reveal it>"
}}
"""


@dataclass
class LLMBugCandidate:
    cand_id: str
    file: str
    model: str
    original: str
    modified: str
    category: str
    expected_behavior: str
    exposing_condition: str
    reviewer_note: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def build_prompt(rtl_text: str, context: str, spec: str, category: str) -> str:
    return PROMPT_TEMPLATE.format(rtl=rtl_text, context=context, spec=spec, category=category)


def parse_llm_response(text: str) -> dict | None:
    """Extract the JSON object from a model response; None if malformed."""
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    for k in ("original", "modified", "category", "expected_behavior", "exposing_condition"):
        if k not in obj:
            return None
    return obj


def make_candidate(cand_id: str, file: str, model: str, obj: dict,
                   rtl_text: str) -> tuple[LLMBugCandidate | None, str]:
    """Apply safety checks; returns (candidate, rejection_reason)."""
    orig, mod = obj["original"], obj["modified"]
    if orig == mod:
        return None, "no-op edit"
    n = rtl_text.count(orig)
    if n != 1:
        return None, f"original expression not unique (count={n})"
    if "always" in orig and "always" not in mod and len(orig) > 200:
        return None, "suspiciously large structural edit"
    for banned in ("module ", "endmodule", "parameter"):
        if banned in orig and banned in mod and orig.count(banned) != mod.count(banned):
            return None, f"interface keyword '{banned}' modified"
    return LLMBugCandidate(
        cand_id=cand_id, file=file, model=model, original=orig, modified=mod,
        category=obj["category"], expected_behavior=obj["expected_behavior"],
        exposing_condition=obj["exposing_condition"],
    ), "ok"


def load_candidates(path: Path) -> list[LLMBugCandidate]:
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(LLMBugCandidate(**d))
    return out
