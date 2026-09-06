"""
prefilter.py — применяет правила из keywords.yaml ко всем тендерам в базе.

СТРАТЕГИЯ: собираем всё, что выдал поиск B2B-Center — финальную
разметку делает человек в чате на полном контексте.

Поэтому для тендеров из section='search' префильтр работает максимально
просто: ВСЕ → score=100. Без шумового скоринга по числу запросов
(он отбраковывал реальные кейсы, где тендер совпадал с многими
синонимами одновременно — это сильный сигнал релевантности, а не шум).

Защита от поломок сервера остаётся на стороне fetch_list.py:
если по запросу выдача >NOISE_THRESHOLD лотов, запрос пропускается
полностью (значит сервер вернул общий /market/ листинг).

Для тендеров из commercial/fz223 (сплошной обход) логика прежняя:
  - есть blacklist-слово → score=0
  - есть whitelist-слово → score=100
  - иначе → score=NULL

Скрипт можно запускать сколько угодно раз — он просто перепишет score.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "b2bcenter.db"
KW_PATH = ROOT / "keywords.yaml"


def load_keywords() -> tuple[list[str], list[str]]:
    if not KW_PATH.exists():
        sys.exit(f"[err] Не нашёл {KW_PATH}")
    cfg = yaml.safe_load(KW_PATH.read_text(encoding="utf-8")) or {}
    whitelist = [kw.lower().strip() for kw in cfg.get("whitelist_keywords", []) if kw]
    blacklist = [kw.lower().strip() for kw in cfg.get("blacklist", []) if kw]
    return whitelist, blacklist


def find_hits(text: str, keywords: list[str]) -> list[str]:
    text_low = text.lower()
    return [kw for kw in keywords if kw in text_low]


def count_queries(search_query: str | None) -> int:
    if not search_query:
        return 0
    return len([q for q in search_query.split(";") if q.strip()])


def main() -> None:
    if not DB_PATH.exists():
        sys.exit(f"[err] База {DB_PATH} не найдена. Сначала запусти fetch_list.py")

    whitelist, blacklist = load_keywords()
    print(f"[info] whitelist: {len(whitelist)} слов, blacklist: {len(blacklist)} слов")
    print(f"[info] для search-тендеров шумовой скоринг ОТКЛЮЧЁН — все идут в выгрузку")

    conn = sqlite3.connect(DB_PATH)
    rows = list(conn.execute(
        "SELECT id, name, category, section, search_query FROM tenders"
    ))

    n_total = len(rows)
    n_candidates = 0
    n_blacklisted = 0
    n_neutral = 0
    n_search_kept = 0

    for tid, name, category, section, search_query in rows:
        haystack = f"{name or ''} {category or ''}"

        if section == "search":
            # Все search-тендеры идут в выгрузку. Финальную разметку
            # делает человек на полном контексте в чате.
            score = 100
            n_queries = count_queries(search_query)
            hits_str = f"(via search: {n_queries}q)"
            n_candidates += 1
            n_search_kept += 1
        else:
            # Сплошной обход — старая логика с whitelist/blacklist
            bl_hits = find_hits(haystack, blacklist)
            wl_hits = find_hits(haystack, whitelist)
            if bl_hits:
                score = 0
                hits_str = "BL: " + ", ".join(bl_hits[:5])
                n_blacklisted += 1
            elif wl_hits:
                score = 100
                hits_str = "WL: " + ", ".join(wl_hits[:5])
                n_candidates += 1
            else:
                score = None
                hits_str = None
                n_neutral += 1

        conn.execute(
            "UPDATE tenders SET prefilter_score = ?, prefilter_hits = ? WHERE id = ?",
            (score, hits_str, tid),
        )

    conn.commit()
    conn.close()

    print(f"\n=== РЕЗУЛЬТАТ ПРЕФИЛЬТРА ===")
    print(f"Всего тендеров:                {n_total}")
    print(f"Кандидаты (score=100):         {n_candidates}")
    if n_search_kept:
        print(f"  из них из search:            {n_search_kept}")
    print(f"Отсеяно blacklist (score=0):   {n_blacklisted}")
    print(f"Нерелевантно (score=NULL):     {n_neutral}")
    print(f"\nДальше: запусти export_for_review.py для выгрузки в txt.")


if __name__ == "__main__":
    main()
