from unittest.mock import Mock

import pytest

from core.services.scoring_v2.aggregator import aggregate, min_queue
from core.services.scoring_v2.models import ClassifierDecision
from core.services.scoring_v2.pipeline import ScoringV2Pipeline


def _decision(candidate: bool = False, confidence: float = 0.0, **detail):
    return ClassifierDecision(candidate, confidence, detail=detail)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Внедрение Kubernetes и DevOps", "P1"),
        ("Комплексная уборка помещений", "reject"),
        ("Поставка серверного оборудования", "reject"),
        ("Аудит IT инфраструктуры", "P2"),
    ],
)
def test_pipeline_business_queues(title: str, expected: str) -> None:
    result = ScoringV2Pipeline(seed=99).qualify("id", title)
    assert result.review_queue == expected


def test_legacy_candidate_is_kept_for_review() -> None:
    result = ScoringV2Pipeline().qualify(
        "id", "Неопределенный предмет", v1_tier="qualified", v1_category="review"
    )
    assert result.positive_candidate
    assert "legacy_v1_scorer" in result.decision_reasons


def test_batch_preserves_input_order() -> None:
    rows = [{"id": "1", "title": "аудит серверов"}, {"id": "2", "title": "клининг"}]
    assert [r.tender_id for r in ScoringV2Pipeline().qualify_batch(rows)] == ["1", "2"]


def test_p3_sampling_is_deterministic_and_deduplicated() -> None:
    subject = ScoringV2Pipeline()
    subject._rng = Mock(random=Mock(return_value=0.0))
    first = subject.qualify("1", "комплексная уборка помещений")
    second = subject.qualify("2", "комплексная уборка помещений")
    assert first.review_queue == "P3"
    assert first.p3_control_sample
    assert second.review_queue == "reject"


def test_aggregate_disagreement_and_auto_reject_paths() -> None:
    conflict = aggregate(
        "1", "title", "аудит kubernetes", _decision(True, 0.99),
        _decision(True, 0.9, total_weight=25), _decision(), _decision(), _decision()
    )
    assert conflict.classifier_disagreement
    assert conflict.review_queue == "P1"

    rejected = aggregate(
        "2", "title", "клининг", _decision(True, 0.99),
        _decision(), _decision(), _decision(), _decision()
    )
    assert rejected.auto_reject and rejected.review_queue == "reject"


def test_supply_priority_is_capped_and_queue_order_helper() -> None:
    supplied = aggregate(
        "1", "title", "поставка kubernetes", _decision(),
        _decision(True, 1.0, total_weight=80), _decision(True, 0.85),
        _decision(), _decision(), v1_category="core"
    )
    assert supplied.procurement_type == "supply_only"
    assert supplied.review_priority_score <= 25
    assert supplied.review_queue == "P2"
    assert min_queue("P1", "reject") == "reject"
