"""Qualification Engine v2 — context-aware, rules-driven, explainable."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.models import TenderModel


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    phrase: str
    score: int
    type: str  # positive / negative / hard_stop


@dataclass
class RuleDef:
    id: str
    phrases: list[str]
    score: int
    type: str  # positive / negative / hard_stop
    strong_marker: str = "none"  # core / review / weak / none
    minimum_category: str = "low"  # core / review / lowish / low
    exceptions: dict[str, list[str]] = field(default_factory=dict)
    forbidden_context: list[str] = field(default_factory=list)
    required_context: list[str] = field(default_factory=list)
    match_type: str = "contains"  # "contains" | "regex"


@dataclass
class QualificationConfig:
    threshold: int
    review_threshold: int
    rules: list[RuleDef]


@dataclass
class QualificationResult:
    tier: str
    score: int
    category: str
    positive_matches: list[RuleMatch]
    negative_matches: list[RuleMatch]
    hard_stop_match: RuleMatch | None
    strong_marker_triggered: bool
    explanation: str


# ── Normalization ─────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Normalize text for matching — aggressive, handles ИТ/IT, hyphens, ё/е."""
    t = text.lower()
    t = t.replace("ё", "е")
    # Normalize ИТ/IT variants — convert all to "it"
    t = re.sub(r"\bит\b", "it", t)
    t = re.sub(r"\bит-", "it ", t)
    t = re.sub(r"\bит\s", "it ", t)
    t = re.sub(r"\bit\b", "it", t)
    t = re.sub(r"\bit-", "it ", t)
    t = re.sub(r"\bit\s", "it ", t)
    # Normalize hyphenation — all dashes/typo-dashes → space
    t = t.replace("-", " ").replace("—", " ").replace("–", " ")
    t = t.replace("\u00a0", " ")  # non-breaking space
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ── Rule loading ──────────────────────────────────────────────────────────

