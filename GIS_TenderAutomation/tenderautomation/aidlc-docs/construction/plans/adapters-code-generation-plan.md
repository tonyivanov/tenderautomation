# Code Generation Plan — Unit 2: Platform Adapters

## Контекст

**Application code**: `src/adapters/` (новые файлы)
**Tests**: `tests/unit/adapters/`
**Existing code** (reference only, не изменяется): `Разбор тендеров/`
**Stories**: US-01● (полный сбор с B2B-Center и Bidzaar)
**Зависит от**: Unit 1 (`core.adapters.PlatformAdapter`, `core.models.*`)

---

## Статус выполнения

### Шаг 1: Структура и зависимости
- [x] 1.1 `src/adapters/__init__.py`
- [x] 1.2 Обновить `requirements.txt` — добавить `httpx`, `playwright`, `beautifulsoup4`
- [x] 1.3 Обновить `.gitignore` — `data/` уже добавлен ✓

### Шаг 2: B2B-Center — Parsers
- [x] 2.1 `src/adapters/b2bcenter/parsers.py` — `parse_price()`, `parse_deadline()`, `parse_total_count()`, `parse_rows()`

### Шаг 3: B2B-Center — Scraper
- [x] 3.1 `src/adapters/b2bcenter/scraper.py` — `B2BCenterScraper` (поиск, пагинация, антибот, incremental stop)

### Шаг 4: B2B-Center — Adapter + дескриптор
- [x] 4.1 `src/adapters/b2bcenter/adapter.py` — `B2BCenterAdapter(PlatformAdapter)`
- [x] 4.2 `src/adapters/b2bcenter/descriptor.yaml`
- [x] 4.3 `src/adapters/b2bcenter/queries.yaml` (перенос из существующего `search_queries.yaml`)
- [x] 4.4 `src/adapters/b2bcenter/__init__.py`

### Шаг 5: Bidzaar — Auth
- [x] 5.1 `src/adapters/bidzaar/auth.py` — `BidzaarAuth` (three-step chain, Playwright headless)

### Шаг 6: Bidzaar — API Client
- [x] 6.1 `src/adapters/bidzaar/api_client.py` — `BidzaarApiClient` (httpx, pagination, incremental)

### Шаг 7: Bidzaar — Adapter + дескриптор
- [x] 7.1 `src/adapters/bidzaar/adapter.py` — `BidzaarAdapter(PlatformAdapter)`
- [x] 7.2 `src/adapters/bidzaar/descriptor.yaml`
- [x] 7.3 `src/adapters/bidzaar/__init__.py`

### Шаг 8: Регистрация адаптеров в CLI
- [x] 8.1 Обновить `src/core/cli.py` — раскомментировать регистрацию адаптеров

### Шаг 9: Тесты (pytest + Hypothesis)
- [x] 9.1 `tests/unit/adapters/__init__.py`
- [x] 9.2 `tests/unit/adapters/b2bcenter/__init__.py`
- [x] 9.3 `tests/unit/adapters/b2bcenter/test_parsers.py` — PBT: parse_price, parse_deadline
- [x] 9.4 `tests/unit/adapters/b2bcenter/test_adapter.py` — map_to_tender determinism
- [x] 9.5 `tests/unit/adapters/bidzaar/__init__.py`
- [x] 9.6 `tests/unit/adapters/bidzaar/test_adapter.py` — map_to_tender determinism, ID format

### Шаг 10: Документация
- [x] 10.1 `aidlc-docs/construction/adapters/code/code-summary.md`

---

## Трассировка историй

| История | Шаги |
|---|---|
| US-01● (сбор с B2B-Center) | 2, 3, 4 |
| US-01● (сбор с Bidzaar) | 5, 6, 7 |
| US-01● (регистрация в pipeline) | 8 |
