from core.services.scoring_v2.action_object_gate import apply_action_object
from core.services.scoring_v2.entity_gate import (
    apply_entity_gate,
    detect_entity_actions,
    detect_entity_it_objects,
    detect_it_context,
    detect_negative_contexts,
    has_strong_it_object,
)
from core.services.scoring_v2.hard_stop import apply_hard_stop
from core.services.scoring_v2.normalizer import (
    expand_abbreviations,
    normalize,
    strip_prefixes,
)
from core.services.scoring_v2.rules_gate import apply_rules
from core.services.scoring_v2.strong_object_service_gate import (
    apply_strong_object_service_gate,
)


def test_normalization_expansion_and_prefix_removal() -> None:
    normalized = normalize("Тендер №42: Аудит ИТ-инфраструктуры / ЦОД")
    assert "ё" not in normalized
    expanded = expand_abbreviations(normalized)
    assert "центр обработки данных" in expanded
    assert strip_prefixes(expanded).startswith("аудит")
    assert expand_abbreviations("уборка помещений") == "уборка помещений"


def test_hard_stop_and_rules_have_positive_and_negative_paths() -> None:
    assert apply_hard_stop("комплексная уборка помещений").candidate
    assert not apply_hard_stop("аудит серверной инфраструктуры").candidate
    rules = apply_rules("внедрение kubernetes и devops")
    assert rules.candidate and rules.detail["total_weight"] >= 25
    assert not apply_rules("закупка мебели").candidate


def test_action_object_requires_nearby_pair() -> None:
    assert apply_action_object("аудит серверной инфраструктуры").candidate
    separated = "аудит " + ("x" * 250) + " сервер"
    assert not apply_action_object(separated, max_distance=200).candidate
    assert not apply_action_object("аудит бухгалтерской отчетности").candidate


def test_entity_detectors_and_negative_context_gate() -> None:
    text = "аудит и модернизация серверной инфраструктуры kubernetes"
    actions = detect_entity_actions(text)
    objects = detect_entity_it_objects(text)
    assert {"audit", "modernization"} <= actions
    assert {"server", "containers"} <= objects
    assert detect_it_context(text, objects)
    assert has_strong_it_object(objects)
    assert apply_entity_gate(text).candidate

    negative = "обслуживание инженерных сетей здания"
    assert detect_negative_contexts(negative)
    assert apply_entity_gate(negative).reason == "negative_context_blocked"
    assert apply_entity_gate("оказание консультационных услуг").reason == "no_entity_match"


def test_strong_object_service_gate_requires_both_parts() -> None:
    assert apply_strong_object_service_gate("поддержка система хранения данных").candidate
    assert not apply_strong_object_service_gate("система хранения данных").candidate
