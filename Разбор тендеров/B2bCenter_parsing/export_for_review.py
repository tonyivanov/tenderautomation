"""
export_for_review.py — выгружает тендеры из базы в txt для ручного разбора.

Создаёт два файла:
  data/all_tenders.txt        — ВСЕ актуальные тендеры (новейшие сверху)
  data/score100_tenders.txt   — только кандидаты после префильтра

Формат: одна строка — один тендер.
  [DEADLINE] [SECTION] ЗАКАЗЧИК | ЗАГОЛОВОК | ХИТЫ | ССЫЛКА
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "b2bcenter.db"
OUT_ALL = ROOT / "data" / "all_tenders.txt"
OUT_100 = ROOT / "data" / "score100_tenders.txt"


def fmt_date(iso: str | None) -> str:
    return iso[:10] if iso else "—"


def fmt_section(section: str) -> str:
    return {"commercial": "КОММ", "fz223": "223ФЗ", "search": "ПОИСК"}.get(
        section, section.upper()
    )


def export(conn: sqlite3.Connection, sql: str, out: Path, label: str) -> int:
    rows = list(conn.execute(sql))
    lines = [
        f"# {label}",
        f"# Всего тендеров: {len(rows)}",
        f"# Формат: [DEADLINE] [SECTION] ЗАКАЗЧИК | ЗАГОЛОВОК | ХИТЫ/ЗАПРОСЫ | URL",
        "",
    ]
    for tid, section, name, category, company, deadline, hits, query, url in rows:
        company = (company or "—").strip().replace("|", "/")
        title_full = f"{category}: {name}" if category else (name or "—")
        title_full = title_full.strip().replace("\n", " ").replace("\r", " ")
        title_full = title_full.replace("|", "/")
        # Сначала хиты префильтра, потом — поисковые запросы (если были)
        signals_parts = []
        if hits:
            signals_parts.append(hits.replace("|", "/"))
        if query:
            signals_parts.append(f"Q: {query.replace('|', '/')}")
        signals = " ; ".join(signals_parts)
        lines.append(
            f"[{fmt_date(deadline)}] [{fmt_section(section)}] "
            f"{company} | {title_full} | {signals} | {url}"
        )

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] {label}: {len(rows)} строк → {out}")
    return len(rows)


def main() -> None:
    if not DB_PATH.exists():
        sys.exit(f"[err] База {DB_PATH} не найдена. Сначала запусти fetch_list.py")

    conn = sqlite3.connect(DB_PATH)

    n_all = export(
        conn,
        """
        SELECT id, section, name, category, company_name, deadline_date,
               prefilter_hits, search_query, url
        FROM tenders
        ORDER BY publish_date DESC NULLS LAST
        """,
        OUT_ALL,
        "ВСЕ актуальные тендеры с B2B-Center",
    )

    n_100 = export(
        conn,
        """
        SELECT id, section, name, category, company_name, deadline_date,
               prefilter_hits, search_query, url
        FROM tenders
        WHERE prefilter_score = 100 OR section = 'search'
        ORDER BY publish_date DESC NULLS LAST
        """,
        OUT_100,
        "Кандидаты: score=100 ИЛИ найденные через search",
    )

    conn.close()

    print()
    print("Размеры файлов:")
    print(f"  {OUT_ALL.name}:       {OUT_ALL.stat().st_size // 1024} KB ({n_all} тендеров)")
    print(f"  {OUT_100.name}: {OUT_100.stat().st_size // 1024} KB ({n_100} тендеров)")
    print()
    print("Загрузи оба файла в чат — размечу, какие реально интересны для GIS.")


if __name__ == "__main__":
    main()
