"""
fetch_list.py — обходит раздел /market/ на B2B-Center, парсит таблицу
тендеров и складывает в SQLite. Без авторизации (на Дне 1 cookie не нужны).

Режимы:
  1) Сплошной обход секции (commercial / fz223), с пагинацией ?from=N
  2) Поиск по ключевому слову — использует встроенный поиск B2B-Center.
     Морфология: слово приводится к корню, все формы попадают в выдачу.
     Wildcards: смаз* → смазка, смазочный; *пожар* → пожарный, противопожарный.

Запуск:
  python fetch_list.py                      # все секции, инкрементально
  python fetch_list.py --section commercial # только коммерческие
  python fetch_list.py --limit 100          # ограничить 100 тендерами
  python fetch_list.py --full               # без ранней остановки

  python fetch_list.py --search "kubernetes"           # один запрос
  python fetch_list.py --search-file search_queries.yaml  # пачка запросов

Между запросами случайные паузы 1.5-4 сек, иногда длинные 8-15 сек.
"""

from __future__ import annotations

import argparse
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import httpx
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "b2bcenter.db"

BASE = "https://www.b2b-center.ru"

# Секции площадки. Можно расширять — структура одинаковая, отличается
# только query-параметр в URL.
SECTIONS = {
    # Коммерческие закупки + продажи (всё, что не 223-ФЗ)
    "commercial": f"{BASE}/market/",
    # 223-ФЗ (госзакупки крупных компаний с госучастием)
    "fz223": f"{BASE}/search-tender/zakupki/",
}

# Маскируемся под обычный браузер. Без правдоподобного UA быстро прилетает 403.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Между запросами делаем паузу. С вероятностью LONG_PAUSE_PROB пауза длинная
# ("посмотрел/почитал и пошёл дальше"). Это и снижает риск rate-limit, и
# естественно выглядит для антибота.
SLEEP_MIN = 1.5
SLEEP_MAX = 4.0
LONG_PAUSE_PROB = 0.15
LONG_PAUSE_MIN = 8.0
LONG_PAUSE_MAX = 15.0

# Размер страницы листинга. Нужен для пагинации через ?from=N.
PAGE_SIZE = 20

# Сколько подряд "знакомых" тендеров считаем сигналом "дальше идти бесполезно".
INCREMENTAL_STOP_AFTER = 5


def humanlike_pause() -> float:
    """Случайная пауза с редкими длинными остановками. Возвращает длительность."""
    if random.random() < LONG_PAUSE_PROB:
        pause = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
    else:
        pause = random.uniform(SLEEP_MIN, SLEEP_MAX)
    time.sleep(pause)
    return pause

# Регэкспы для разбора карточки
RE_TENDER_ID = re.compile(r"/tender-(\d+)/")
# Дата в формате 28.04.2026 21:02
RE_DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})")


