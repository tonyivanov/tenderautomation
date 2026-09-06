"""
Авторизация в Bidzaar через Playwright.

Логика:
- Если playwright_state.json существует — открываем headless-браузер с сохранённой
  сессией, забираем свежий access-токен из localStorage, закрываем.
- Если нет (или сессия протухла) — открываем видимый браузер, ждём, пока
  пользователь залогинится руками, сохраняем state.

Используется fetch_list.py при старте — заменяет ручной auth.txt.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
STATE_PATH = ROOT / "playwright_state.json"
TOKEN_CACHE_PATH = ROOT / "data" / "token_cache.json"

LOGIN_URL = "https://bidzaar.com/auth/login"
APP_URL = "https://bidzaar.com/requests/public"

# Bidzaar хранит JWT в localStorage под ключом access_token (как plain-строку,
# не JSON). Здесь же ключ id_token. Срока истечения отдельно нет — определим
# его, распарсив payload самого JWT.
ACCESS_TOKEN_KEY = "access_token"


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        sys.exit(
            "[err] Playwright не установлен.\n"
            "Запусти 1_setup.bat — он поставит Playwright и Chromium."
        )


def _jwt_expiry(token):
    """Достаём поле exp (Unix timestamp) из JWT-payload. 0 если не получилось."""
    import base64
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return 0
        payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return int(payload.get("exp", 0))
    except Exception:
        return 0


def _extract_token_from_storage(storage_items):
    """
    Достаём access_token. Bidzaar хранит его в localStorage под ключом
    access_token напрямую (plain JWT, не JSON-обёртка).
    Срок истечения берём из payload самого токена (поле exp).
    """
    token = storage_items.get(ACCESS_TOKEN_KEY)
    if not token:
        return None, 0

    # На всякий случай — иногда оборачивают в кавычки/JSON
    token = token.strip().strip('"')
    if token.startswith("{"):
        try:
            data = json.loads(token)
            token = data.get("access_token", "")
        except json.JSONDecodeError:
            return None, 0

    if not token or "." not in token:
        return None, 0

    expires_at = _jwt_expiry(token)
    return token, expires_at


def _read_localstorage(page):
    """Достаём весь localStorage страницы как dict."""
    return page.evaluate(
        """() => {
            const out = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                out[k] = localStorage.getItem(k);
            }
            return out;
        }"""
    )


def _do_manual_login(sync_playwright):
    """Открываем видимый браузер, ждём логина, сохраняем state и токен."""
    print("[auth] Сессия отсутствует или протухла — нужен ручной логин.")
    print("[auth] Сейчас откроется браузер. Войди в Bidzaar как обычно,")
    print("[auth] дождись главной страницы — окно закроется само.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(LOGIN_URL)

        # Ждём появления access_token в localStorage. Появляется обычно
        # через 1-3 секунды после успешного логина.
        deadline = time.time() + 300  # 5 минут максимум
        token = None
        expires_at = 0
        while time.time() < deadline:
            try:
                items = _read_localstorage(page)
                token, expires_at = _extract_token_from_storage(items)
                if token:
                    break
            except Exception:
                pass
            time.sleep(2)

        if not token:
            browser.close()
            sys.exit("[err] Не удалось дождаться логина за 5 минут. Запусти заново.")

        # Сохраняем cookies + localStorage + всё прочее
        context.storage_state(path=str(STATE_PATH))
        browser.close()

        _save_token(token, expires_at)
        print(f"[auth] Готово. Сессия сохранена в {STATE_PATH.name}")
        return token


def _save_token(token, expires_at):
    TOKEN_CACHE_PATH.parent.mkdir(exist_ok=True)
    TOKEN_CACHE_PATH.write_text(
        json.dumps({"access_token": token, "expires_at": expires_at}),
        encoding="utf-8",
    )


def _load_cached_token():
    """Возвращает токен из кэша, если он ещё валиден (с запасом 60 сек)."""
    if not TOKEN_CACHE_PATH.exists():
        return None
    try:
        data = json.loads(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
        if data.get("expires_at", 0) - 60 > time.time():
            return data["access_token"]
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _refresh_token_silently(sync_playwright):
    """Открываем headless-браузер, заходим на app, забираем свежий токен."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()
        try:
            page.goto(APP_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            browser.close()
            print(f"[warn] Не получилось открыть страницу: {e}")
            return None

        # Даём приложению догрузиться и обновить токен (если нужно)
        time.sleep(3)
        try:
            items = _read_localstorage(page)
        except Exception as e:
            browser.close()
            print(f"[warn] Не удалось прочитать localStorage: {e}")
            return None

        token, expires_at = _extract_token_from_storage(items)
        # Перезаписываем state — куки и localStorage могли обновиться
        if token:
            context.storage_state(path=str(STATE_PATH))
        browser.close()

        if token:
            _save_token(token, expires_at)
            return token
        return None


def get_token():
    """
    Главная функция. Возвращает свежий access-токен.
    Сценарии:
      1. Кэш свежий — отдаём из кэша (мгновенно).
      2. State есть — открываем headless, обновляем токен.
      3. State нет / не сработал — открываем видимый браузер для логина.
    """
    sync_playwright = _import_playwright()

    cached = _load_cached_token()
    if cached:
        return cached

    if STATE_PATH.exists():
        print("[auth] Обновляю токен через сохранённую сессию...")
        token = _refresh_token_silently(sync_playwright)
        if token:
            print("[auth] Токен обновлён.")
            return token
        print("[auth] Сохранённая сессия не сработала — нужен повторный логин.")

    return _do_manual_login(sync_playwright)


def get_session_cookies():
    """
    Достаёт cookies из state-файла в формате dict для requests.
    Если state-файла нет — возвращает пустой dict.
    """
    if not STATE_PATH.exists():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    cookies = {}
    for c in data.get("cookies", []):
        cookies[c["name"]] = c["value"]
    return cookies


if __name__ == "__main__":
    # Запуск напрямую — для теста: показать токен.
    t = get_token()
    print(f"\nТокен (первые 60 символов): {t[:60]}...")
