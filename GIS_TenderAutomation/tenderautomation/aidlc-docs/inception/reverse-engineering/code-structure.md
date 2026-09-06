# Code Structure

## Build System
- **Type**: pip + venv, по `requirements.txt` на каждый конвейер. Оркестрация — Windows `.bat` (описаны в README; в распакованном архиве присутствуют только `.py`/`.yaml`/`.md`).
- **Configuration**: `requirements.txt` (×2), `keywords.yaml` (×2), `search_queries.yaml` (B2B, ~94 ключа). Кроссплатформенно: Python-скрипты работают и под Linux/macOS (см. секцию в DEPLOYMENT.md).

## Key Modules

```text
Разбор тендеров/
├── B2bCenter_parsing/        # b2bcenter-scout (HTML-скрейпинг)
│   ├── fetch_list.py   661 LOC  — обход поиска, парсинг, SQLite
│   ├── recon_card.py   236 LOC  — забор полной карточки (Playwright)
│   ├── prefilter.py    123 LOC  — простановка score
│   ├── login.py        108 LOC  — Playwright-логин, сохранение сессии
│   ├── export_for_review.py 106 LOC — выгрузка TXT
│   ├── reset_search.py  54 LOC  — чистка search-данных
│   ├── search_queries.yaml      — production-словарь (~94 ключа)
│   ├── keywords.yaml            — whitelist/blacklist для сплошного обхода
│   └── requirements.txt         — httpx, bs4, lxml, PyYAML, playwright
│
└── Bidzaar_parsing/          # bidzaar-scout (JSON API)
    ├── auth.py         235 LOC  — Playwright-аутентификация, JWT из localStorage
    ├── fetch_list.py   231 LOC  — синк списка через API (requests)
    ├── export_for_review.py 110 LOC — выгрузка TXT
    ├── prefilter.py    109 LOC  — простановка score
    ├── keywords.yaml            — whitelist/blacklist
    └── requirements.txt         — requests, PyYAML, playwright
```

### Existing Files Inventory (кандидаты на модификацию)
- `B2bCenter_parsing/fetch_list.py` — основная логика обхода/парсинга B2B-Center.
- `B2bCenter_parsing/prefilter.py` — правила score (мягкие: все search → 100).
- `B2bCenter_parsing/export_for_review.py` — формат TXT для разбора.
- `B2bCenter_parsing/login.py`, `recon_card.py` — Playwright-ветка (recon).
- `B2bCenter_parsing/reset_search.py` — обслуживание БД.
- `Bidzaar_parsing/auth.py` — аутентификация (security-критично).
- `Bidzaar_parsing/fetch_list.py` — синк через API, заголовки `x-user-companyid`.
- `Bidzaar_parsing/prefilter.py` — правила по `keywords.yaml` (0/50/100).
- `Bidzaar_parsing/export_for_review.py` — формат TXT.
- `*/keywords.yaml`, `B2bCenter_parsing/search_queries.yaml` — конфиг ключей (правится без кода).

## Design Patterns

### Pipeline (ETL)
- **Location**: оба конвейера.
- **Purpose**: разделение этапов fetch / store / filter / export.
- **Implementation**: отдельные скрипты, общая SQLite-таблица `tenders` как точка обмена.

### Incremental sync + dedup
- **Location**: `fetch_list.py` (оба).
- **Purpose**: не дублировать ранее виденные тендеры.
- **Implementation**: primary key по `id`, upsert; у B2B к существующим дописывается `search_query` через `;`.

### Config-as-data
- **Location**: `keywords.yaml`, `search_queries.yaml`.
- **Purpose**: правки бизнес-логики отбора без изменения кода (для не-разработчика).

### Saved-session auth
- **Location**: `login.py` (B2B), `auth.py` (Bidzaar).
- **Purpose**: обойти 2FA/капчу разовым ручным логином.
- **Implementation**: Playwright storage state (`auth_state.json` / `playwright_state.json`), кэш токена.

## Critical Dependencies
### Playwright
- **Usage**: аутентификация и (B2B) recon карточек.
- **Purpose**: обход 2FA/капчи через реальный браузер, хранение сессии.

### httpx / requests
- **Usage**: B2B — httpx (HTML), Bidzaar — requests (API).
- **Purpose**: HTTP-клиент.

### beautifulsoup4 + lxml
- **Usage**: B2B — парсинг HTML-таблицы выдачи.

### PyYAML
- **Usage**: чтение словарей ключевых слов и запросов.