def init_db(conn: sqlite3.Connection) -> None:
    """Создаёт таблицы при первом запуске или мигрирует существующие."""
    # 1. Создание таблицы (если ещё нет)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            id              INTEGER PRIMARY KEY,
            section         TEXT NOT NULL,
            url             TEXT NOT NULL,
            name            TEXT NOT NULL,
            category        TEXT,
            company_name    TEXT,
            company_url     TEXT,
            publish_date    TEXT,
            deadline_date   TEXT,
            search_query    TEXT,
            first_seen      TEXT NOT NULL,
            last_seen       TEXT NOT NULL,
            prefilter_score INTEGER DEFAULT NULL,
            prefilter_hits  TEXT DEFAULT NULL
        )
    """)

    # 2. Миграция: дописать недостающие колонки в старую схему
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tenders)")}
    if "search_query" not in cols:
        conn.execute("ALTER TABLE tenders ADD COLUMN search_query TEXT")

    # 3. Индексы — создаём только после того, как колонки гарантированно есть
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenders_section ON tenders(section)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenders_publish ON tenders(publish_date DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenders_score ON tenders(prefilter_score)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenders_query ON tenders(search_query)")

    conn.commit()


def parse_dt(raw: str) -> str | None:
    """28.04.2026 21:02 -> 2026-04-28T21:02:00. Возвращаем как ISO-строку."""
    if not raw:
        return None
    m = RE_DATE.search(raw)
    if not m:
        return None
    dd, mm, yyyy, hh, mi = m.groups()
    return f"{yyyy}-{mm}-{dd}T{hh}:{mi}:00"


def parse_listing_row(row) -> dict | None:
    """
    Из <tr> таблицы тендеров достаёт нужные поля.

    Колонки:
      0: Название процедуры (с ссылкой и категорией)
      1: Организатор
      2: Опубликовано
      3: Актуально до
      4: Кнопки избранного — игнорируем

    Если не нашли ID тендера — возвращаем None (это служебная строка).
    """
    cells = row.find_all("td")
    if len(cells) < 4:
        return None

    # --- 1. Ссылка на тендер и его ID ---
    name_cell = cells[0]
    link = name_cell.find("a", href=RE_TENDER_ID)
    if not link:
        return None
    m = RE_TENDER_ID.search(link.get("href", ""))
    if not m:
        return None
    tid = int(m.group(1))
    url = link["href"]
    if url.startswith("/"):
        url = BASE + url

    # --- 2. Категория ---
    # На B2B-Center категория идёт как текст ПЕРЕД ссылкой на тендер,
    # без явного разделителя. Чтобы корректно отделить её, идём по
    # дочерним узлам ячейки, собирая всё ДО самой ссылки на тендер.
    category_parts: list[str] = []
    for child in name_cell.children:
        if child is link:
            break
        if isinstance(child, str):
            t = child.strip()
            if t:
                category_parts.append(t)
        elif hasattr(child, "get_text"):
            t = child.get_text(" ", strip=True)
            if t:
                category_parts.append(t)
    category = " ".join(category_parts) if category_parts else None
    if category and len(category) > 200:
        category = category[:197] + "..."

    # --- 3. Название ---
    # Используем separator=' ', чтобы внутренние <br>/<span> не слипали слова
    name = link.get_text(" ", strip=True)
    name = re.sub(r"\s+", " ", name)

    # --- 4. Организатор ---
    company_name = None
    company_url = None
    company_link = cells[1].find("a")
    if company_link:
        company_name = company_link.get_text(" ", strip=True)
        company_url = company_link.get("href", "")
        if company_url.startswith("/"):
            company_url = BASE + company_url
    else:
        # Бывают случаи без ссылки (организатор скрыт)
        company_name = cells[1].get_text(" ", strip=True) or None

    # --- 5. Даты ---
    publish_date = parse_dt(cells[2].get_text(" ", strip=True))
    deadline_date = parse_dt(cells[3].get_text(" ", strip=True))

    return {
        "id": tid,
        "url": url,
        "name": name,
        "category": category,
        "company_name": company_name,
        "company_url": company_url,
        "publish_date": publish_date,
        "deadline_date": deadline_date,
    }


def fetch_page(client: httpx.Client, url: str, offset: int) -> BeautifulSoup:
    """
    Качает одну страницу листинга. Пагинация на B2B-Center — через
    параметр ?from=N, где N — смещение в записях (шаг 20).
    """
    params = {"from": offset} if offset > 0 else None
    r = client.get(url, params=params, timeout=30)
    if r.status_code == 403:
        raise SystemExit(
            f"[err] 403 Forbidden на {r.url}. Похоже, антибот. "
            f"Подожди 10-15 минут или увеличь паузы (SLEEP_MAX)."
        )
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def iter_listing_rows(soup: BeautifulSoup) -> Iterator[dict]:
    """Достаёт из страницы все валидные строки таблицы."""
    # На /market/ таблица одна большая. Берём <tr>, фильтруем парсером.
    for tr in soup.find_all("tr"):
        row = parse_listing_row(tr)
        if row:
            yield row


def upsert_tender(
    conn: sqlite3.Connection,
    row: dict,
    section: str,
    now_iso: str,
    search_query: str | None = None,
) -> bool:
    """
    Вставляет новый тендер или обновляет last_seen у существующего.
    Если тендер уже был, но пришёл по новому search_query — допишем его.
    Возвращает True, если тендер был новым.
    """
    cur = conn.execute(
        "SELECT search_query FROM tenders WHERE id = ?", (row["id"],)
    )
    existing = cur.fetchone()
    is_new = existing is None

    if is_new:
        conn.execute(
            """
            INSERT INTO tenders (
                id, section, url, name, category,
                company_name, company_url,
                publish_date, deadline_date, search_query,
                first_seen, last_seen
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["id"], section, row["url"], row["name"], row["category"],
                row["company_name"], row["company_url"],
                row["publish_date"], row["deadline_date"], search_query,
                now_iso, now_iso,
            ),
        )
    else:
        # Если пришёл новый поисковый запрос — добавим к существующим через ;
        old_q = (existing[0] or "")
        if search_query and search_query not in old_q.split(";"):
            new_q = f"{old_q};{search_query}" if old_q else search_query
            conn.execute(
                "UPDATE tenders SET last_seen = ?, deadline_date = ?, "
                "search_query = ? WHERE id = ?",
                (now_iso, row["deadline_date"], new_q, row["id"]),
            )
        else:
            conn.execute(
                "UPDATE tenders SET last_seen = ?, deadline_date = ? WHERE id = ?",
                (now_iso, row["deadline_date"], row["id"]),
            )
    return is_new


