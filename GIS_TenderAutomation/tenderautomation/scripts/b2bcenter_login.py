"""
Ручной логин в B2B-Center через видимый браузер.
Сохраняет сессию в data/b2bcenter_state.json для последующего использования.

Запуск из корня проекта:
    PYTHONPATH=src venv/bin/python scripts/b2bcenter_login.py
"""
import json
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

STATE_PATH = Path("data/b2bcenter_state.json")
STATE_PATH.parent.mkdir(exist_ok=True)

LOGGED_IN_SELECTORS = [
    'a[href*="/personal/"]',
    'a[href*="/logout/"]',
    'a[href*="/lk/"]',
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def main():
    print("Открываю B2B-Center в браузере...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()
        page.goto("https://www.b2b-center.ru/", wait_until="domcontentloaded", timeout=30000)

        print()
        print("=" * 60)
        print("Войдите в B2B-Center в открывшемся окне браузера.")
        print("После успешного входа (появится личный кабинет)")
        print("нажмите Enter здесь в терминале.")
        print("=" * 60)
        input()

        logged_in = any(page.locator(sel).count() > 0 for sel in LOGGED_IN_SELECTORS)
        if not logged_in:
            print("⚠️  Не удалось подтвердить вход. Всё равно сохраняю сессию...")

        context.storage_state(path=str(STATE_PATH))
        cookies = context.cookies()
        print(f"✅ Сессия сохранена: {len(cookies)} cookies → {STATE_PATH}")
        browser.close()

    # Test with saved cookies
    print("\nПроверяю поиск с сохранённой сессией...")
    state = json.loads(STATE_PATH.read_text())
    cookie_dict = {c["name"]: c["value"] for c in state.get("cookies", [])}

    with httpx.Client(headers=HEADERS, cookies=cookie_dict, follow_redirects=True) as client:
        r = client.get("https://www.b2b-center.ru/market/?search=devops")
        if "captcha" not in str(r.url).lower() and "forbidden" not in r.text.lower():
            soup = BeautifulSoup(r.text, "html.parser")
            lot_links = soup.find_all("a", href=re.compile(r"/market/\d+"))
            print(f"✅ Поиск работает! Найдено ссылок на тендеры: {len(lot_links)}")
            if lot_links:
                print(f"   Пример: {lot_links[0].get('href')}")
        else:
            print(f"❌ Поиск заблокирован: {r.url}")
            sys.exit(1)


if __name__ == "__main__":
    main()
