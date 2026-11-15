"""Explainable preliminary difficulty tiers (not agent-calibrated)."""
from __future__ import annotations

from dataclasses import dataclass


EASY = "easy"
MEDIUM = "medium"
HARD = "hard"

# Categories that typically need multi-cycle / protocol reasoning
_MEDIUM_CATS = {
    "handshake",
    "framing",
    "protocol",
    "fsm",
    "counter",
    "timing",
    "status",
}
_HARD_CATS = {
    "synchronizer",
    "cross_module",
    "param",
    "metastability",
}


@dataclass
class Difficulty:
    tier: str
    reasons: list[str]

    def to_dict(self) -> dict:
        return {"tier": self.tier, "reasons": self.reasons}


def classify_difficulty(
    *,
    category: str,
    file: str,
    original: str,
    modified: str,
    strategy: str = "",
    fail_is_timeout: bool = False,
    multi_file: bool = False,
) -> Difficulty:
    """Heuristic tiers — recorded reasons, not empirical agent scores."""
    reasons: list[str] = []
    cat = (category or "").lower()
    edit_span = abs(len(modified) - len(original)) + min(len(original), len(modified))

    if multi_file:
        reasons.append("spans multiple modules/files")
        return Difficulty(HARD, reasons)

    if cat in _HARD_CATS:
        reasons.append(f"category '{category}' typically requires subtle protocol/timing reasoning")
        return Difficulty(HARD, reasons)

    if fail_is_timeout:
        reasons.append("failure manifests as hang/timeout (deadlock-style debugging)")
        return Difficulty(HARD if cat in _MEDIUM_CATS else MEDIUM, reasons)

    if cat in _MEDIUM_CATS or strategy == "history":
        reasons.append(f"category/strategy suggests multi-cycle or protocol reasoning ({category or strategy})")
        if edit_span < 40:
            reasons.append("edit is localized to one expression")
        return Difficulty(MEDIUM, reasons)

    # default: localized arithmetic/boundary/reset single-site
    reasons.append("localized single-module expression edit")
    reasons.append(f"category '{category or 'unknown'}' maps to straightforward functional symptom")
    if edit_span > 120:
        reasons.append("larger contiguous edit region → promote to medium")
        return Difficulty(MEDIUM, reasons)
    return Difficulty(EASY, reasons)
