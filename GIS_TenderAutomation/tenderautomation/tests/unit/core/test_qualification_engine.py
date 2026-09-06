from hypothesis import given
from hypothesis import strategies as st

from core.models.tender import TenderModel
from core.services.qualification_engine import QualificationConfig, QualificationEngine, RuleDef, normalize


def tender(title: str) -> TenderModel:
    return TenderModel(id="b2bcenter_1", platform="b2bcenter", external_id="1", title=title, url="https://example.test")


def engine(*rules: RuleDef) -> QualificationEngine:
    return QualificationEngine(QualificationConfig(threshold=50, review_threshold=12, rules=list(rules)))


def positive(term: str, score: int) -> RuleDef:
    return RuleDef(id=term, phrases=[term], score=score, type="positive")


@given(st.text(max_size=200))
def test_normalize_idempotent(title: str) -> None:
    assert normalize(normalize(title)) == normalize(title)


@given(st.text(max_size=200))
def test_score_nonnegative_and_deterministic(title: str) -> None:
    subject = engine(positive("devops", 30))
    first = subject.qualify(tender(title))
    assert first.score >= 0
    assert first == subject.qualify(tender(title))


def test_thresholds_and_hard_stop() -> None:
    assert engine(positive("devops", 60)).qualify(tender("devops")).tier == "qualified"
    assert engine(positive("devops", 20)).qualify(tender("devops")).tier == "in_review"
    hard = RuleDef(id="cleaning", phrases=["уборка"], score=0, type="hard_stop")
    result = engine(positive("облако", 60), hard).qualify(tender("облако и уборка"))
    assert (result.tier, result.score, result.category) == ("filtered", 0, "hard_stop")
