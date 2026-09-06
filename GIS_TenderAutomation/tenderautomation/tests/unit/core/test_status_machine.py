"""Tests for TenderStatus state machine — PBT: only valid transitions allowed."""
import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.models.tender import TenderStatus, _VALID_TRANSITIONS


ALL_STATUSES = list(TenderStatus)


class TestValidTransitions:
    def test_pending_to_qualified(self):
        assert TenderStatus.PENDING.can_transition_to(TenderStatus.QUALIFIED)

    def test_pending_to_filtered(self):
        assert TenderStatus.PENDING.can_transition_to(TenderStatus.FILTERED)

    def test_qualified_to_in_review(self):
        assert TenderStatus.QUALIFIED.can_transition_to(TenderStatus.IN_REVIEW)

    def test_in_review_to_taken(self):
        assert TenderStatus.IN_REVIEW.can_transition_to(TenderStatus.TAKEN)

    def test_in_review_to_rejected(self):
        assert TenderStatus.IN_REVIEW.can_transition_to(TenderStatus.REJECTED)

    def test_in_review_to_deferred(self):
        assert TenderStatus.IN_REVIEW.can_transition_to(TenderStatus.DEFERRED)

    def test_deferred_to_in_review(self):
        assert TenderStatus.DEFERRED.can_transition_to(TenderStatus.IN_REVIEW)


class TestInvalidTransitions:
    def test_filtered_cannot_go_to_qualified_directly(self):
        assert not TenderStatus.FILTERED.can_transition_to(TenderStatus.QUALIFIED)

    def test_taken_has_no_transitions(self):
        for target in ALL_STATUSES:
            assert not TenderStatus.TAKEN.can_transition_to(target)

    def test_rejected_has_no_transitions(self):
        for target in ALL_STATUSES:
            assert not TenderStatus.REJECTED.can_transition_to(target)

    def test_pending_cannot_jump_to_taken(self):
        assert not TenderStatus.PENDING.can_transition_to(TenderStatus.TAKEN)


class TestPBTTransitions:
    @given(
        source=st.sampled_from(ALL_STATUSES),
        target=st.sampled_from(ALL_STATUSES),
    )
    def test_transition_consistent_with_table(self, source, target):
        expected = target in _VALID_TRANSITIONS.get(source, set())
        assert source.can_transition_to(target) == expected
