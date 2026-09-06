import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

import pytest

# Make src/ importable without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Override settings for tests — no real DB needed for unit tests
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_tender")
os.environ.setdefault("B2BCENTER_USERNAME", "test@test.com")
os.environ.setdefault("B2BCENTER_PASSWORD", "testpass")
os.environ.setdefault("BIDZAAR_USERNAME", "test@test.com")
os.environ.setdefault("BIDZAAR_PASSWORD", "testpass")

from core.models import (  # noqa: E402
    ProcedureState,
    TenderInspectionResult,
    TenderModel,
    TenderStatus,
)


@pytest.fixture
def tender_factory() -> Callable[..., TenderModel]:
    def build(**overrides: object) -> TenderModel:
        values: dict[str, object] = {
            "id": "bidzaar_example",
            "platform": "bidzaar",
            "external_id": "example",
            "title": "Infrastructure tender",
            "buyer": "Test buyer",
            "budget": Decimal("1000000"),
            "deadline": datetime(2099, 1, 1, tzinfo=timezone.utc),
            "url": "https://bidzaar.com/app/process/light/example",
            "raw_data": {},
            "status": TenderStatus.PENDING,
        }
        values.update(overrides)
        return TenderModel(**values)  # type: ignore[arg-type]

    return build


@pytest.fixture
def inspection_factory() -> Callable[..., TenderInspectionResult]:
    def build(**overrides: object) -> TenderInspectionResult:
        values: dict[str, object] = {
            "tender_id": "bidzaar_example",
            "state": ProcedureState.ACTIVE,
            "verified": True,
            "attempted_at": datetime(2026, 7, 23, tzinfo=timezone.utc),
        }
        values.update(overrides)
        return TenderInspectionResult(**values)  # type: ignore[arg-type]

    return build
