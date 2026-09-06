import sqlite3

from core.models import V3LookupState
from core.services.v3_export import V3ExportProjection


def _database(path, rows) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE classification_cache (
        cache_key TEXT PRIMARY KEY, tender_id TEXT, normalized_title TEXT,
        verdict TEXT, fit_score INTEGER, confidence REAL,
        procurement_type TEXT, judge_verdict TEXT, judge_fit_score INTEGER,
        judge_confidence REAL, created_at TEXT)"""
    )
    connection.executemany(
        "INSERT INTO classification_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    connection.close()


def test_projection_prefers_id_and_applies_confident_judge(tmp_path, tender_factory) -> None:
    path = tmp_path / "v3.db"
    _database(path, [("k", "bidzaar_example", "Other", "reject", 10, .9, "unknown", "review", 70, .8, "2026")])
    tender = tender_factory(title="Other")

    result = V3ExportProjection(path).get_many((tender,))[tender.id]

    assert result.state is V3LookupState.FOUND
    assert result.context is not None
    assert result.context.queue == "P2"
    assert result.context.verdict == "review"


def test_projection_requires_unambiguous_title_fallback(tmp_path, tender_factory) -> None:
    path = tmp_path / "v3.db"
    row = ("k1", None, "Duplicate", "core", 90, .9, "services", "", 0, 0, "2026")
    _database(path, [row, ("k2", *row[1:])])
    tender = tender_factory(title="Duplicate")
    assert V3ExportProjection(path).get_many((tender,))[tender.id].state is V3LookupState.NOT_FOUND


def test_projection_distinguishes_unavailable_and_lists_p1_p2(tmp_path, tender_factory) -> None:
    missing = V3ExportProjection(tmp_path / "missing.db")
    tender = tender_factory()
    assert missing.get_many((tender,))[tender.id].state is V3LookupState.UNAVAILABLE

    path = tmp_path / "v3.db"
    _database(path, [("k", tender.id, tender.title, "core", 95, .9, "services", "", 0, 0, "2026")])
    refs = V3ExportProjection(path).list_eligible_refs()
    assert refs[0].tender_id == tender.id
