from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from core.models import (
    InspectionApplyStatus,
    ProcedureState,
    TenderInspectionResult,
    TenderModel,
    TenderStatus,
)
from core.repositories import TenderRepository


POSTGRESQL_URL = os.getenv("TEST_POSTGRESQL_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRESQL_URL,
    reason="TEST_POSTGRESQL_URL is required for real PostgreSQL migration checks",
)


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    if POSTGRESQL_URL is None:
        yield None
        return
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRESQL_URL)
    command.upgrade(config, "head")
    engine = create_engine(POSTGRESQL_URL)
    try:
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE tenders CASCADE"))
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


def _tender(identifier: str) -> TenderModel:
    return TenderModel(
        id=f"bidzaar_{identifier}",
        platform="bidzaar",
        external_id=identifier,
        title=f"Integration tender {identifier}",
        buyer="Original buyer",
        budget=Decimal("1000.00"),
        url=f"https://example.test/{identifier}",
        qualification_tier="qualified",
        status=TenderStatus.DEFERRED,
    )


def test_migration_round_trip_and_repository_read_write(migrated_database) -> None:
    assert migrated_database is not None
    columns = {
        column["name"]
        for column in inspect(migrated_database).get_columns("tenders")
    }
    assert {
        "procedure_state",
        "procedure_checked_at",
        "procedure_last_attempt_at",
        "procedure_source",
        "procedure_error_category",
    }.issubset(columns)

    repository = TenderRepository()
    tender = _tender("roundtrip")
    assert repository.save_batch([tender]).failed_count == 0

    restored = repository.get_by_id(tender.id)
    assert restored is not None
    assert restored.procedure_state is ProcedureState.UNKNOWN
    assert restored.status is TenderStatus.DEFERRED


def test_concurrent_old_new_apply_is_monotonic_and_isolated() -> None:
    repository = TenderRepository()
    tender = _tender("concurrent")
    repository.save_batch([tender])
    attempted_at = datetime(2026, 7, 23, 8, tzinfo=timezone.utc)
    older = TenderInspectionResult(
        tender_id=tender.id,
        state=ProcedureState.CLOSED,
        verified=True,
        attempted_at=attempted_at,
        buyer="Older buyer",
    )
    newer = TenderInspectionResult(
        tender_id=tender.id,
        state=ProcedureState.ACTIVE,
        verified=True,
        attempted_at=attempted_at + timedelta(seconds=1),
        buyer="Newest buyer",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(repository.apply_inspection, (newer, older)))

    assert all(
        result.status in {InspectionApplyStatus.APPLIED, InspectionApplyStatus.STALE}
        for result in results
    )
    restored = repository.get_by_id(tender.id)
    assert restored is not None
    assert restored.procedure_state is ProcedureState.ACTIVE
    assert restored.buyer == "Newest buyer"
    assert restored.status is TenderStatus.DEFERRED
    assert restored.qualification_tier == "qualified"

    missing = repository.apply_inspection(
        TenderInspectionResult(
            tender_id="bidzaar_missing",
            attempted_at=attempted_at + timedelta(seconds=2),
        )
    )
    assert missing.status is InspectionApplyStatus.MISSING
    assert repository.get_by_id(tender.id) is not None
