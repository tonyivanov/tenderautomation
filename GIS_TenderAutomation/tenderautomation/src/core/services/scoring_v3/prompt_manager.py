"""Prompt versioning and loading."""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "prompts"


def load_system_prompt(version: str = "v3") -> str:
    path = _PROMPTS_DIR / f"tender_classifier_{version}_system.txt"
    return path.read_text(encoding="utf-8")


def load_user_prompt(version: str = "v3") -> str:
    path = _PROMPTS_DIR / f"tender_classifier_{version}_user.txt"
    return path.read_text(encoding="utf-8")


def load_judge_prompt(version: str = "v3") -> str:
    path = _PROMPTS_DIR / f"tender_judge_{version}_system.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""