# Точные параметры поиска на B2B-Center (выяснили живым тестом):
#   /market/?f_keyword=<слово>&searching=1&trade=all
# trade=all захватывает все типы процедур: коммерческие закупки,
# продажи и 223-ФЗ — одной выдачей.
SEARCH_KEYWORD_PARAM = "f_keyword"
SEARCH_FIXED_PARAMS = {"searching": "1", "trade": "all"}

# Защита от шумовой выдачи. Если на запрос B2B-Center ВНЕЗАПНО возвращает
# общий /market/ листинг (> NOISE_THRESHOLD актуальных лотов), считаем,
# что фильтр не сработал, и пропускаем этот запрос. Реальные тематические
# запросы редко дают больше 200-300 совпадений.
NOISE_THRESHOLD = 1000

# Между разными поисковыми запросами — короткая пауза. На реальном
# прогоне 2-10 сек хватает, при условии включённого NOISE_THRESHOLD-фильтра.
INTER_QUERY_PAUSE_MIN = 2.0
INTER_QUERY_PAUSE_MAX = 4.0

# Регэксп для извлечения "Актуальных лотов: N" из шапки выдачи.
# В числе тысячные разделители — это ТОЛЬКО неразрывные пробелы
# (\u00a0 или \u202f). Обычный пробел НЕ считаем разделителем —
# иначе склеим с числом из соседней строки после get_text(' ').
RE_ACTUAL_COUNT = re.compile(
    r"Актуальных\s+лотов\s*:\s*([\d\u00a0\u202f]+)",
    re.IGNORECASE,
)


def parse_actual_count(soup: BeautifulSoup) -> int | None:
    """Достаёт число "Актуальных лотов: N" из шапки страницы поиска.
    На реальном сайте тысячные разбиваются неразрывным пробелом."""
    # Используем raw text с переносами, чтобы регэксп точно остановился
    # на границе строки и не съел соседнее число
    text = soup.get_text("\n", strip=False)
    m = RE_ACTUAL_COUNT.search(text)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    return int(digits) if digits else None


def normalize_query(q: str) -> str:
    """
    Стратегия: собираем шире, разбираем потом.
    Запросы передаются в B2B-Center как есть, без кавычек — пусть их
    встроенный поиск работает по корням и подстрокам. Это даст много
    мусора (например "SRE" поймает корень "сре"), но и спрячет меньше
    наших тендеров из-за разнобоя в формулировках.

    Защиту от спорных случаев делает:
      - NOISE_THRESHOLD в crawl_search (если выдача >1000 — сервер
        игнорировал фильтр, пропускаем запрос)
      - prefilter (тендеры с >=4 запросами в search_query помечает
        шумовыми)
      - финальный разбор результата человеком в чате
    """
    return q.strip()


