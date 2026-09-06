"""Stage 2: Rule-based candidate gate — strong profile markers."""
from __future__ import annotations

from typing import Any

from .constants import STRONG_RULES
from .models import ClassifierDecision


def apply_rules(normalized_text: str) -> ClassifierDecision:
    """Check for strong profile GIS markers. Returns candidate=True if any found."""
    matched: list[dict[str, Any]] = []
    total_weight = 0

    for rule in STRONG_RULES:
        for phrase in rule["phrases"]:
            if phrase in normalized_text:
                matched.append({"rule_id": rule["id"], "phrase": phrase, "weight": rule["weight"]})
                total_weight += rule["weight"]
                break  # one match per rule

    if matched:
        return ClassifierDecision(
            candidate=True,
            confidence=min(total_weight / 50, 1.0),  # Normalize to 0..1
            reason="strong_profile_marker",
            detail={"matches": matched, "total_weight": total_weight},
        )
    return ClassifierDecision(candidate=False, confidence=0.0, reason="no_strong_marker")
