"""Two-pass aggregation: primary model + judge model → final verdict and queue.

Logic:
1. First pass (primary model) classifies every tender.
2. Judge pass re-classifies when confidence is low, verdict=review,
   primary disagrees with legacy, procurement_type=mixed, or risk flags present.
3. Combine first + judge → final verdict, compute disagreement, assign queue.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from . import config, models
import logging

logger = logging.getLogger(__name__)

# ── v3.2 domain lists ───────────────────────────────────────────────────
P1_ALLOWED_DOMAINS = frozenset({
    "devops", "linux_administration", "containers", "virtualization",
    "infrastructure_audit", "infrastructure_migration", "infrastructure_modernization",
    "managed_infrastructure", "backup", "storage", "databases", "information_security",
})

NON_IT_DOMAINS = frozenset({
    "non_it", "facilities", "web_and_marketing", "application_software",
    "office_it", "supply",
})


@dataclass
class AggregationStats:
    total: int = 0
    first_pass_core: int = 0
    first_pass_review: int = 0
    first_pass_reject: int = 0
    sent_to_judge: int = 0
    judge_core: int = 0
    judge_review: int = 0
    judge_reject: int = 0
    disagreements: int = 0
    final_core: int = 0
    final_review: int = 0
    final_reject: int = 0
    queue_p1: int = 0
    queue_p2: int = 0
    queue_p3: int = 0
    queue_reject: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


def _resolve_final_verdict(fp: models.LLMClassificationItem, jp: models.LLMClassificationItem | None) -> tuple[str, bool]:
    """Determine final verdict and whether classifiers disagreed.

    Returns (verdict, disagreement_flag).
    """
    if jp is None:
        return fp.verdict, False

    # Agreement: both same verdict → use that verdict
    if fp.verdict == jp.verdict:
        return fp.verdict, False

    # Disagreement detected
    # If one says core and other says review → review (safety: send to human)
    if {fp.verdict, jp.verdict} == {"core", "review"}:
        return "review", True

    # If one says core and other says reject → review (escalate for safety)
    if {fp.verdict, jp.verdict} == {"core", "reject"}:
        return "review", True

    # If one says review and other says reject → ASYMMETRIC:
    # Weak review (fit<40, no IT domain) + confident judge reject → reject
    # Otherwise → review (safety)
    if {fp.verdict, jp.verdict} == {"review", "reject"}:
        review_item = fp if fp.verdict == "review" else jp
        reject_item = jp if fp.verdict == "review" else fp
        if (review_item.fit_score < 40
            and reject_item.confidence >= 0.80
            and review_item.primary_domain in NON_IT_DOMAINS):
            return "reject", True
        return "review", True

    # Fallback: primary verdict, flagged as disagreement
    return fp.verdict, True


def _assign_queue(
    verdict: str,
    fit_score: int,
    confidence: float,
    disagreement: bool,
    both_reject: bool = False,
    legacy_category: str = "",
) -> tuple[str, int]:
    """Assign queue (P1/P2/P3/reject) and priority score.

    P1: core/review with fit≥75, conf≥0.82, no disagreement
    P2: review by default, core with lower confidence, any conflict
    Reject: (a) both primary+judge independently said reject, no disagreement
            (b) single-pass reject with conf≥0.85
    P3: stratified 5% sample from reject queue
    Priority = 0 for reject/P3 queues.
    """
    if verdict == "reject" and both_reject and not disagreement:
        return "reject", 0

    if disagreement:
        return "P2", _review_priority(fit_score, confidence)

    if verdict == "reject":
        if confidence >= config.REJECT_MIN_CONFIDENCE:
            return "reject", 0
        else:
            return "P2", _review_priority(fit_score, confidence)

    if verdict == "core":
        if fit_score >= config.P1_MIN_FIT_SCORE and confidence >= config.P1_MIN_CONFIDENCE:
            return "P1", _review_priority(fit_score, confidence)
        else:
            return "P2", _review_priority(fit_score, confidence)

    if verdict == "review":
        if fit_score >= config.P1_MIN_FIT_SCORE and confidence >= config.P1_MIN_CONFIDENCE:
            return "P1", _review_priority(fit_score, confidence)
        else:
            return "P2", _review_priority(fit_score, confidence)

    return "P2", _review_priority(fit_score, confidence)


def _review_priority(fit_score: int, confidence: float) -> int:
    """Compute priority for review queues (P1/P2) only.

    Range roughly 25-100. Higher = more urgent.
    Reject/P3 get priority=0.
    """
    return int(fit_score * 0.6 + confidence * 100 * 0.4)


def _compute_final_confidence(fp: models.LLMClassificationItem, jp: models.LLMClassificationItem | None) -> float:
    """Blend confidences. If judge exists, take average; otherwise primary's."""
    if jp is None:
        return fp.confidence
    return round((fp.confidence + jp.confidence) / 2, 4)


