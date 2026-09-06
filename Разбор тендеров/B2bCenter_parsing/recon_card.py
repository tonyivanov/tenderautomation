"""
recon_card.py — разведка одной карточки тендера авторизованной сессией.

Что делает:
  1. Берёт cookies из auth/auth_state.json (после login.py).
  2. Открывает страницу тендера через httpx (без браузера, быстро).
  3. Сохраняет полный HTML в data/recon/<id>.html
  4. Делает скриншот через Playwright в data/recon/<id>.png
  5. Печатает в консоль, что нашёл интересного: ОКПД, файлы вложений,
     описание лотов, контакты заказчика.

Это разовая разведка. По её результатам собираем парсер карточек.

Запуск:
  python recon_card.py 4431469              # по ID
  python recon_card.py https://www.b2b-...  # по URL
  python recon_card.py --top 3              # первые 3 кандидата из БД
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "b2bcenter.db"
RECON_DIR = ROOT / "data" / "recon"
STATE_FILE = ROOT / "auth" / "auth_state.json"

BASE = "https://www.b2b-center.ru"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def cookies_from_storage_state(state_file: Path) -> dict[str, str]:
    """Достаёт cookies из storage state в формат для httpx."""
    if not state_file.exists():
        sys.exit(f"[err] не нашёл {state_file}. Сначала запусти login.py")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    return {c["name"]: c["value"] for c in state.get("cookies", [])
            if c.get("domain", "").endswith("b2b-center.ru")}


def resolve_url(arg: str) -> str:
    """Принимает или ID, или полный URL — отдаёт полный URL."""
    if arg.startswith("http"):
        return arg
    if arg.isdigit():
        # На B2B-Center URL без slug тоже резолвится через 301 → полный URL
        return f"{BASE}/market/tender-{arg}/"
    sys.exit(f"[err] не понял аргумент: {arg}")


def describe_page(html: str) -> dict:
    """Печатает в лог всё, что удалось найти в карточке."""
    soup = BeautifulSoup(html, "lxml")
    info: dict = {}

    # Заголовок
    h1 = soup.find("h1")
    info["title"] = h1.get_text(strip=True) if h1 else None

    # Все ссылки с атрибутом href, содержащим расширения файлов или /file/
    file_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if any(href.lower().endswith(ext) for ext in
               (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z")):
            file_links.append({"text": text, "href": href})
        elif "/file/" in href or "download" in href.lower():
            file_links.append({"text": text, "href": href})
    info["file_links"] = file_links[:30]

    # Поиск ОКПД2 — обычно в виде "ОКПД2 62.02"
    okpd_pattern = re.compile(r"ОКПД\s*2?[\s:]*([\d.]+)")
    okpd_matches = okpd_pattern.findall(soup.get_text(" ", strip=True))
    info["okpd"] = list(set(okpd_matches))

    # Признаки залогиненности на этой странице
    info["seems_logged_in"] = bool(
        soup.find("a", href=re.compile(r"/personal/|/logout/|/lk/"))
    )

    # Признаки редиректа на логин (страница вернула HTML, но это форма входа)
    info["seems_login_wall"] = bool(
        soup.find("input", attrs={"name": re.compile(r"password", re.I)})
    )

    # Ищем блоки с типичными метками: "Заказчик", "Регион", "Цена", "Способ закупки"
    text = soup.get_text("\n", strip=True)
    labels = [
        "Заказчик", "Организатор", "Регион", "Способ", "Начальная цена",
        "Цена", "Подача", "Окончание", "Контакт", "Лот",
    ]
    snippets = {}
    for label in labels:
        # ищем строки, начинающиеся с метки
        m = re.search(rf"^{label}[^\n]{{0,200}}", text, re.MULTILINE | re.IGNORECASE)
        if m:
            snippets[label] = m.group(0)[:200]
    info["label_snippets"] = snippets

    # Длина текста (косвенный признак — нет ли пейволла)
    info["text_length"] = len(text)

    return info


def fetch_via_httpx(url: str, cookies: dict[str, str]) -> tuple[str, int]:
    """Скачиваем страницу httpx с куками. Возвращаем (html, status)."""
    with httpx.Client(headers=HEADERS, cookies=cookies,
                      follow_redirects=True, timeout=30) as client:
        r = client.get(url)
        return r.text, r.status_code


def screenshot_via_playwright(url: str, out_png: Path) -> None:
    """Делаем скриншот страницы — для визуального контроля."""
    if not STATE_FILE.exists():
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1440, "height": 1800},
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=str(out_png), full_page=True)
        browser.close()


def get_top_candidate_urls(n: int) -> list[str]:
    if not DB_PATH.exists():
        sys.exit("[err] базы нет. Сначала запусти fetch_list.py")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT url FROM tenders WHERE prefilter_score = 100 "
        "ORDER BY publish_date DESC LIMIT ?",
        (n,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?",
                        help="URL карточки или её ID")
    parser.add_argument("--top", type=int, default=0,
                        help="Взять первые N кандидатов из БД")
    parser.add_argument("--no-screenshot", action="store_true")
    args = parser.parse_args()

    RECON_DIR.mkdir(parents=True, exist_ok=True)
    cookies = cookies_from_storage_state(STATE_FILE)
    print(f"[info] загрузил {len(cookies)} cookies из сессии")

    if args.top > 0:
        urls = get_top_candidate_urls(args.top)
        if not urls:
            sys.exit("[err] в базе нет кандидатов с score=100")
    elif args.target:
        urls = [resolve_url(args.target)]
    else:
        sys.exit("usage: recon_card.py <url|id> | --top N")

    for i, url in enumerate(urls, 1):
        print(f"\n=== [{i}/{len(urls)}] {url} ===")

        # Имя файла — последняя цифровая часть URL
        m = re.search(r"tender-(\d+)", url)
        slug = m.group(1) if m else f"unknown_{i}"

        html, status = fetch_via_httpx(url, cookies)
        print(f"[info] HTTP {status}, html_len={len(html)}")

        out_html = RECON_DIR / f"{slug}.html"
        out_html.write_text(html, encoding="utf-8")
        print(f"[ok] сохранил HTML → {out_html}")

        info = describe_page(html)
        print(f"[info] title: {info['title']}")
        print(f"[info] seems_logged_in: {info['seems_logged_in']}")
        print(f"[info] seems_login_wall: {info['seems_login_wall']}")
        print(f"[info] text_length: {info['text_length']}")
        print(f"[info] ОКПД найдено: {info['okpd']}")
        print(f"[info] файлов вложений: {len(info['file_links'])}")
        for fl in info["file_links"][:5]:
            print(f"        - {fl['text']!r} → {fl['href']}")
        print(f"[info] метки на странице:")
        for k, v in info["label_snippets"].items():
            print(f"        {k}: {v}")

        out_json = RECON_DIR / f"{slug}.report.json"
        out_json.write_text(
            json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[ok] отчёт по структуре → {out_json}")

        if not args.no_screenshot:
            out_png = RECON_DIR / f"{slug}.png"
            try:
                screenshot_via_playwright(url, out_png)
                print(f"[ok] скриншот → {out_png}")
            except Exception as e:
                print(f"[warn] скриншот не сделал: {e}")

        # Между запросами — человекоподобная пауза 2-5 сек
        if i < len(urls):
            import random
            pause = random.uniform(2.0, 5.0)
            print(f"[info] пауза {pause:.1f} сек")
            time.sleep(pause)


if __name__ == "__main__":
    main()
