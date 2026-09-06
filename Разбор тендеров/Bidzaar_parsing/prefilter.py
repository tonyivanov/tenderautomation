"""
Применяет правила из keywords.yaml к каждому тендеру в базе и проставляет:
  - prefilter_score: 0 (отсев), 50 (нейтрально), 100 (кандидат)
  - prefilter_reason: что сработало

Запуск:
  python prefilter.py
"""
import sqlite3
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "bidzaar.db"
KEYWORDS_PATH = ROOT / "keywords.yaml"


def load_rules():
    if not KEYWORDS_PATH.exists():
        sys.exit(f"[err] Не найден файл {KEYWORDS_PATH}")
    rules = yaml.safe_load(KEYWORDS_PATH.read_text(encoding="utf-8"))
    return rules or {}


def normalize(text):
    return (text or "").lower()


def first_match(text, patterns):
    """Возвращает первый pattern, который встретился как подстрока."""
    for p in patterns:
        if p.lower() in text:
            return p
    return None


def score_tender(name, rules):
    """
    Возвращает (score, reason).
      0   — попало в blacklist
      100 — есть positive keyword
      50  — нет совпадений (нейтрально)
    Blacklist приоритетнее whitelist.
    """
    text = normalize(name)
    bl = first_match(text, rules.get("blacklist", []))
    if bl:
        return 0, f"blacklist: {bl}"
    wl = first_match(text, rules.get("whitelist_keywords", []))
    if wl:
        return 100, f"keyword: {wl}"
    return 50, "no match"


def main():
    if not DB_PATH.exists():
        sys.exit(f"[err] База {DB_PATH} не найдена. Сначала запусти fetch_list.py")

    rules = load_rules()
    conn = sqlite3.connect(DB_PATH)

    rows = list(conn.execute("SELECT id, name FROM tenders"))
    print(f"[info] Размечаем {len(rows)} тендеров...")

    counts = {0: 0, 50: 0, 100: 0}
    for tid, name in rows:
        score, reason = score_tender(name, rules)
        counts[score] = counts.get(score, 0) + 1
        conn.execute(
            "UPDATE tenders SET prefilter_score=?, prefilter_reason=? WHERE id=?",
            (score, reason, tid),
        )
    conn.commit()

    print(f"\n[done] Результаты префильтра:")
    print(f"  Кандидаты (score=100):       {counts.get(100, 0)}")
    print(f"  Нейтральные (score=50):      {counts.get(50, 0)}")
    print(f"  Отсев blacklist (score=0):   {counts.get(0, 0)}")

    print("\n[info] Все кандидаты (score=100):")
    print("-" * 80)
    for company, name, reason in conn.execute("""
        SELECT company_name, name, prefilter_reason
        FROM tenders
        WHERE prefilter_score=100
        ORDER BY publish_date DESC
    """):
        company = (company or "")[:30]
        name = (name or "")[:90]
        print(f"  [{company:<30}] {name}  ({reason})")

    print("\n[info] Примеры нейтральных (первые 20, проверь — не упустили ли что):")
    print("-" * 80)
    for company, name in conn.execute("""
        SELECT company_name, name FROM tenders
        WHERE prefilter_score=50
        ORDER BY publish_date DESC
        LIMIT 20
    """):
        company = (company or "")[:30]
        name = (name or "")[:90]
        print(f"  [{company:<30}] {name}")

    conn.close()


if __name__ == "__main__":
    main()
