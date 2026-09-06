"""Data models for Scoring v2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClassifierDecision:
    """Решение одного классификатора."""
    candidate: bool = False
    confidence: float = 0.0
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateResult:
    """Полный результат квалификации v2."""
    tender_id: str = ""
    original_title: str = ""
    normalized_title: str = ""

    # Итоговые решения (v2)
    positive_candidate: bool = False          # есть содержательный положительный сигнал
    selected_for_human_review: bool = False   # попадает на ревью
    review_priority_score: int = 0
    review_queue: str = ""  # P1 / P2 / P3 / reject
    auto_reject: bool = False

    # v1 совместимость (для сравнения)
    candidate_for_human_review: bool = False  # deprecated, = selected_for_human_review

    # Решения классификаторов
    legacy: ClassifierDecision = field(default_factory=ClassifierDecision)
    hard_stop: ClassifierDecision = field(default_factory=ClassifierDecision)
    rules: ClassifierDecision = field(default_factory=ClassifierDecision)
    action_object: ClassifierDecision = field(default_factory=ClassifierDecision)
    entity_gate: ClassifierDecision = field(default_factory=ClassifierDecision)
    strong_object_service: ClassifierDecision = field(default_factory=ClassifierDecision)
    semantic: ClassifierDecision | None = None  # Этап 2
    llm: ClassifierDecision | None = None        # Этап 3

    # Флаги
    classifier_disagreement: bool = False
    has_strong_it_signal: bool = False
    supply_only: bool = False
    p3_control_sample: bool = False
    procurement_type: str = ""  # supply_only / services_only / mixed_supply_and_services / licenses_only / unknown

    # Semantic core (после strip_prefixes + expand_abbreviations)
    semantic_core_title: str = ""

    # Причины
    decision_reasons: list[str] = field(default_factory=list)

    # Эталонная v1 для сравнения
    v1_tier: str = ""
    v1_score: int = 0
    v1_category: str = ""


@dataclass
class HardStopRule:
    """Правило безопасного hard-stop."""
    id: str
    phrases: list[str]
    confidence: float = 0.99


@dataclass
class StrongRule:
    """Сильное профильное правило."""
    id: str
    phrases: list[str]
    weight: int = 15
