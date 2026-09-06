import sqlite3

from core.services.scoring_v3 import cache
from core.services.scoring_v3.models import LLMClassificationItem


def test_legacy_cache_migrates_idempotently_and_preserves_rows(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cache.db"
    monkeypatch.setattr(cache, "_CACHE_PATH", path)
    cache.init_db()
    cache.put("Legacy", LLMClassificationItem(id="t1", fit_score=67))
    with sqlite3.connect(path) as connection:
        connection.execute("DROP INDEX idx_cache_tender_id")
        connection.execute("ALTER TABLE classification_cache DROP COLUMN tender_id")

    cache.init_db()
    cache.init_db()

    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(classification_cache)")}
        count = connection.execute("SELECT COUNT(*) FROM classification_cache").fetchone()[0]
    assert "tender_id" in columns
    assert count == 1
    assert cache.get("Legacy").fit_score == 67


def test_cache_round_trip_stores_tender_id(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cache.db"
    monkeypatch.setattr(cache, "_CACHE_PATH", path)
    cache.init_db()
    cache.put("Stable", LLMClassificationItem(id="t1", verdict="core"), tender_id="bidzaar_42")
    assert cache.get("Stable", tender_id="bidzaar_42").verdict == "core"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT tender_id FROM classification_cache").fetchone()[0] == "bidzaar_42"
    assert cache.get("Stable", tender_id="bidzaar_other") is None