def _compute_final_fit(fp: models.LLMClassificationItem, jp: models.LLMClassificationItem | None) -> int:
    """Blend fit scores."""
    if jp is None:
        return fp.fit_score
    return int((fp.fit_score + jp.fit_score) / 2)


def aggregate_single(
    tender_id: str,
    title: str,
    first_pass: models.LLMClassificationItem,
    judge_pass: models.LLMClassificationItem | None,
    legacy_tier: str = "",
    legacy_score: int = 0,
    legacy_category: str = "",
    cache_hit: bool = False,
) -> models.V3Result:
    """Aggregate first pass + optional judge pass into final V3Result."""
    verdict, disagreed = _resolve_final_verdict(first_pass, judge_pass)
    final_conf = _compute_final_confidence(first_pass, judge_pass)
    final_fit = _compute_final_fit(first_pass, judge_pass)

    # Both models independently said reject with no disagreement → true reject
    both_reject = (
        judge_pass is not None
        and first_pass.verdict == "reject"
        and judge_pass.verdict == "reject"
        and not disagreed
    )

    queue, prio = _assign_queue(verdict, final_fit, final_conf, disagreed, both_reject, legacy_category)

    # ── v3.2: P1 allowlist enforcement ────────────────────────────────
    if queue == "P1":
        domain = str(first_pass.primary_domain) if first_pass else "unknown"
        proc_type = str(first_pass.procurement_type) if first_pass else "unknown"
        risk_flags = first_pass.risk_flags if first_pass else []
        risk_set = set(risk_flags)

        # P1 requires core verdict, services only, allowed domain, no risk flags
        if verdict != "core":
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif proc_type != "services":
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif domain not in P1_ALLOWED_DOMAINS:
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif risk_set:
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif final_fit < 85:
            queue, prio = "P2", _review_priority(final_fit, final_conf)

    # ── v3.2: P2 caps — mixed/vendor/ambiguous/insufficient → max P2 ──
    if queue == "P1":
        risk_flags = first_pass.risk_flags if first_pass else []
        if first_pass and first_pass.procurement_type == "mixed":
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif "vendor_authorization_possible" in risk_flags:
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif "insufficient_context" in risk_flags:
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif "ambiguous_title" in risk_flags:
            queue, prio = "P2", _review_priority(final_fit, final_conf)

    # ── v3.2.3.4: P1 caps — mixed/vendor/unknown/managed_no_obj → max P2
    if queue == "P1":
        risk_flags = first_pass.risk_flags if first_pass else []
        domain = str(first_pass.primary_domain) if first_pass else "unknown"
        proc_type = str(first_pass.procurement_type) if first_pass else "unknown"
        if proc_type == "mixed":
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif domain == "unknown":
            queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif domain == "managed_infrastructure":
            # Generic managed infrastructure without explicit IT object → P2
            title_low = title.lower()
            has_explicit_obj = any(w in title_low for w in {
                "сервер", "схд", "сеть", "cisco", "juniper", "hpe", "dell",
                "netapp", "vmware", "oracle", "kubernetes", "docker", "devops",
                "ci/cd", "резервн", "сетевое оборуд", "маршрутизатор",
                "коммутатор", "межсетев", "баз данных",
            })
            if not has_explicit_obj:
                queue, prio = "P2", _review_priority(final_fit, final_conf)
        elif domain == "information_security":
            # Security vendor tools (PAM, specific products) → P2, not P1
            vendor_tool = any(w in title.lower() for w in {
                "pam", "privileged access", "управление доступом",
            })
            if vendor_tool:
                queue, prio = "P2", _review_priority(final_fit, final_conf)

    # ── v3.2.3.5: Building-related caps → max P2 ──────────────────────
    if queue == "P1":
        title_low = title.lower()
        if any(w in title_low for w in {"нежилого здания", "нежилом здании", "в части здания", "части нежилого здания", "инженерной инфраструктуры"}):
            queue, prio = "P2", _review_priority(final_fit, final_conf)

    # ── v3.2: Non-IT reject → reject regardless of confidence ─────────
    if verdict == "reject" and queue == "P2":
        domain = str(first_pass.primary_domain) if first_pass else "unknown"
        if domain in NON_IT_DOMAINS:
            queue, prio = "reject", 0

    # ── v3.2: Schema validation ───────────────────────────────────────
    if str(verdict) not in ("core", "review", "reject"):
        logger.warning(f"Invalid verdict '{verdict}' for {tender_id}, marking as schema_error")
        result = models.V3Result(
            tender_id=tender_id,
            original_title=title,
            cache_hit=cache_hit,
            analysis_status="schema_error",
            first_pass=first_pass,
            primary_model="",
            judge_pass=judge_pass,
            judge_model="",
            final_verdict="review",
            final_fit_score=40,
            final_confidence=0.30,
            classifier_disagreement=disagreed,
            queue="P2",
            priority=20,
            legacy_tier=legacy_tier,
            legacy_score=legacy_score,
            legacy_category=legacy_category,
        )
        return result

    result = models.V3Result(
        tender_id=tender_id,
        original_title=title,
        cache_hit=cache_hit,
        analysis_status="completed",
        first_pass=first_pass,
        primary_model="",
        judge_pass=judge_pass,
        judge_model="",
        final_verdict=verdict,
        final_fit_score=final_fit,
        final_confidence=final_conf,
        classifier_disagreement=disagreed,
        queue=queue,
        priority=prio,
        legacy_tier=legacy_tier,
        legacy_score=legacy_score,
        legacy_category=legacy_category,
    )
    # v3.2.3.1: Assert reject+P2 should never exist
    if queue in ("P1", "P2") and verdict == "reject":
        logger.error(f"INVARIANT VIOLATION: reject verdict in {queue} for {tender_id}, fixing")
        result = models.V3Result(
            tender_id=tender_id, original_title=title, cache_hit=cache_hit,
            analysis_status="invariant_fix",
            first_pass=first_pass, primary_model="",
            judge_pass=judge_pass, judge_model="",
            final_verdict="review", final_fit_score=40, final_confidence=0.40,
            classifier_disagreement=disagreed,
            queue="P2", priority=30,
            legacy_tier=legacy_tier, legacy_score=legacy_score, legacy_category=legacy_category,
        )
        result.pre_filter_verdict = verdict
        result.pre_filter_queue = queue
        return result

    # v3.2.3: Save pre-filter state for audit trail
    result.pre_filter_verdict = verdict
    result.pre_filter_queue = queue
    return result


