"""
Выгружает тендеры из базы в три txt-файла для ручного анализа в чате:

  data/all_tenders.txt              — ВСЕ активные тендеры
  data/score100_tenders.txt         — все кандидаты по префильтру (score=100)
  data/new_score100_tenders.txt     — только новые кандидаты (ещё не разобранные)

Формат: одна строка — один тендер. Сортировка по дате публикации, свежие сверху.

Запуск:
  python export_for_review.py
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "bidzaar.db"
OUT_ALL = ROOT / "data" / "all_tenders.txt"
OUT_100 = ROOT / "data" / "score100_tenders.txt"
OUT_100_NEW = ROOT / "data" / "new_score100_tenders.txt"

TENDER_URL_TEMPLATE = "https://bidzaar.com/process/light/{id}"


def fmt_date(iso_str):
    if not iso_str:
        return "—"
    return iso_str[:10]


def export(conn, query, out_path, label):
    rows = list(conn.execute(query))
    lines = [
        f"# {label}",
        f"# Всего тендеров: {len(rows)}",
        f"# Формат: [DEADLINE] ЗАКАЗЧИК | ЗАГОЛОВОК | ССЫЛКА",
        "",
    ]
    for company, name, deadline, tid in rows:
        company = (company or "—").strip()
        name = (name or "—").strip().replace("\n", " ").replace("\r", " ")
        url = TENDER_URL_TEMPLATE.format(id=tid)
        lines.append(f"[{fmt_date(deadline)}] {company} | {name} | {url}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] {label}: {len(rows)} строк -> {out_path}")
    return len(rows)


def main():
    if not DB_PATH.exists():
        sys.exit(f"[err] База {DB_PATH} не найдена. Сначала запусти 2_fetch.bat")

    conn = sqlite3.connect(DB_PATH)

    # Файл 1: ВСЕ активные тендеры
    n_all = export(
        conn,
        """
        SELECT company_name, name, acceptance_end_date, id
        FROM tenders
        ORDER BY publish_date DESC
        """,
        OUT_ALL,
        "ВСЕ активные тендеры на Bidzaar",
    )

    # Файл 2: кандидаты по префильтру (все, в том числе уже разобранные)
    n_100 = export(
        conn,
        """
        SELECT company_name, name, acceptance_end_date, id
        FROM tenders
        WHERE prefilter_score = 100
        ORDER BY publish_date DESC
        """,
        OUT_100,
        "Все кандидаты по префильтру (score=100)",
    )

    # Файл 3: только новые кандидаты (ещё не разобранные)
    n_100_new = export(
        conn,
        """
        SELECT company_name, name, acceptance_end_date, id
        FROM tenders
        WHERE prefilter_score = 100 AND reviewed_at IS NULL
        ORDER BY publish_date DESC
        """,
        OUT_100_NEW,
        "Новые кандидаты (ещё не разобранные)",
    )

    conn.close()

    print()
    print("[done] Готово.")
    print(f"  {OUT_ALL.name}:               {n_all} тендеров")
    print(f"  {OUT_100.name}:          {n_100} тендеров")
    print(f"  {OUT_100_NEW.name}:      {n_100_new} тендеров (НОВЫЕ)")
    print()
    if n_100_new == 0:
        print("[info] Новых кандидатов нет — все уже размечены.")
    else:
        print(f"[info] Загрузи new_score100_tenders.txt в чат для разбора.")


if __name__ == "__main__":
    main()
