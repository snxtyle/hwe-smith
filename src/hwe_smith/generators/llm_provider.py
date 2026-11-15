"""LLM bug-candidate provider interface.

Offline JSONL is the default and required path for reproducibility.
Optional live providers can be plugged in via environment variables without
embedding secrets in the repo.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from hwe_smith.generators.llm import (
    LLMBugCandidate,
    build_prompt,
    load_candidates,
    make_candidate,
    parse_llm_response,
)


class LLMBugProvider(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        cand_id: str,
        file: str,
        rtl_text: str,
        context: str,
        spec: str,
        category: str,
    ) -> tuple[LLMBugCandidate | None, str]:
        """Return (candidate, reason)."""


class OfflineJSONLProvider(LLMBugProvider):
    """Load pre-generated candidates; no network."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._by_id = {c.cand_id: c for c in load_candidates(self.path)}

    def generate(
        self,
        *,
        cand_id: str,
        file: str,
        rtl_text: str,
        context: str,
        spec: str,
        category: str,
    ) -> tuple[LLMBugCandidate | None, str]:
        c = self._by_id.get(cand_id)
        if c is None:
            return None, f"cand_id {cand_id} not in {self.path}"
        # re-run safety against current RTL
        obj = {
            "original": c.original,
            "modified": c.modified,
            "category": c.category,
            "expected_behavior": c.expected_behavior,
            "exposing_condition": c.exposing_condition,
        }
        return make_candidate(c.cand_id, c.file, c.model, obj, rtl_text)

    def all(self) -> list[LLMBugCandidate]:
        return list(self._by_id.values())


class EnvHTTPProvider(LLMBugProvider):
    """Optional live provider.

    Requires:
      HWE_SMITH_LLM_API_URL
      HWE_SMITH_LLM_API_KEY
      HWE_SMITH_LLM_MODEL (optional)
    Not used unless explicitly constructed — offline mode remains default.
    """

    def __init__(self):
        self.url = os.environ.get("HWE_SMITH_LLM_API_URL", "")
        self.key = os.environ.get("HWE_SMITH_LLM_API_KEY", "")
        self.model = os.environ.get("HWE_SMITH_LLM_MODEL", "unspecified")
        if not self.url or not self.key:
            raise RuntimeError(
                "live LLM provider requires HWE_SMITH_LLM_API_URL and HWE_SMITH_LLM_API_KEY"
            )

    def generate(
        self,
        *,
        cand_id: str,
        file: str,
        rtl_text: str,
        context: str,
        spec: str,
        category: str,
    ) -> tuple[LLMBugCandidate | None, str]:
        import urllib.request

        prompt = build_prompt(rtl_text, context, spec, category)
        body = json.dumps(
            {"model": self.model, "prompt": prompt, "cand_id": cand_id, "file": file}
        ).encode()
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            raw = resp.read().decode()
        # accept either raw model text or {"text": "..."}
        try:
            payload = json.loads(raw)
            text = payload.get("text") or payload.get("content") or raw
        except json.JSONDecodeError:
            text = raw
        obj = parse_llm_response(text)
        if obj is None:
            return None, "unparseable LLM response"
        return make_candidate(cand_id, file, self.model, obj, rtl_text)


def get_default_provider(jsonl_path: Path) -> OfflineJSONLProvider:
    """Always prefer offline JSONL for validation reproducibility."""
    return OfflineJSONLProvider(jsonl_path)
