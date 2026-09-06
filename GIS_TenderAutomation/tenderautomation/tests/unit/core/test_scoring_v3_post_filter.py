import pytest

from core.services.scoring_v3.models import LLMClassificationItem, V3Result
from core.services.scoring_v3.post_filter import apply_post_filter


def _result(procurement_type="services", domain="devops", verdict="core"):
    return V3Result(
        tender_id="1",
        first_pass=LLMClassificationItem(
            id="t1",
            verdict=verdict,
            procurement_type=procurement_type,
            primary_domain=domain,
        ),
        final_verdict=verdict,
        final_fit_score=90,
        final_confidence=0.9,
        queue="P1",
        priority=90,
    )


@pytest.mark.parametrize(
    "title",
    [
        "Сопровождение Directum",
        "Обслуживание кассового оборудования",
        "Обслуживание торговых объектов Монетка",
        "Обслуживание инженерных систем склада",
    ],
)
def test_known_non_targets_are_rejected(title: str) -> None:
    result = apply_post_filter(_result(), title)
    assert result.queue == "reject"
    assert result.analysis_status == "post_filter_reject"


def test_1c_infrastructure_exception_is_p2() -> None:
    result = apply_post_filter(_result(), "Миграция серверов 1С на Astra Linux")
    assert result.queue == "P2"
    assert result.analysis_status == "post_filter_1c_exception"


def test_pure_supply_reject_and_mixed_restore() -> None:
    pure = apply_post_filter(_result("supply_only"), "Поставка серверного оборудования")
    assert pure.queue == "reject"
    mixed = apply_post_filter(
        _result("supply_only", domain="devops", verdict="reject"),
        "Поставка и внедрение Kubernetes",
    )
    assert mixed.first_pass.procurement_type == "mixed"
    assert mixed.queue == "P2"


def test_infrastructure_false_negative_is_forced_to_p2() -> None:
    result = apply_post_filter(
        _result("services", domain="unknown", verdict="reject"),
        "Аудит Wi-Fi сети",
    )
    assert result.queue == "P2"
    assert result.analysis_status == "post_filter_force_p2"


def test_service_only_title_fixes_procurement_type() -> None:
    result = apply_post_filter(_result("unknown"), "Настройка и сопровождение Linux")
    assert result.first_pass.procurement_type == "services"
