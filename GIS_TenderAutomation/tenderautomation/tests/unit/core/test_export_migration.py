from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from core.models import ProcedureState
from core.orm import TenderORM
from core.repositories import TenderRepository


def _migration_module():
    path = Path(__file__).parents[3] / "migrations/versions/0003_export_integrity.py"
    spec = spec_from_file_location("migration_0003", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain_and_orm_columns() -> None:
    migration = _migration_module()

    assert migration.revision == "0003"
    assert migration.down_revision == "0002"
    assert TenderORM.__table__.c.procedure_state.server_default is not None
    assert "ix_tenders_procedure_state" in {
        index.name for index in TenderORM.__table__.indexes
    }


def test_legacy_orm_row_gets_safe_procedure_defaults(tender_factory) -> None:
    tender = tender_factory()
    row = type("LegacyRow", (), tender.model_dump())()
    row.status = tender.status.value

    restored = TenderRepository.orm_to_model(row)

    assert restored.procedure_state is ProcedureState.UNKNOWN
    assert restored.procedure_checked_at is None