def crawl_search(
    conn: sqlite3.Connection,
    client: httpx.Client,
    query: str,
    limit: int | None,
    full: bool,
) -> tuple[int, int]:
    """
    Один поисковый запрос — обходим все страницы выдачи через ?from=N.
    Чтобы не перегружать выдачу, обрезаем по limit.
    Тендеры помечаются section='search' и запоминается search_query.

    Защита: на первой странице читаем "Актуальных лотов: N". Если N
    превышает NOISE_THRESHOLD — пропускаем запрос как шумовой
    (сервер вернул общий листинг вместо отфильтрованного).

    Многословные запросы автоматически оборачиваются в кавычки
    для точного поиска (см. normalize_query).
    """
    # Поисковая строка для сервера: с кавычками для многословных
    server_query = normalize_query(query)
    # Под каким именем сохраняем в БД — оригинальный без кавычек,
    # чтобы было приятнее читать в выгрузке
    label_query = query.strip().strip('"')

    if server_query != query:
        print(f"\n=== Поиск: «{label_query}» (как точная фраза) ===")
    else:
        print(f"\n=== Поиск: «{label_query}» ===")

    base_url = f"{BASE}/market/"
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    seen_total = 0
    new_total = 0
    consecutive_known = 0
    offset = 0
    stop = False
    noise_check_done = False

    while not stop:
        params = {SEARCH_KEYWORD_PARAM: server_query, **SEARCH_FIXED_PARAMS}
        if offset > 0:
            params["from"] = offset
        try:
            r = client.get(base_url, params=params, timeout=30)
            r.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[err] {e}")
            break
        soup = BeautifulSoup(r.text, "lxml")

        # На первой странице — проверка на шум.
        if not noise_check_done:
            actual = parse_actual_count(soup)
            if actual is None:
                print(f"[warn] не нашёл счётчик 'Актуальных лотов', продолжаю осторожно")
            elif actual > NOISE_THRESHOLD:
                print(
                    f"[skip] выдача {actual} лотов > порога {NOISE_THRESHOLD} — "
                    f"сервер игнорирует фильтр, пропускаю запрос"
                )
                return 0, 0
            else:
                print(f"[info] фильтр сработал: {actual} лотов в выдаче")
            noise_check_done = True

        rows = list(iter_listing_rows(soup))

        if not rows:
            if offset == 0:
                print(f"[info] по запросу «{label_query}» ничего не нашлось")
            else:
                print(f"[info] from={offset} пусто, конец выдачи")
            break

        page_new = 0
        for row in rows:
            seen_total += 1
            is_new = upsert_tender(conn, row, "search", now_iso, label_query)
            if is_new:
                new_total += 1
                page_new += 1
                consecutive_known = 0
            else:
                consecutive_known += 1
            if limit and seen_total >= limit:
                stop = True
                break
        conn.commit()

        print(
            f"[from={offset:>5}] получено: {len(rows):>3}  "
            f"новых: {page_new:>3}  "
            f"всего за запрос: {seen_total}"
        )

        if stop:
            break
        if not full and consecutive_known >= INCREMENTAL_STOP_AFTER:
            print(f"[info] {INCREMENTAL_STOP_AFTER} знакомых подряд — выхожу")
            break

        offset += PAGE_SIZE
        pause = humanlike_pause()
        if pause > LONG_PAUSE_MIN:
            print(f"[info] длинная пауза {pause:.1f} сек")

    # Большая пауза перед следующим запросом
    if not stop:
        big_pause = random.uniform(INTER_QUERY_PAUSE_MIN, INTER_QUERY_PAUSE_MAX)
        print(f"[info] пауза перед следующим запросом: {big_pause:.1f} сек")
        time.sleep(big_pause)

    return seen_total, new_total


