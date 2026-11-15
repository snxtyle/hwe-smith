"""Unified candidate schema used by rules / LLM / history generators."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# Canonical validation outcomes
ACCEPTED = "ACCEPTED"
REJECTED_PREFIX = "REJECT_"
INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
UNRESOLVED = "UNRESOLVED"

# Map legacy pipeline verdicts onto the public vocabulary
LEGACY_VERDICT_MAP = {
    "ACCEPT": ACCEPTED,
    "REJECT_BASELINE": INFRASTRUCTURE_ERROR,  # pristine should pass; env/repo problem
    "REJECT_NONUNIQUE": "REJECT_INTEGRITY",
    "REJECT_SURVIVES": "REJECT_SURVIVES",
    "REJECT_COMPILED_CLEAN": "REJECT_COMPILE_ERROR",
    "REJECT_RESTORE_FAILED": "REJECT_INTEGRITY",
    "REJECT_RESTORE_NOT_CLEAN": "REJECT_INTEGRITY",
    "REJECT_REGRESSION": "REJECT_REGRESSION",
    "REJECT_REAPPLY_FAILED": "REJECT_INTEGRITY",
    "REJECT_FLAKY": "REJECT_NON_REPRODUCIBLE",
}


def normalize_verdict(verdict: str) -> str:
    if verdict in (ACCEPTED, INFRASTRUCTURE_ERROR, UNRESOLVED) or verdict.startswith("REJECT_"):
        if verdict == "ACCEPT":
            return ACCEPTED
        return LEGACY_VERDICT_MAP.get(verdict, verdict)
    return LEGACY_VERDICT_MAP.get(verdict, verdict)


@dataclass
class Candidate:
    """One proposed bug before/after validation."""

    cand_id: str
    repo: str
    commit: str
    file: str
    module: str
    category: str
    strategy: str  # rules | llm | history
    original: str
    modified: str
    expected_effect: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mutation(
        cls,
        mut_id: str,
        file: str,
        category: str,
        original: str,
        modified: str,
        expected_effect: str,
        strategy: str = "rules",
        repo: str = "alexforencich/verilog-uart",
        commit: str = "1b867e53af738e4a8bc7c839ca2f1c07f40382dc",
        **extra: Any,
    ) -> "Candidate":
        module = file.rsplit("/", 1)[-1].removesuffix(".v")
        return cls(
            cand_id=mut_id,
            repo=repo,
            commit=commit,
            file=file,
            module=module,
            category=category,
            strategy=strategy,
            original=original,
            modified=modified,
            expected_effect=expected_effect,
            metadata=dict(extra),
        )
