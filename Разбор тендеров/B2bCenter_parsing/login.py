"""
login.py — одноразовый логин на b2b-center.ru через Playwright.

Логика:
  1. Открывает реальный Chromium с видимым окном.
  2. Ждёт, пока ты вручную залогинишься (логин, пароль, 2FA если есть).
  3. Когда увидишь, что вошёл — переключаешься в терминал и нажимаешь Enter.
  4. Скрипт сохраняет cookies + localStorage в auth/auth_state.json.

После этого карточный парсер использует этот файл, чтобы ходить
авторизованным httpx без браузера.

Срок жизни сессии — обычно сутки-несколько. Когда начнут прилетать редиректы
на /login/, просто запусти login.py заново.

Запуск:
  python login.py
  python login.py --headless     # без окна, только если уже знаешь куки
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
AUTH_DIR = ROOT / "auth"
STATE_FILE = AUTH_DIR / "auth_state.json"

LOGIN_URL = "https://www.b2b-center.ru/"
# Признаки того, что мы залогинены — на странице есть ссылка на личный кабинет.
# Проверяем по селекторам, которые видны только авторизованным.
LOGGED_IN_SELECTORS = [
    "a[href*='/personal/']",
    "a[href*='/logout/']",
    "a[href*='/lk/']",
]


def is_logged_in(page) -> bool:
    for sel in LOGGED_IN_SELECTORS:
        if page.locator(sel).count() > 0:
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        # Стандартное разрешение, обычный UA — никаких фокусов.
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()

        print(f"[info] открываю {LOGIN_URL}")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        if is_logged_in(page):
            print("[info] похоже, уже залогинен")
        else:
            print()
            print("=" * 60)
            print("Залогинься в открывшемся окне браузера.")
            print("Когда увидишь личный кабинет — вернись сюда")
            print("и нажми Enter.")
            print("=" * 60)
            input()

            # Перепроверяем
            if not is_logged_in(page):
                print("[warn] селекторы личного кабинета не нашлись.")
                print("       возможно, разметка изменилась — но я всё равно сохраню cookies.")
                print("       нажми Enter ещё раз, если ты точно залогинен.")
                input()

        # Сохраняем storage state — туда попадают cookies + localStorage
        context.storage_state(path=str(STATE_FILE))

        # Дополнительно сохраним cookies в плоский json для отладки
        cookies = context.cookies()
        (AUTH_DIR / "cookies_debug.json").write_text(
            json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print(f"\n[ok] storage state сохранён в {STATE_FILE}")
        print(f"[ok] кук в сессии: {len(cookies)}")
        print()
        print("Дальше: запусти recon_card.py, чтобы я посмотрел, что отдаёт")
        print("страница тендера для авторизованного пользователя.")

        browser.close()


if __name__ == "__main__":
    main()
