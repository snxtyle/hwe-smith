"""Problem-statement leakage check.

Verifies that a generated problem statement does not contain:
  - the exact original expression
  - the exact modified expression
  - the reference patch content
  - hidden test names/assertion literals
"""
from __future__ import annotations

import re
from pathlib import Path


def check_leakage(problem_statement: str, original_expr: str,
                  modified_expr: str, patch_text: str | None = None,
                  hidden_test_tokens: list[str] | None = None) -> list[str]:
    """Return list of leakage violations (empty = clean)."""
    leaks = []
    ps = problem_statement

    def norm(s: str) -> str:
        # collapse whitespace so multi-line RTL snippets can't sneak through
        return re.sub(r"\s+", " ", s).strip()

    nps = norm(ps)
    if len(original_expr.strip()) > 8 and norm(original_expr) in nps:
        leaks.append("original_expression")
    if len(modified_expr.strip()) > 8 and norm(modified_expr) in nps:
        leaks.append("modified_expression")
    if patch_text:
        # any +/- hunk line (normalized) appearing in the statement
        for line in patch_text.splitlines():
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                body = norm(line[1:])
                if len(body) > 12 and body in nps:
                    leaks.append("patch_hunk")
                    break
    for tok in hidden_test_tokens or []:
        if len(tok) > 6 and tok.lower() in ps.lower():
            leaks.append(f"hidden_test_token:{tok}")
    return leaks
