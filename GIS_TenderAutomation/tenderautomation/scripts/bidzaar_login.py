"""
Ручной логин в Bidzaar через видимый браузер.
Сохраняет сессию в data/bidzaar_state.json для V3 deep analysis и закрытых вложений.

Запуск из корня проекта:
    PYTHONPATH=src python scripts/bidzaar_login.py
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LOGIN_URL = "https://bidzaar.com/auth/login"
APP_URL = "https://bidzaar.com/requests/public"
STATE_PATH = Path("data/bidzaar_state.json")
TOKEN_PATH = Path("data/bidzaar_token.json")
STATE_PATH.parent.mkdir(exist_ok=True)


def extract_token(page) -> tuple[str, int]:
    """Bidzaar хранит JWT в localStorage.access_token."""
    try:
        items = page.evaluate(
            "() => { const o={}; for(let i=0;i<localStorage.length;i++){"
            "const k=localStorage.key(i); o[k]=localStorage.getItem(k);} return o; }"
        )
    except Exception:
        return "", 0

    token_raw = items.get("access_token", "").strip().strip('"')
    if token_raw.startswith("{"):
        try:
            token_raw = json.loads(token_raw).get("access_token", "")
        except json.JSONDecodeError:
            return "", 0

    if not token_raw or "." not in token_raw:
        return "", 0

    # Декодируем exp из JWT
    import base64
    try:
        parts = token_raw.split(".")
        padding = "=" * ((4 - len(parts[1]) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        expires_at = int(payload.get("exp", 0))
    except Exception:
        expires_at = 0

    return token_raw, expires_at


def main():
    print("Открываю Bidzaar в браузере...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

        print()
        print("=" * 60)
        print("Войдите в Bidzaar в открывшемся окне браузера.")
        print("После успешного входа (появится список тендеров)")
        print("нажмите Enter здесь в терминале.")
        print("=" * 60)
        input()

        # Ждём появления токена в localStorage после редиректа
        token, expires_at = extract_token(page)
        deadline = time.time() + 30
        while not token and time.time() < deadline:
            print("Ожидаю токен...")
            time.sleep(2)
            token, expires_at = extract_token(page)

        if token:
            print(f"✅ Токен получен (exp: {expires_at})")
            TOKEN_PATH.write_text(
                json.dumps({"access_token": token, "expires_at": expires_at}),
                encoding="utf-8",
            )
        else:
            print("⚠️  Токен не найден в localStorage. Всё равно сохраняю сессию...")

        context.storage_state(path=str(STATE_PATH))
        cookies = context.cookies()
        print(f"✅ Сессия сохранена: {len(cookies)} cookies → {STATE_PATH}")
        browser.close()

    # Проверяем
    print("\nПроверка сессии...")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    print(f"Сохранено cookies: {len(state.get('cookies', []))}")
    print(f"Токен сохранён: {TOKEN_PATH.exists()}")
    print("\nГотово! Теперь доступен V3 deep analysis закрытых вложений.")


if __name__ == "__main__":
    main()
