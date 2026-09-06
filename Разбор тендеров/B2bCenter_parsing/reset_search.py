"""
reset_search.py — удаляет из базы тендеры, найденные через поиск.

Зачем: если мы изменили логику поиска (например, добавили кавычки для
точного совпадения), старые шумные результаты остаются в БД и портят
выгрузку. Этот скрипт чистит только section='search', оставляя
commercial и fz223 нетронутыми.

После запуска: запусти 2b_search.bat — он перенаберёт чистые данные.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "b2bcenter.db"


def main() -> None:
    if not DB_PATH.exists():
        sys.exit(f"[err] База {DB_PATH} не найдена")

    conn = sqlite3.connect(DB_PATH)

    n_search = conn.execute(
        "SELECT COUNT(*) FROM tenders WHERE section = 'search'"
    ).fetchone()[0]
    n_other = conn.execute(
        "SELECT COUNT(*) FROM tenders WHERE section != 'search'"
    ).fetchone()[0]

    print(f"В базе:")
    print(f"  search   тендеров: {n_search}  ← будут удалены")
    print(f"  другие   тендеров: {n_other}   ← останутся")

    if n_search == 0:
        print("\nНечего удалять.")
        return

    conn.execute("DELETE FROM tenders WHERE section = 'search'")
    conn.commit()

    n_after = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    print(f"\nГотово. В базе осталось: {n_after} тендеров.")
    print("Дальше: запусти 2b_search.bat для свежего прогона поиска.")

    conn.close()


if __name__ == "__main__":
    main()
