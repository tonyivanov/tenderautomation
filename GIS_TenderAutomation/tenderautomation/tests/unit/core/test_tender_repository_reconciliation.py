from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.repositories import tender as repository_module
from core.repositories.tender import TenderRepository


class _SessionContext:
    def __init__(self, session: Mock) -> None:
        self.session = session

    def __enter__(self) -> Mock:
        return self.session

    def __exit__(self, *args: object) -> None:
        return None


def _orm_row(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": "bidzaar_abc",
        "platform": "bidzaar",
        "external_id": "abc",
        "title": "Tender",
        "buyer": "Buyer",
        "budget": None,
        "deadline": None,
        "description": None,
        "url": "https://bidzaar.com/process/light/abc",
        "raw_data": {},
        "content_hash": "old",
        "prefilter_score": 10,
        "qualification_tier": "qualified",
        "matched_keywords": ["cloud"],
        "status": "taken",
        "published_at": None,
        "collected_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("limit", [0, 201, -1, True])
def test_candidate_batch_limit_is_validated_before_db(limit: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 200"):
        TenderRepository().get_reconciliation_candidates(limit)


def test_candidate_query_is_bounded_and_deterministic(monkeypatch) -> None:
    session = Mock()
    result = session.execute.return_value
    result.scalars.return_value.all.return_value = []
    monkeypatch.setattr(
        repository_module, "SessionLocal", lambda: _SessionContext(session)
    )

    assert TenderRepository().get_reconciliation_candidates(50) == []
    query = session.execute.call_args.args[0]
    compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY tenders.updated_at DESC, tenders.id ASC" in compiled
    assert "LIMIT 50" in compiled
    assert "tenders.deadline IS NULL" in compiled
    assert "bidzaar" in compiled


def test_conditional_update_preserves_status_and_existing_deadline(monkeypatch) -> None:
    existing = datetime(2026, 8, 1, tzinfo=timezone.utc)
    row = _orm_row(deadline=existing, status="deferred")
    session = Mock()
    session.get.return_value = row
    monkeypatch.setattr(
        repository_module, "SessionLocal", lambda: _SessionContext(session)
    )

    updated = TenderRepository().apply_reconciliation_update(
        "bidzaar_abc",
        deadline=datetime(2027, 1, 1, tzinfo=timezone.utc),
        url="https://bidzaar.com/app/process/light/abc",
        raw_data_updates={"deadline_source": "detail"},
    )

    assert updated == (False, True)
    assert row.deadline == existing
    assert row.status == "deferred"
    assert row.url.endswith("/app/process/light/abc")
    session.commit.assert_called_once()


def test_deadline_update_commits_one_row_and_merges_provenance(monkeypatch) -> None:
    row = _orm_row(raw_data={"kept": True})
    session = Mock()
    session.get.return_value = row
    monkeypatch.setattr(
        repository_module, "SessionLocal", lambda: _SessionContext(session)
    )

    updated = TenderRepository().apply_reconciliation_update(
        row.id,
        deadline=datetime(2026, 9, 1, tzinfo=timezone.utc),
        raw_data_updates={"deadline_source": "detail"},
    )

    assert updated == (True, False)
    assert row.raw_data == {"kept": True, "deadline_source": "detail"}
    assert row.content_hash != "old"
    session.commit.assert_called_once()


def test_no_change_does_not_commit(monkeypatch) -> None:
    row = _orm_row(url="https://bidzaar.com/app/process/light/abc")
    session = Mock()
    session.get.return_value = row
    monkeypatch.setattr(
        repository_module, "SessionLocal", lambda: _SessionContext(session)
    )
    assert TenderRepository().apply_reconciliation_update(row.id) == (False, False)
    session.commit.assert_not_called()


def test_remaining_candidate_count_uses_shared_predicate(monkeypatch) -> None:
    session = Mock()
    session.execute.return_value.scalar_one.return_value = 7
    monkeypatch.setattr(
        repository_module, "SessionLocal", lambda: _SessionContext(session)
    )
    assert TenderRepository().count_reconciliation_candidates() == 7


def test_advisory_lock_is_released_on_error(monkeypatch) -> None:
    session = Mock()
    session.execute.return_value.scalar_one.return_value = True
    monkeypatch.setattr(repository_module, "SessionLocal", lambda: session)

    with pytest.raises(RuntimeError):
        with TenderRepository().reconciliation_lock() as acquired:
            assert acquired is True
            raise RuntimeError("stop")

    assert session.execute.call_count == 2
    session.close.assert_called_once()


def test_unavailable_advisory_lock_is_not_unlocked(monkeypatch) -> None:
    session = Mock()
    session.execute.return_value.scalar_one.return_value = False
    monkeypatch.setattr(repository_module, "SessionLocal", lambda: session)
    with TenderRepository().reconciliation_lock() as acquired:
        assert acquired is False
    assert session.execute.call_count == 1
    session.close.assert_called_once()
