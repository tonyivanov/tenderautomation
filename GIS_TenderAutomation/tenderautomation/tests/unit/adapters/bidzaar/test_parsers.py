from adapters.bidzaar.parsers import parse_detail_deadline
from core.models import DeadlineExtractionState, DeadlineLabelKind


def test_explicit_acceptance_label_is_extracted() -> None:
    outcome = parse_detail_deadline(
        "<div>Acceptance end</div><div>2026-08-01T12:30:00+03:00</div>"
    )
    assert outcome.state is DeadlineExtractionState.RESOLVED
    assert outcome.deadline is not None
    assert outcome.deadline.label_kind is DeadlineLabelKind.ACCEPTANCE_END


def test_unlabelled_date_is_not_extracted() -> None:
    assert (
        parse_detail_deadline("<time>2026-08-01T12:30:00+03:00</time>").state
        is DeadlineExtractionState.MISSING
    )