def load_search_queries(path: Path) -> list[str]:
    """Грузит список поисковых фраз из YAML."""
    if not path.exists():
        sys.exit(f"[err] не нашёл {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    queries = cfg.get("queries", [])
    return [q.strip() for q in queries if q and q.strip()]


def crawl_section(
    conn: sqlite3.Connection,
    client: httpx.Client,
    section_key: str,
    section_url: str,
    limit: int | None,
    full: bool,
) -> tuple[int, int]:
    """
    Обходит одну секцию (commercial / fz223) через ?from=N.
    Возвращает (всего_увидели, новых_добавили).

    Условия выхода:
      - дошли до пустой страницы
      - набрали --limit тендеров
      - в режиме без --full увидели INCREMENTAL_STOP_AFTER знакомых подряд
    """
    print(f"\n=== Секция: {section_key} ({section_url}) ===")
    if limit:
        print(f"[info] лимит: {limit} тендеров")

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    seen_total = 0
    new_total = 0
    consecutive_known = 0
    offset = 0
    stop = False

    while not stop:
        soup = fetch_page(client, section_url, offset)
        rows = list(iter_listing_rows(soup))

        if not rows:
            if offset == 0:
                print("[warn] первая страница пустая — что-то не так с парсером")
            else:
                print(f"[info] страница from={offset} пустая, конец секции")
            break

        page_new = 0
        for row in rows:
            seen_total += 1
            is_new = upsert_tender(conn, row, section_key, now_iso)
            if is_new:
                new_total += 1
                page_new += 1
                consecutive_known = 0
            else:
                consecutive_known += 1

            if limit and seen_total >= limit:
                stop = True
                break

        conn.commit()
        print(
            f"[from={offset:>5}] получено: {len(rows):>3}  "
            f"новых: {page_new:>3}  "
            f"всего за запуск: {seen_total}  "
            f"знакомых подряд: {consecutive_known}"
        )

        if stop:
            print(f"[info] достигнут лимит {limit}")
            break
        if not full and consecutive_known >= INCREMENTAL_STOP_AFTER:
            print(
                f"[info] {INCREMENTAL_STOP_AFTER} тендеров подряд знакомы — "
                f"дальше всё уже в базе. Используй --full для полного обхода."
            )
            break

        offset += PAGE_SIZE
        pause = humanlike_pause()
        # Длинные паузы озвучиваем — выглядят как "пользователь задумался"
        if pause > LONG_PAUSE_MIN:
            print(f"[info] длинная пауза {pause:.1f} сек (имитация чтения)")

    return seen_total, new_total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--section", choices=["commercial", "fz223", "all"], default="all",
        help="Секция для сплошного обхода (если не указан --search/--search-file)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Лимит тендеров (на запрос или суммарно по секциям)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Не останавливаться на первом знакомом тендере",
    )
    parser.add_argument(
        "--search", type=str, default=None,
        help="Один поисковый запрос (морфология + wildcards *)",
    )
    parser.add_argument(
        "--search-file", type=str, default=None,
        help="YAML-файл со списком поисковых запросов",
    )
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    grand_seen = 0
    grand_new = 0

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        # === РЕЖИМ ПОИСКА ===
        if args.search or args.search_file:
            queries: list[str] = []
            if args.search:
                queries.append(args.search)
            if args.search_file:
                queries.extend(load_search_queries(Path(args.search_file)))

            print(f"[info] поисковых запросов: {len(queries)}")
            for i, q in enumerate(queries, 1):
                print(f"\n--- запрос {i}/{len(queries)} ---")
                try:
                    s, n = crawl_search(
                        conn, client, q, limit=args.limit, full=args.full,
                    )
                    grand_seen += s
                    grand_new += n
                except httpx.HTTPError as e:
                    print(f"[err] запрос «{q}» оборвался: {e}")
                    continue

        # === РЕЖИМ СПЛОШНОГО ОБХОДА ===
        else:
            sections_to_crawl = (
                list(SECTIONS.items())
                if args.section == "all"
                else [(args.section, SECTIONS[args.section])]
            )
            remaining = args.limit
            for key, url in sections_to_crawl:
                if remaining is not None and remaining <= 0:
                    print(f"\n[info] лимит {args.limit} исчерпан, секцию {key} пропускаю")
                    break
                try:
                    s, n = crawl_section(
                        conn, client, key, url,
                        limit=remaining, full=args.full,
                    )
                    grand_seen += s
                    grand_new += n
                    if remaining is not None:
                        remaining -= s
                except httpx.HTTPError as e:
                    print(f"[err] секция {key} оборвалась: {e}")
                    continue

    total_in_db = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    conn.close()

    print(f"\n=== ИТОГО ===")
    print(f"Просмотрено за этот запуск: {grand_seen}")
    print(f"Новых тендеров: {grand_new}")
    print(f"Всего в базе: {total_in_db}")
    print(f"\nДальше: запусти prefilter.py, чтобы пометить кандидатов.")


if __name__ == "__main__":
    main()
