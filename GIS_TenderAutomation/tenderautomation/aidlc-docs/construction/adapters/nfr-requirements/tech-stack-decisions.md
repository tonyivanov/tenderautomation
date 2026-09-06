# Tech Stack Decisions — Unit 2: Platform Adapters

## Сводная таблица

| Слой | Библиотека | Версия | Обоснование |
|---|---|---|---|
| HTTP-клиент | httpx | ≥0.27.0 | Q1:C — единый клиент для B2B-Center и Bidzaar (вне Playwright). Sync API, современный, поддерживает кастомные headers/cookies |
| Browser automation | playwright | ≥1.48.0 | Bidzaar auth: единственный способ получить JWT из localStorage браузерного приложения |
| HTML parsing | beautifulsoup4 | ≥4.12.0 | B2B-Center: парсинг HTML-таблиц листинга. Стабильный, безопасный парсер `html.parser` |
| YAML loading | PyYAML | ≥6.0.2 | Уже в requirements.txt. Descriptor + queries файлы |
| Base imports | `core.*` | — | PlatformAdapter ABC, TenderModel, RawTender, AuthSession и др. из Unit 1 |

## Детали ключевых решений

### httpx (Q1:C — единый HTTP-клиент)

```python
import httpx

# B2B-Center (sync, с browser-like headers)
with httpx.Client(headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True) as client:
    response = client.get(url)

# Bidzaar API (sync, с Bearer token из Playwright auth)
with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30.0) as client:
    response = client.get(api_url, params={"paging.page": page, "paging.size": 25})
```

**Почему не requests**: httpx более современный, поддерживает HTTP/2, одинаковый API для sync/async. Однородность кодовой базы.

### playwright (Bidzaar auth)

```python
from playwright.sync_api import sync_playwright

# Установка (разово):
# playwright install chromium

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(state_path))
    page = context.new_page()
    try:
        # ... auth logic ...
    finally:
        browser.close()  # SECURITY-15: always cleanup
```

**Playwright state-файлы**: путь из `descriptor.yaml` (`data/bidzaar_state.json`). Gitignored.

### beautifulsoup4 (B2B-Center HTML)

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_text, "html.parser")  # НЕ lxml — безопасный встроенный парсер
```

## Обновлённый requirements.txt (добавить)

```
httpx==0.27.2
playwright==1.48.0
beautifulsoup4==4.12.3
```

## .gitignore — добавить

```gitignore
# Bidzaar session (contain JWT tokens — gitignore regardless of path)
data/bidzaar_state.json
data/bidzaar_token.json
data/
```

## Что NOT используется

| Библиотека | Причина |
|---|---|
| `requests` | Заменяется `httpx` (Q1:C — единый клиент) |
| `lxml` | Потенциальные SSRF-риски при парсинге внешнего HTML (SECURITY-13) |
| `aiohttp` | Core sync — async HTTP не нужен |
| Playwright async API | Core sync — `sync_playwright` достаточен |
> Current async transport decisions are documented in
> `../current-collection-design.md`; legacy examples below are historical context.
