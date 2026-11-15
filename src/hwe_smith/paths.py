"""Single source of truth for project paths and generation config."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent


def load_generation_config() -> dict:
    path = ROOT / "configs" / "generation.yaml"
    return yaml.safe_load(path.read_text())


def load_repository_config() -> dict:
    path = ROOT / "configs" / "repository.yaml"
    return yaml.safe_load(path.read_text())


def sim_timeout_s() -> int:
    cfg = load_generation_config()
    return int(cfg.get("timeout_seconds", 60))


def repo_path() -> Path:
    cfg = load_generation_config()
    return ROOT / cfg.get("cache_dir", "cache/verilog-uart")


def work_path() -> Path:
    cfg = load_generation_config()
    return ROOT / cfg.get("workspace_dir", "data/work")
