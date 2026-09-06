"""Stage 1: Safe Hard-Stop detection."""
from __future__ import annotations

from .constants import SAFE_HARD_STOP_PHRASES
from .models import ClassifierDecision, HardStopRule


# Pre-load rules
_HARD_STOP_RULES: list[HardStopRule] = [
    HardStopRule(id=r["id"], phrases=r["phrases"], confidence=r["confidence"])
    for r in SAFE_HARD_STOP_PHRASES
]


def apply_hard_stop(normalized_text: str) -> ClassifierDecision:
    """Check for safe hard-stop phrases. Used BEFORE IT-signal check."""
    for rule in _HARD_STOP_RULES:
        for phrase in rule.phrases:
            if phrase in normalized_text:
                return ClassifierDecision(
                    candidate=True,
                    confidence=rule.confidence,
                    reason=f"safe_hard_stop_{rule.id}",
                    detail={"rule_id": rule.id, "phrase": phrase},
                )
    return ClassifierDecision(candidate=False, confidence=0.0, reason="no_hard_stop")