import pytest

from core.services.scoring_v3.aggregator_v3 import (
    _assign_queue,
    _resolve_final_verdict,
    aggregate_single,
    compute_stats,
    stratify_p3,
)
from core.services.scoring_v3.models import LLMClassificationItem, V3Result


def _item(verdict="core", fit=90, confidence=0.9, **kwargs):
    return LLMClassificationItem(
        id="t1", verdict=verdict, fit_score=fit, confidence=confidence, **kwargs
    )


@pytest.mark.parametrize(
    ("first", "judge", "verdict", "disagreement"),
    [
        (_item("core"), None, "core", False),
        (_item("core"), _item("core"), "core", False),
        (_item("core"), _item("review"), "review", True),
        (_item("core"), _item("reject"), "review", True),
        (_item("review", fit=20, primary_domain="non_it"), _item("reject", confidence=0.9), "reject", True),
        (_item("review", fit=60), _item("reject"), "review", True),
    ],
)
def test_final_verdict_matrix(first, judge, verdict, disagreement) -> None:
    assert _resolve_final_verdict(first, judge) == (verdict, disagreement)


@pytest.mark.parametrize(
    ("args", "queue"),
    [
        (("reject", 0, 0.9, False, True), "reject"),
        (("review", 50, 0.5, True, False), "P2"),
        (("reject", 20, 0.2, False, False), "P2"),
        (("core", 90, 0.9, False, False), "P1"),
        (("core", 60, 0.9, False, False), "P2"),
        (("review", 90, 0.9, False, False), "P1"),
        (("unknown", 50, 0.5, False, False), "P2"),
    ],
)
def test_queue_matrix(args, queue) -> None:
    assert _assign_queue(*args)[0] == queue


def test_p1_allowlist_and_caps() -> None:
    core = _item(procurement_type="services", primary_domain="devops")
    assert aggregate_single("1", "DevOps Kubernetes", core, None).queue == "P1"
    assert aggregate_single(
        "2", "PAM access", _item(procurement_type="services", primary_domain="information_security"), None
    ).queue == "P2"
    assert aggregate_single(
        "3", "Услуги в части нежилого здания", core, None
    ).queue == "P2"
    assert aggregate_single(
        "4", "Generic service", _item(procurement_type="services", primary_domain="managed_infrastructure"), None
    ).queue == "P2"


def test_invalid_schema_and_non_it_reject() -> None:
    schema = aggregate_single("1", "Title", _item("broken"), None)
    assert schema.analysis_status == "schema_error" and schema.queue == "P2"
    rejected = aggregate_single(
        "2", "Furniture", _item("reject", fit=20, confidence=0.2, primary_domain="non_it"), None
    )
    assert rejected.queue == "reject"


def test_stratification_and_stats_cover_every_queue() -> None:
    results = [
        V3Result(tender_id="p1", queue="P1", final_verdict="core", first_pass=_item("core")),
        V3Result(tender_id="p2", queue="P2", final_verdict="review", first_pass=_item("review"), classifier_disagreement=True),
        V3Result(tender_id="r1", queue="reject", final_verdict="reject", first_pass=_item("reject"), legacy_category="core"),
        V3Result(tender_id="r2", queue="reject", final_verdict="reject", first_pass=_item("reject"), legacy_category="low"),
    ]
    sampled = stratify_p3(results)
    assert any(result.queue == "P3" for result in sampled)
    stats = compute_stats(sampled, {"total_tokens": 12})
    assert stats.total == 4
    assert stats.queue_p1 == 1 and stats.queue_p2 == 1
    assert stats.total_tokens == 12
