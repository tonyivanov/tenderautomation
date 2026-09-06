"""SQLite cache for LLM classification results.

Cache key = SHA-256(normalized_title | prompt_version | primary_model).
Stores the full LLMClassificationItem as JSON.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any
from . import config, models
from .title_prep import make_cache_key

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_PATH = _CACHE_DIR / "llm_classification_v3.db"

_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_CACHE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    """Create table if not exists (safe to call multiple times)."""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS classification_cache (
                    cache_key TEXT PRIMARY KEY,
                    tender_id TEXT,
                    normalized_title TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    fit_score INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    procurement_type TEXT NOT NULL DEFAULT 'unknown',
                    primary_domain TEXT NOT NULL DEFAULT 'unknown',
                    secondary_domains TEXT NOT NULL DEFAULT '[]',
                    needs_documents INTEGER NOT NULL DEFAULT 0,
                    positive_evidence TEXT NOT NULL DEFAULT '[]',
                    negative_evidence TEXT NOT NULL DEFAULT '[]',
                    risk_flags TEXT NOT NULL DEFAULT '[]',
                    reason TEXT NOT NULL DEFAULT '',
                    model_used TEXT NOT NULL DEFAULT '',
                    judge_verdict TEXT NOT NULL DEFAULT '',
                    judge_fit_score INTEGER NOT NULL DEFAULT 0,
                    judge_confidence REAL NOT NULL DEFAULT 0.0,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(classification_cache)")}
            if "tender_id" not in columns:
                conn.execute("ALTER TABLE classification_cache ADD COLUMN tender_id TEXT")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_model
                ON classification_cache(model_used)
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_tender_id ON classification_cache(tender_id)")
            conn.commit()
        finally:
            conn.close()


def get(title: str, *, tender_id: str | None = None) -> models.LLMClassificationItem | None:
    """Retrieve by stable ID and key, with a title-key fallback for legacy rows."""
    key = make_cache_key(title)
    with _lock:
        conn = _get_conn()
        try:
            row = None
            if tender_id:
                row = conn.execute(
                    "SELECT * FROM classification_cache WHERE tender_id = ? AND cache_key = ?",
                    (tender_id, key),
                ).fetchone()
            if row is None:
                if tender_id:
                    row = conn.execute(
                        """SELECT * FROM classification_cache
                           WHERE cache_key = ? AND (tender_id IS NULL OR tender_id = '')""",
                        (key,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM classification_cache WHERE cache_key = ?", (key,)
                    ).fetchone()
            if row is None:
                return None
            return models.LLMClassificationItem(
                id=row["cache_key"], verdict=row["verdict"], fit_score=row["fit_score"],
                confidence=row["confidence"], procurement_type=row["procurement_type"],
                primary_domain=row["primary_domain"], secondary_domains=json.loads(row["secondary_domains"]),
                needs_documents=bool(row["needs_documents"]), positive_evidence=json.loads(row["positive_evidence"]),
                negative_evidence=json.loads(row["negative_evidence"]), risk_flags=json.loads(row["risk_flags"]),
                reason=row["reason"],
            )
        finally:
            conn.close()


def put(title: str, item: models.LLMClassificationItem, *,
        tender_id: str | None = None,
        model_used: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost: float = 0.0,
        ) -> None:
    """Store classification in cache. Key derived from title."""
    key = make_cache_key(title)
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO classification_cache
                   (cache_key, tender_id, normalized_title, verdict, fit_score, confidence,
                    procurement_type, primary_domain, secondary_domains,
                    needs_documents, positive_evidence, negative_evidence,
                    risk_flags, reason, model_used, input_tokens, output_tokens,
                    estimated_cost)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    key,
                    tender_id,
                    title,
                    item.verdict,
                    item.fit_score,
                    item.confidence,
                    item.procurement_type,
                    item.primary_domain,
                    json.dumps(item.secondary_domains, ensure_ascii=False),
                    int(item.needs_documents),
                    json.dumps(item.positive_evidence, ensure_ascii=False),
                    json.dumps(item.negative_evidence, ensure_ascii=False),
                    json.dumps(item.risk_flags, ensure_ascii=False),
                    item.reason,
                    model_used,
                    input_tokens,
                    output_tokens,
                    estimated_cost,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def put_judge(title: str, item: models.LLMClassificationItem) -> None:
    """Update cache with judge classification result."""
    key = make_cache_key(title)
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                """UPDATE classification_cache
                   SET judge_verdict = ?, judge_fit_score = ?, judge_confidence = ?
                   WHERE cache_key = ?""",
                (item.verdict, item.fit_score, item.confidence, key),
            )
            conn.commit()
        finally:
            conn.close()


def get_judge(title: str) -> models.LLMClassificationItem | None:
    """Retrieve cached judge classification by title."""
    key = make_cache_key(title)
    with _lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT judge_verdict, judge_fit_score, judge_confidence FROM classification_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None or not row[0]:
                return None
            return models.LLMClassificationItem(
                id=key[:16],
                verdict=row[0],
                fit_score=row[1],
                confidence=row[2],
            )
        finally:
            conn.close()


def stats() -> dict[str, Any]:
    """Return cache statistics."""
    with _lock:
        conn = _get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM classification_cache").fetchone()[0]
            by_verdict: dict[str, int] = {}
            for row in conn.execute(
                "SELECT verdict, COUNT(*) FROM classification_cache GROUP BY verdict"
            ):
                by_verdict[row[0]] = row[1]
            by_model: dict[str, dict[str, int | float]] = {}
            for row in conn.execute(
                "SELECT model_used, COUNT(*), SUM(estimated_cost) FROM classification_cache GROUP BY model_used"
            ):
                by_model[row[0]] = {"count": row[1], "total_cost": round(row[2], 6)}
            return {
                "total_entries": total,
                "by_verdict": by_verdict,
                "by_model": by_model,
                "db_path": str(_CACHE_PATH),
            }
        finally:
            conn.close()


def clear() -> int:
    """Delete all cache entries. Returns number of deleted rows."""
    with _lock:
        conn = _get_conn()
        try:
            count = conn.execute("DELETE FROM classification_cache").rowcount
            conn.commit()
            return count
        finally:
            conn.close()


# Auto-init on import
init_db()
