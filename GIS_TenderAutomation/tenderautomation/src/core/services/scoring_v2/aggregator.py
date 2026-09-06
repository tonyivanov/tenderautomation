"""Stage 6-8: Aggregation — исправленная v2.1."""
from __future__ import annotations

from .constants import MANUAL_SAFETY_NET
from .models import CandidateResult, ClassifierDecision


CATEGORY_RANK = {"low": 0, "lowish": 1, "review": 2, "core": 3}


def _max_category(a: str, b: str) -> str:
    return a if CATEGORY_RANK.get(a, 0) >= CATEGORY_RANK.get(b, 0) else b


def aggregate(
    tender_id: str,
    original_title: str,
    normalized_text: str,
    hard_stop: ClassifierDecision,
    rules: ClassifierDecision,
    action_object: ClassifierDecision,
    entity_gate: ClassifierDecision,
    strong_object_service: ClassifierDecision,
    semantic_core_title: str = "",
    v1_tier: str = "",
    v1_score: int = 0,
    v1_category: str = "",
) -> CandidateResult:
    result = CandidateResult(
        tender_id=tender_id,
        original_title=original_title,
        normalized_title=normalized_text,
        semantic_core_title=semantic_core_title,
        hard_stop=hard_stop,
        rules=rules,
        action_object=action_object,
        entity_gate=entity_gate,
        strong_object_service=strong_object_service,
        v1_tier=v1_tier,
        v1_score=v1_score,
        v1_category=v1_category,
    )

    # ── Исправление 1: Legacy scorer как страховочный классификатор ──────
    legacy_candidate = (
        v1_tier in ("qualified", "in_review")
        or v1_category in ("core", "review", "lowish")
    )
    result.legacy = ClassifierDecision(
        candidate=legacy_candidate,
        confidence=0.8 if legacy_candidate else 0.0,
        reason="legacy_v1_scorer" if legacy_candidate else "",
        detail={"v1_tier": v1_tier, "v1_category": v1_category},
    )

    # ── Strong IT signal ──────────────────────────────────────────────────
    result.has_strong_it_signal = rules.candidate

    # ── Исправление 6: Disagreement — только при двух явных решениях ─────
    explicit_decisions: list[str] = []
    if rules.candidate:
        explicit_decisions.append("relevant")
    if hard_stop.candidate and hard_stop.confidence >= 0.99:
        explicit_decisions.append("non_relevant")
    # action_object — weak signal, не участвует в disagreement
    # legacy — страховка, не участвует в disagreement

    result.classifier_disagreement = (
        "relevant" in explicit_decisions
        and "non_relevant" in explicit_decisions
    )

    # ── Hard-stop + IT-signal conflict ────────────────────────────────────
    if hard_stop.candidate and result.has_strong_it_signal:
        result.classifier_disagreement = True

    # ── Procurement type detection ────────────────────────────────────────
    # "закупка" сама по себе не определяет тип — "закупка услуг" = services
    supply_signals = ["поставка", "приобретение",
                      "предоставление права использования", "продление лицензий"]
    service_signals = ["внедрение", "настройка", "сопровождение", "поддержка",
                       "модернизация", "миграция", "администрирование", "обследование",
                       "аудит", "проектирование", "оказание услуг", "тестирование",
                       "пентест", "разработка", "развертывание", "развёртывание",
                       "закупка услуг", "закупка работ", "услуги по", "работы по"]
    has_supply_signal = any(w in normalized_text for w in supply_signals)
    has_service_signal = any(w in normalized_text for w in service_signals)

    if has_supply_signal and not has_service_signal:
        result.supply_only = True
        result.procurement_type = "supply_only"
    elif has_supply_signal and has_service_signal:
        result.procurement_type = "mixed_supply_and_services"
    elif has_service_signal:
        result.procurement_type = "services"
    else:
        result.procurement_type = "unknown"

    # ── Исправление 2: Разделить positive_candidate ───────────────────────
    result.positive_candidate = any([
        legacy_candidate,
        rules.candidate,
        action_object.candidate,
    ])

    result.selected_for_human_review = (
        result.positive_candidate
        or result.classifier_disagreement
    )

    # ── Manual safety net (после всего) ──────────────────────────────────
    for net_word in MANUAL_SAFETY_NET:
        if net_word in normalized_text:
            result.positive_candidate = True
            result.selected_for_human_review = True
            result.decision_reasons.append("manual_safety_net")
            break

    # ── Auto-reject ───────────────────────────────────────────────────────
    # Только когда hard_stop без IT-сигнала и без action_object
    if hard_stop.candidate and hard_stop.confidence >= 0.99:
        if not result.has_strong_it_signal and not action_object.candidate and not legacy_candidate:
            result.auto_reject = True

    if result.auto_reject:
        result.selected_for_human_review = False
        result.positive_candidate = False

    # ── Decision reasons ──────────────────────────────────────────────────
    if legacy_candidate:
        result.decision_reasons.append("legacy_v1_scorer")
    if rules.candidate:
        result.decision_reasons.append("strong_profile_marker")
    if action_object.candidate:
        result.decision_reasons.append("action_object_pair")
    if result.classifier_disagreement:
        result.decision_reasons.append("classifier_disagreement")

    # ── Priority score ────────────────────────────────────────────────────
    priority = 0

    if legacy_candidate:
        # legacy даёт базовый приоритет в зависимости от v1-категории
        legacy_priority = {"core": 30, "review": 18, "lowish": 10}.get(v1_category, 5)
        priority += legacy_priority
    if rules.candidate:
        weight = rules.detail.get("total_weight", 0)
        priority += min(weight, 40)
    if action_object.candidate:
        priority += 15
    if result.has_strong_it_signal:
        priority += 10
    if result.classifier_disagreement:
        priority += 5

    # ── Исправление 5: Supply cap — только на priority, не на candidate ──
    if result.supply_only or result.procurement_type == "supply_only":
        result.review_priority_score = min(priority, 25)
    elif result.review_priority_score == 0:
        result.review_priority_score = min(priority, 100)
    else:
        result.review_priority_score = min(priority, 100)

    # Negative factors
    if hard_stop.candidate and result.has_strong_it_signal:
        result.review_priority_score = max(result.review_priority_score, 8)

    # ── Исправление 3: Очереди — P2 не по умолчанию ─────────────────────
    if result.auto_reject:
        result.review_queue = "reject"
    elif result.positive_candidate and result.review_priority_score >= 40:
        result.review_queue = "P1"
    elif result.positive_candidate or result.classifier_disagreement:
        result.review_queue = "P2"
    else:
        result.review_queue = "reject"

    # ── Исправление 5: Чистые поставки не выше P2 ────────────────────────
    if result.procurement_type == "supply_only" and result.review_queue == "P1":
        result.review_queue = "P2"
        result.review_priority_score = min(result.review_priority_score, 25)

    # ── Совместимость ────────────────────────────────────────────────────
    result.candidate_for_human_review = result.selected_for_human_review

    return result


def min_queue(a: str, b: str) -> str:
    """Возвращает очередь с меньшим приоритетом."""
    order = {"P1": 0, "P2": 1, "P3": 2, "reject": 3}
    return a if order.get(a, 99) >= order.get(b, 99) else b