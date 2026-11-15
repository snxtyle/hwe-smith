"""Deduplication fingerprints for validated tasks."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


def _norm_expr(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def fingerprint(
    *,
    repo: str,
    commit: str,
    file: str,
    module: str,
    category: str,
    original: str,
    modified: str,
    fail_signature: str = "",
) -> str:
    """Stable edit fingerprint.

    Primary identity is repo/commit/file + normalized original→modified text.
    Category and fail_signature are recorded separately by callers; they are
    intentionally NOT part of the hash so the same underlying bug packaged
    twice (e.g. RULE_001 vs INT_001) still dedupes.
    """
    del category, module, fail_signature  # documented inputs; not hashed
    payload = "|".join(
        [
            repo,
            commit,
            file,
            _norm_expr(original),
            _norm_expr(modified),
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def fail_signature_from_record(rec: dict) -> str:
    """Coarse behavioural signature from mutated sim result."""
    mut = rec.get("mutated") or {}
    parts = [
        str(mut.get("status", "")),
        str(mut.get("exit_code", "")),
        str(mut.get("tests_failed", "")),
    ]
    log = mut.get("log") or ""
    # keep short stable tokens from assertion messages
    for token in ("received data does not match", "TIMEOUT", "AssertionError", "FAIL"):
        if token.lower() in log.lower():
            parts.append(token)
            break
    return "|".join(parts)


@dataclass
class DedupDecision:
    task_id: str
    fingerprint: str
    keep: bool
    reason: str
    duplicate_of: str | None = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "fingerprint": self.fingerprint,
            "keep": self.keep,
            "reason": self.reason,
            "duplicate_of": self.duplicate_of,
        }


def _task_priority(name: str) -> tuple[int, str]:
    # Prefer production strategy IDs over integration-test packaging artifacts.
    if name.startswith("hwe_INT_"):
        return (1, name)
    return (0, name)


def dedupe_tasks(task_dirs: list[Path]) -> list[DedupDecision]:
    """First occurrence kept; later identical fingerprints marked duplicate."""
    seen: dict[str, str] = {}
    out: list[DedupDecision] = []
    for td in sorted(task_dirs, key=lambda p: _task_priority(p.name)):
        meta_path = td / "metadata.json"
        if not meta_path.exists():
            out.append(
                DedupDecision(td.name, "missing", False, "missing metadata.json")
            )
            continue
        meta = json.loads(meta_path.read_text())
        mut = meta.get("mut") or {}
        fp = fingerprint(
            repo=meta.get("repo", "alexforencich/verilog-uart"),
            commit=meta.get("commit", "1b867e53af738e4a8bc7c839ca2f1c07f40382dc"),
            file=mut.get("file", ""),
            module=Path(mut.get("file", "")).stem,
            category=mut.get("category", ""),
            original=mut.get("original", ""),
            modified=mut.get("modified", ""),
            fail_signature=fail_signature_from_record(meta),
        )
        if fp in seen:
            out.append(
                DedupDecision(
                    td.name,
                    fp,
                    False,
                    "duplicate fingerprint of earlier accepted task",
                    duplicate_of=seen[fp],
                )
            )
        else:
            seen[fp] = td.name
            out.append(DedupDecision(td.name, fp, True, "first occurrence"))
    return out
