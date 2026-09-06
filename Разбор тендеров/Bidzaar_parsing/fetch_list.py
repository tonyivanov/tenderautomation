"""
Забирает список тендеров с Bidzaar и складывает в SQLite.

Авторизация — автоматическая, через модуль auth.py (Playwright).
Первый раз попросит залогиниться руками в открытом окне браузера,
дальше всё будет работать само.

Запуск:
  python fetch_list.py            # инкрементальный синк (только новые)
  python fetch_list.py --full     # пересобрать всё с нуля
"""
import json
import sqlite3
import time
import sys
from pathlib import Path
import requests

import auth as auth_module

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "bidzaar.db"

LIST_URL = "https://bidzaar.com/api/process/light/procedures/available"
RATE_LIMIT_SECONDS = 1.0


def make_session():
    """Создаём requests.Session с актуальным токеном и куками."""
    token = auth_module.get_token()
    cookies = auth_module.get_session_cookies()

    s = requests.Session()
    for name, value in cookies.items():
        s.cookies.set(name, value, domain="bidzaar.com")

    company_id_cookie = cookies.get("x-company-id", "")
    company_id = ""
    if "%3B" in company_id_cookie:
        company_id = company_id_cookie.split("%3B")[-1]
    elif company_id_cookie:
        company_id = company_id_cookie

    s.headers.update({
        "authorization": f"Bearer {token}",
        "accept": "application/json, text/plain, */*",
        "accept-language": "ru-RU,ru;q=0.9,en;q=0.8",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ),
        "referer": "https://bidzaar.com/",
        "origin": "https://bidzaar.com",
    })
    if company_id:
        s.headers["x-user-companyid"] = company_id
    return s


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tenders (
            id TEXT PRIMARY KEY,
            number TEXT,
            name TEXT,
            company_id TEXT,
            company_name TEXT,
            publish_date TEXT,
            acceptance_end_date TEXT,
            finish_date TEXT,
            status INTEGER,
            procedure_type INTEGER,
            trading_type INTEGER,
            delivery_addresses TEXT,
            raw_json TEXT,
            fetched_at TEXT,
            reviewed_at TEXT,
            prefilter_score INTEGER,
            prefilter_reason TEXT,
            details_fetched INTEGER DEFAULT 0,
            llm_score INTEGER,
            llm_verdict TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_publish_date ON tenders(publish_date DESC);
        CREATE INDEX IF NOT EXISTS idx_prefilter ON tenders(prefilter_score);
        CREATE INDEX IF NOT EXISTS idx_reviewed ON tenders(reviewed_at);
    """)
    # Миграция: добавляем reviewed_at для старых баз, если поля ещё нет
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tenders)")}
    if "reviewed_at" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN reviewed_at TEXT")
        conn.commit()
    conn.commit()
    return conn


def fetch_page(session, page, page_size=25):
    params = [
        ("paging.page", page),
        ("paging.size", page_size),
        ("sorting.key", "publishDate"),
        ("sorting.direction", "desc"),
        ("logic", "and"),
        ("filters[0].operator", "in"),
        ("filters[0].field", "status"),
        ("filters[0].value", "[1]"),
        ("filters[1].operator", "eq"),
        ("filters[1].field", "procedureType"),
        ("filters[1].value", "1"),
    ]
    r = session.get(LIST_URL, params=params, timeout=30)
    if r.status_code in (401, 403):
        sys.exit(
            f"[err] Сервер вернул {r.status_code}. Сессия недействительна.\n"
            "Удали playwright_state.json и запусти заново — будет ручной логин."
        )
    r.raise_for_status()
    return r.json()


def upsert_tender(conn, item, fetched_at):
    conn.execute("""
        INSERT INTO tenders (
            id, number, name, company_id, company_name,
            publish_date, acceptance_end_date, finish_date,
            status, procedure_type, trading_type,
            delivery_addresses, raw_json, fetched_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            acceptance_end_date=excluded.acceptance_end_date,
            finish_date=excluded.finish_date,
            status=excluded.status,
            raw_json=excluded.raw_json,
            fetched_at=excluded.fetched_at
    """, (
        item["id"],
        item.get("number"),
        item.get("name"),
        item.get("companyId"),
        item.get("companyName"),
        item.get("publishDate"),
        item.get("acceptanceEndDate"),
        item.get("finishDate"),
        item.get("status"),
        item.get("procedureType"),
        item.get("tradingType"),
        json.dumps(item.get("deliveryAddresses", []), ensure_ascii=False),
        json.dumps(item, ensure_ascii=False),
        fetched_at,
    ))


def main():
    incremental = "--full" not in sys.argv
    session = make_session()
    conn = init_db()

    known_ids = (
        {row[0] for row in conn.execute("SELECT id FROM tenders")}
        if incremental else set()
    )
    if incremental:
        print(f"[info] В базе уже {len(known_ids)} тендеров. Идём до первого знакомого.")
    else:
        print("[info] Полный сбор (флаг --full). Прочешем все страницы.")

    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    page = 1
    total_added = 0
    total_seen = 0
    total_count = None

    while True:
        try:
            data = fetch_page(session, page)
        except requests.HTTPError as e:
            print(f"[err] HTTP ошибка на странице {page}: {e}")
            break
        except requests.RequestException as e:
            print(f"[err] Сетевая ошибка на странице {page}: {e}. Жду 5 сек и повторяю.")
            time.sleep(5)
            try:
                data = fetch_page(session, page)
            except Exception as e2:
                print(f"[err] Повторная ошибка: {e2}. Останавливаюсь.")
                break

        items = data.get("items", [])
        if total_count is None:
            total_count = data.get("totalCount", 0)
            print(f"[info] Всего активных тендеров на площадке: {total_count}")

        if not items:
            print(f"[info] Страница {page} пустая. Останавливаюсь.")
            break

        page_known_count = 0
        for item in items:
            total_seen += 1
            if incremental and item["id"] in known_ids:
                page_known_count += 1
            else:
                upsert_tender(conn, item, fetched_at)
                total_added += 1
        conn.commit()

        new_on_page = len(items) - page_known_count
        print(f"[ok] Страница {page}: получено {len(items)}, новых {new_on_page}")

        if incremental and page_known_count == len(items):
            print("[info] Все на странице уже в базе — синк завершён.")
            break

        if total_seen >= total_count:
            print("[info] Достигли последней страницы.")
            break

        page += 1
        time.sleep(RATE_LIMIT_SECONDS)

    print(f"\n[done] Добавлено/обновлено: {total_added}. Просмотрено: {total_seen}.")
    print(f"[done] База: {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