# Fixed seed is required for reproducible quality-control sampling, not security.
_P3_RNG = random.Random(42)  # nosec B311

def stratify_p3(results: list[models.V3Result]) -> list[models.V3Result]:
    """Promote a stratified 5% sample from reject queue to P3.

    Stratification: sample evenly across legacy categories (core/review/lowish/hard_stop)
    to ensure all categories are represented in P3.
    """
    rejects = [r for r in results if r.queue == "reject"]
    if not rejects:
        return results

    target_count = max(1, int(len(rejects) * config.P3_SAMPLE_RATE))

    # Group by legacy category for stratified sampling
    by_cat: dict[str, list[models.V3Result]] = {}
    for r in rejects:
        cat = r.legacy_category or "unknown"
        by_cat.setdefault(cat, []).append(r)

    # Allocate slots proportionally
    total_rejects = len(rejects)
    selected: set[str] = set()
    for cat, group in by_cat.items():
        group_slots = max(1, int(target_count * len(group) / total_rejects))
        sample = _P3_RNG.sample(group, min(group_slots, len(group)))
        for r in sample:
            selected.add(r.tender_id)

    # If we haven't reached target, fill from any remaining
    remaining_target = target_count - len(selected)
    if remaining_target > 0:
        remaining = [r for r in rejects if r.tender_id not in selected]
        extra = _P3_RNG.sample(remaining, min(remaining_target, len(remaining)))
        for r in extra:
            selected.add(r.tender_id)

    # Apply queue change
    for r in results:
        if r.tender_id in selected:
            r.queue = "P3"

    return results


def compute_stats(
    results: list[models.V3Result],
    stats_override: dict[str, int] | None = None,
) -> AggregationStats:
    """Compute aggregation statistics from results."""
    s = AggregationStats()
    s.total = len(results)

    for r in results:
        # First pass — use string comparison, not enum
        fp_v = str(r.first_pass.verdict) if r.first_pass else "error"
        if fp_v == "core":
            s.first_pass_core += 1
        elif fp_v == "review":
            s.first_pass_review += 1
        else:
            s.first_pass_reject += 1

        # Judge pass
        if r.judge_pass is not None:
            s.sent_to_judge += 1
            jp_v = str(r.judge_pass.verdict)
            if jp_v == "core":
                s.judge_core += 1
            elif jp_v == "review":
                s.judge_review += 1
            else:
                s.judge_reject += 1

        # Final — validate and count
        fv = str(r.final_verdict)
        if fv == "core":
            s.final_core += 1
        elif fv == "review":
            s.final_review += 1
        else:
            s.final_reject += 1

        if r.classifier_disagreement:
            s.disagreements += 1

        # Queue
        if r.queue == "P1":
            s.queue_p1 += 1
        elif r.queue == "P2":
            s.queue_p2 += 1
        elif r.queue == "P3":
            s.queue_p3 += 1
        else:
            s.queue_reject += 1

        s.total_tokens += r.input_tokens + r.output_tokens
        s.total_cost += r.estimated_cost

    if stats_override:
        for k, v in stats_override.items():
            setattr(s, k, v)

    return s
