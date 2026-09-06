"""Scoring v2 Pipeline — v2.4 (entity gate, strong object+service, semantic core)."""
from __future__ import annotations

import random
from typing import Any

from .action_object_gate import apply_action_object
from .aggregator import aggregate
from .entity_gate import apply_entity_gate
from .hard_stop import apply_hard_stop
from .models import CandidateResult
from .normalizer import expand_abbreviations, normalize, strip_prefixes
from .rules_gate import apply_rules
from .strong_object_service_gate import apply_strong_object_service_gate


IT_INDICATOR_WORDS = [
    "сервер", "сет", "linux", "виртуализац", "облак", "цод", "резервн",
    "безопасност", "аудит", "пентест", "инфраструктур", "мониторинг",
    "миграц", "разработк", "контейнер", "kubernetes", "docker", "devops",
    "схд", "ceph", "veeam", "vmware", "postgres", "oracle", "cisco",
    "маршрутизатор", "коммутатор", "межсетев", "ddos", "waf", "pam",
]


class ScoringV2Pipeline:
    def __init__(self, seed: int = 42) -> None:
        # Deterministic quality-control sampling; no security decision uses this RNG.
        self._rng = random.Random(seed)  # nosec B311
        self._seen_p3_titles: set[str] = set()
        self._p3_category_counts: dict[str, int] = {}

    def _has_it_indicators(self, text: str) -> bool:
        return any(w in text for w in IT_INDICATOR_WORDS)

    def _is_exact_hard_stop(self, text: str) -> bool:
        obvious = ["клининг", "комплексная уборка", "уборка помещений",
                   "комплексное питание", "доставка обедов",
                   "создание сайта", "разработка сайта", "поддержка сайта",
                   "smm сопровождение", "рекламная кампания", "pr продвижение",
                   "пассажирские перевозки", "грузовые перевозки",
                   "специальная оценка условий труда"]
        return any(w in text for w in obvious)

    def _get_p3_sample_rate(self, result: CandidateResult, text: str) -> float:
        if result.review_queue != "reject":
            return 0.0

        has_it = self._has_it_indicators(text)
        actions = result.entity_gate.detail.get("all_actions", [])
        objects = result.entity_gate.detail.get("all_objects", [])
        has_action = bool(actions)
        has_object = bool(objects)

        # ТЗ §18: стратифицированная выборка
        if self._is_exact_hard_stop(text):
            return 0.10  # 10% точных hard-stop
        if result.procurement_type == "mixed_supply_and_services" and not result.positive_candidate:
            return 0.15  # 15% mixed supply без candidate
        if has_it and not has_action and not has_object:
            return 0.20  # 20% IT-слова без действий и объектов
        if has_action and not has_object:
            return 0.15
        if has_object and not has_action:
            return 0.15
        if has_it:
            return 0.20
        return 0.03  # ~15% случайные

    def _check_p3_duplicate(self, text: str, category: str) -> bool:
        """Limit P3 to max 3 near-duplicates per category."""
        key = category + "::" + text[:80]
        if key in self._seen_p3_titles:
            return False
        cat_count = self._p3_category_counts.get(category, 0)
        if cat_count >= 3:
            return False
        self._p3_category_counts[category] = cat_count + 1
        self._seen_p3_titles.add(key)
        return True

    def qualify(
        self,
        tender_id: str,
        title: str,
        v1_tier: str = "",
        v1_score: int = 0,
        v1_category: str = "",
    ) -> CandidateResult:
        text = normalize(title)
        expanded = expand_abbreviations(text)
        semantic_core = strip_prefixes(expanded)

        hard_stop = apply_hard_stop(text)
        rules = apply_rules(semantic_core)
        action_object = apply_action_object(semantic_core)
        entity_gate = apply_entity_gate(semantic_core)
        strong_object_service = apply_strong_object_service_gate(semantic_core)

        result = aggregate(
            tender_id=tender_id, original_title=title, normalized_text=text,
            hard_stop=hard_stop, rules=rules, action_object=action_object,
            entity_gate=entity_gate, strong_object_service=strong_object_service,
            semantic_core_title=semantic_core,
            v1_tier=v1_tier, v1_score=v1_score, v1_category=v1_category,
        )

        # P3 — stratified sample
        if result.review_queue == "reject" and not result.positive_candidate:
            sample_rate = self._get_p3_sample_rate(result, text)
            if self._rng.random() < sample_rate:
                cat = "hard_stop" if self._is_exact_hard_stop(text) else "general"
                if self._check_p3_duplicate(text, cat):
                    result.review_queue = "P3"
                    result.selected_for_human_review = True
                    result.candidate_for_human_review = True
                    result.p3_control_sample = True
                    result.decision_reasons.append("p3_control_sample")

        return result

    def qualify_batch(self, tenders: list[dict[str, Any]]) -> list[CandidateResult]:
        results: list[CandidateResult] = []
        for t in tenders:
            result = self.qualify(
                tender_id=t.get("id", ""), title=t.get("title", ""),
                v1_tier=t.get("v1_tier", ""), v1_score=t.get("v1_score", 0),
                v1_category=t.get("v1_category", ""),
            )
            results.append(result)
        return results