def load_config(filters_dir: Path) -> QualificationConfig:
    config_path = filters_dir / "config.yaml"
    rules_path = filters_dir / "rules.yaml"

    with open(config_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    threshold = config_data["qualification"]["threshold"]
    review_threshold = config_data["qualification"].get("review_threshold", 12)

    with open(rules_path, encoding="utf-8") as f:
        rules_data = yaml.safe_load(f)

    rules = []
    for r in rules_data.get("rules", []):
        rules.append(RuleDef(
            id=r["id"],
            phrases=r.get("phrases", []),
            score=r.get("score", 0),
            type=r.get("type", "positive"),
            strong_marker=r.get("strong_marker", "none"),
            minimum_category=r.get("minimum_category", "low"),
            exceptions=r.get("exceptions", {}),
            forbidden_context=r.get("forbidden_context", []),
            required_context=r.get("required_context", []),
            match_type=r.get("match_type", "contains"),
        ))

    return QualificationConfig(
        threshold=threshold,
        review_threshold=review_threshold,
        rules=rules,
    )


# ── Matching helpers ──────────────────────────────────────────────────────

def _phrase_matches(phrase: str, text: str, match_type: str = "contains") -> bool:
    """Check if phrase matches text (contains or regex)."""
    if match_type == "regex":
        return bool(re.search(phrase, text, re.IGNORECASE))
    return phrase in text


def _check_exceptions(rule: RuleDef, text: str) -> bool:
    """Return True if any exception condition is met (rule should NOT apply)."""
    if not rule.exceptions:
        return False
    any_words = rule.exceptions.get("any", [])
    for w in any_words:
        if w in text:
            return True
    return False


def _check_forbidden_context(rule: RuleDef, text: str) -> bool:
    """Return True if forbidden context is present (rule should NOT apply)."""
    for w in rule.forbidden_context:
        if w in text:
            return True
    return False


def _check_required_context(rule: RuleDef, text: str) -> bool:
    """Return True if required context is present (rule SHOULD apply)."""
    if not rule.required_context:
        return True
    for w in rule.required_context:
        if w in text:
            return True
    return False


CATEGORY_RANK = {"low": 0, "lowish": 1, "review": 2, "core": 3}


def _max_category(a: str, b: str) -> str:
    return a if CATEGORY_RANK.get(a, 0) >= CATEGORY_RANK.get(b, 0) else b


# ── Qualification Engine ──────────────────────────────────────────────────

class QualificationEngine:
    def __init__(self, config: QualificationConfig) -> None:
        self._config = config
        # Separate rules by type for fast lookup
        self._hard_stops = [r for r in config.rules if r.type == "hard_stop"]
        self._positive = [r for r in config.rules if r.type == "positive"]
        self._negative = [r for r in config.rules if r.type == "negative"]

    @classmethod
    def from_filters_dir(cls, filters_dir: Path) -> "QualificationEngine":
        return cls(load_config(filters_dir))

    def qualify(self, tender: TenderModel) -> QualificationResult:
        """Run full qualification pipeline."""
        original = tender.title
        text = normalize(original)

        # Stage 0: Priority hard-stop — office equipment (never overridable, exact phrases only)
        office_exact = ["офисная техника", "офисной техники", "офисной техникой",
                        "офисную технику", "офисной технике"]
        if any(oe in text for oe in office_exact):
            return QualificationResult(
                tier="filtered", score=0, category="hard_stop",
                positive_matches=[], negative_matches=[],
                hard_stop_match=RuleMatch(
                    rule_id="office_equipment", phrase="офисная техника",
                    score=0, type="hard_stop"
                ),
                strong_marker_triggered=False,
                explanation="Hard-stop: правило office_equipment (офисная техника)",
            )

        # Stage 1: Hard stop check
        hard_stop_match = None
        for rule in self._hard_stops:
            if _check_exceptions(rule, text):
                continue
            for phrase in rule.phrases:
                if _phrase_matches(phrase, text, rule.match_type):
                    if _check_forbidden_context(rule, text):
                        continue
                    hard_stop_match = RuleMatch(
                        rule_id=rule.id, phrase=phrase,
                        score=rule.score, type="hard_stop"
                    )
                    break
            if hard_stop_match:
                break

        # Stage 2: Strong marker detection (even if hard-stopped, find markers)
        strong_marker_triggered = False
        for rule in self._positive:
            if rule.strong_marker in ("core", "review"):
                if _check_exceptions(rule, text):
                    continue
                if _check_forbidden_context(rule, text):
                    continue
                if not _check_required_context(rule, text):
                    continue
                for phrase in rule.phrases:
                    if _phrase_matches(phrase, text, rule.match_type):
                        strong_marker_triggered = True
                        break
                if strong_marker_triggered:
                    break

        # Stage 2.5: Pure supply check — downgrade strong marker + cap score at 2
        supply_phrases = ["поставка программного обеспечения", "поставка по", "предоставление права использования",
                          "продление лицензий", "поставка лицензий", "приобретение", "закупка",
                          "поставка оборудования", "поставка сервер"]
        has_pure_supply = any(_phrase_matches(p, text) for p in supply_phrases)
        service_words = ["внедрение", "миграция", "настройка", "сопровождение", "поддержка",
                         "проектирование", "обследование", "модернизация", "интеграция",
                         "администрирование", "оказание услуг"]
        has_service_words = any(w in text for w in service_words)
        if has_pure_supply and not has_service_words:
            strong_marker_triggered = False  # override — pure supply is never core
            supply_capped = True
        else:
            supply_capped = False

        # Stage 3: Strong marker override — unblock hard stop
        if hard_stop_match and strong_marker_triggered:
            # Check if hard-stopped rule itself has exceptions matching
            hard_rule = next((r for r in self._hard_stops if r.id == hard_stop_match.rule_id), None)
            if hard_rule and _check_exceptions(hard_rule, text):
                hard_stop_match = None  # exception triggered → unblock

        # If still hard-stopped
        if hard_stop_match:
            return QualificationResult(
                tier="filtered", score=0, category="hard_stop",
                positive_matches=[], negative_matches=[],
                hard_stop_match=hard_stop_match,
                strong_marker_triggered=strong_marker_triggered,
                explanation=f"Hard-stop: правило {hard_stop_match.rule_id} ({hard_stop_match.phrase})",
            )

        # Stage 4: Positive scoring
        positive_matches: list[RuleMatch] = []
        total_score = 0
        for rule in self._positive:
            if _check_exceptions(rule, text):
                continue
            if _check_forbidden_context(rule, text):
                continue
            if not _check_required_context(rule, text):
                continue
            match_found = False
            for phrase in rule.phrases:
                if _phrase_matches(phrase, text, rule.match_type):
                    positive_matches.append(RuleMatch(
                        rule_id=rule.id, phrase=phrase,
                        score=rule.score, type="positive"
                    ))
                    total_score += rule.score
                    match_found = True
                    break  # one match per rule

        # Stage 5: Negative scoring
        negative_matches: list[RuleMatch] = []
        for rule in self._negative:
            if _check_exceptions(rule, text):
                continue
            if _check_forbidden_context(rule, text):
                continue
            match_found = False
            for phrase in rule.phrases:
                if _phrase_matches(phrase, text):
                    # For negative rules with exceptions: check if exception words present
                    if rule.exceptions:
                        any_exc = rule.exceptions.get("any", [])
                        if any(w in text for w in any_exc):
                            continue  # exception overrides negative rule
                    negative_matches.append(RuleMatch(
                        rule_id=rule.id, phrase=phrase,
                        score=rule.score, type="negative"
                    ))
                    total_score += rule.score
                    match_found = True
                    break

        total_score = max(total_score, 0)

        # Default category before caps
        category = "low"

        # Stage 5.5: Supply cap — cap at 2 for pure supply (always set tier)
        if supply_capped:
            total_score = min(total_score, 2)
            category = "low"
            tier = "filtered"

        # Stage 5.6: Vendor hardware support cap — cap at 17, max category review
        vendor_hw_keywords = ["huawei", "netapp", "hpe", "cisco", "oracle"]
        has_vendor_hw = any(kw in text for kw in vendor_hw_keywords)
        vendor_capped = False
        if has_vendor_hw and not supply_capped:
            if total_score > 17:
                total_score = 17
                category = "review"
                tier = "in_review"
                vendor_capped = True

        # Stage 6: Determine tier and category (if not already set by caps)
        if not vendor_capped and not supply_capped:
            if total_score >= self._config.threshold:
                tier = "qualified"
                category = "core"
            elif total_score >= self._config.review_threshold:
                tier = "in_review"
                category = "review"
            elif total_score >= 6:
                tier = "filtered"
                category = "lowish"
            else:
                tier = "filtered"
                category = "low"

        # Stage 6.5: Safety net — pentest minimum score (after caps, cannot be overridden)
        if "пентест" in text:
            total_score = max(total_score, 15)
            category = _max_category(category, "review")
            tier = "in_review" if category == "review" and _max_category(category, "review") == "review" else tier
        if ("пентест" in text or "аудит" in text) and re.search(r"информационн.{0,10}инфраструктур", text):
            total_score = max(total_score, 20)
            category = _max_category(category, "core")
            tier = "qualified"

        # Stage 7: Strong marker minimum category override
        if strong_marker_triggered:
            min_cat = "low"
            for rule in self._positive:
                if rule.strong_marker in ("core", "review"):
                    if any(m.rule_id == rule.id for m in positive_matches):
                        if rule.minimum_category == "core" and category in ("review", "lowish", "low"):
                            category = "core"
                            tier = "qualified"
                        elif rule.minimum_category == "review" and category in ("lowish", "low"):
                            category = "review"
                            tier = "in_review"
                        break

        # Stage 8: Build explanation
        explanation_parts = []
        if positive_matches:
            top = sorted(positive_matches, key=lambda m: -m.score)[:3]
            explanation_parts.append(f"Найдены фразы: {', '.join(m.phrase for m in top)}")
        if negative_matches:
            explanation_parts.append(f"Отрицательный контекст: {', '.join(m.phrase for m in negative_matches)}")
        if strong_marker_triggered:
            explanation_parts.append("Сильный маркер активирован")
        if not explanation_parts:
            explanation_parts.append("Значимых совпадений не найдено")

        return QualificationResult(
            tier=tier, score=total_score, category=category,
            positive_matches=positive_matches, negative_matches=negative_matches,
            hard_stop_match=None,
            strong_marker_triggered=strong_marker_triggered,
            explanation="; ".join(explanation_parts),
        )

    # Backward-compatible interface
    def qualify_legacy(self, tender: TenderModel) -> tuple[str, int, list[str], str]:
        r = self.qualify(tender)
        matched = [m.phrase for m in r.positive_matches]
        reason = r.hard_stop_match.phrase if r.hard_stop_match else ""
        return r.tier, r.score, matched, reason