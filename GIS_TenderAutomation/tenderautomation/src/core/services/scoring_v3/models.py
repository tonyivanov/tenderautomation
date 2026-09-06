"""Scoring v3 — data models (LLM classification)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    CORE = "core"
    REVIEW = "review"
    REJECT = "reject"

# ── LLM Classification Item ──────────────────────────────────────────────
@dataclass
class LLMClassificationItem:
    id: str
    verdict: str = "review"
    fit_score: int = 50
    confidence: float = 0.5
    procurement_type: str = "unknown"
    primary_domain: str = "unknown"
    secondary_domains: list[str] = field(default_factory=list)
    needs_documents: bool = False
    positive_evidence: list[str] = field(default_factory=list)
    negative_evidence: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    reason: str = ""

# ── V3 Result (aggregated per tender) ────────────────────────────────────
@dataclass
class V3Result:
    tender_id: str = ""
    original_title: str = ""
    cache_hit: bool = False
    analysis_status: str = ""  # completed / failed / budget_paused / cached

    # First pass
    first_pass: LLMClassificationItem = field(
        default_factory=lambda: LLMClassificationItem(id="")
    )
    primary_model: str = ""
    primary_model_used: str = ""

    # Judge pass
    judge_pass: LLMClassificationItem | None = None
    judge_model: str = ""
    judge_model_used: str = ""

    # Final
    final_verdict: str = "review"
    final_fit_score: int = 50
    final_confidence: float = 0.5
    classifier_disagreement: bool = False

    # Queue
    queue: str = "P2"  # P1 / P2 / P3 / reject
    priority: int = 50
    pre_filter_verdict: str = ""
    pre_filter_queue: str = ""

    # Costs
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0

    # Legacy (diagnostic only)
    legacy_tier: str = ""
    legacy_score: int = 0
    legacy_category: str = ""

    @property
    def needs_judge(self) -> bool:
        fp = self.first_pass
        return (
            fp.confidence < 0.80
            or fp.verdict == "review"
            or (fp.verdict == "reject" and self.legacy_category in ("core", "review", "lowish"))
            or (fp.verdict == "core" and self.legacy_category == "hard_stop")
            or fp.procurement_type == "mixed"
            or "ambiguous_title" in fp.risk_flags
            or "insufficient_context" in fp.risk_flags
        )
