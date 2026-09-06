# API Documentation

Система не предоставляет собственного API. Ниже — **внешние API/источники, которые она потребляет**, **внутренние интерфейсы CLI** и **схема данных SQLite**.

## External APIs (consumed)

### B2B-Center (неофициальный, HTML-скрейпинг)
- **Поиск**: `GET https://www.b2b-center.ru/market/?f_keyword=<слово>&searching=1&trade=all`
- **Пагинация**: `&from=N` (шаг 20).
- **Секции**: `commercial` → `/market/`, `fz223` → `/search-tender/zakupki/`.
- **Морфология**: поиск по корням; wildcard `смаз*`; без кавычек — OR между словами.
- **Аутентификация**: для списков не нужна; для полных карточек/вложений — сессия GIS (Playwright).
- **Защита**: правдоподобный `User-Agent` обязателен (иначе 403); если выдача >1000 лотов — фильтр проигнорирован, запрос пропускается.

### Bidzaar (официальный JSON API)
| Назначение | URL | Метод |
|---|---|---|
| Список активных тендеров | `https://bidzaar.com/api/process/light/procedures/available` | GET |
| Детали тендера (позиции) | `.../procedures/read/{id}/versions/{version_id}/positions` | GET |
| Скачивание файла | `https://bidzaar.com/api/filestorage/files/download/{file_id}` | GET |
| Карточка для людей | `https://bidzaar.com/process/light/{id}` | — |

- **Параметры списка**: `paging.page`, `paging.size=25`, `sorting.key=publishDate&direction=desc`, фильтры `status in [1]`, `procedureType eq 1`.
- **Заголовки**: `Authorization: Bearer <JWT>` (срок 1 час) + `x-user-companyid` (второй uuid из cookie `x-company-id` после `%3B`).
- **Объёмы**: ~2700–2900 активных; комфортно ~1 запрос/сек (`RATE_LIMIT_SECONDS = 1.0`).

## Internal Interfaces (CLI)

### b2bcenter-scout
- `python fetch_list.py [--section commercial|fz223] [--limit N] [--full] [--search "<kw>"] [--search-file search_queries.yaml]`
- `python prefilter.py` — простановка score.
- `python export_for_review.py` → `data/score100_tenders.txt`, `data/all_tenders.txt`.
- `python login.py` — Playwright-логин → `auth/auth_state.json`.
- `python recon_card.py <id> | --top N` → `data/recon/<id>.{html,report.json}`.
- `python reset_search.py` — удалить search-тендеры.

### bidzaar-scout
- `python fetch_list.py [--full]` — синк (через `auth.py`).
- `python prefilter.py` — простановка score по `keywords.yaml`.
- `python export_for_review.py` → два TXT.
- `auth.py` — модуль: `get_token()`, `get_session_cookies()`.

## Data Models (SQLite, таблица `tenders`)

### b2bcenter.db
- `id` (PK, номер на площадке), `section` (`commercial`/`fz223`/`search`), `url`, `name`, `category`,
  `company_name`, `company_url`, `publish_date`, `deadline_date`,
  `search_query` (через `;`), `prefilter_score` (100/0/NULL), `prefilter_hits`,
  `first_seen`, `last_seen`.

### bidzaar.db
- `id` (PK, uuid), `number`, `name`, `company_name`, `publish_date`, `acceptance_end_date`, `finish_date`,
  `status`, `procedure_type`, `trading_type`, `delivery_addresses` (JSON), `raw_json`, `fetched_at`,
  `prefilter_score` (0/50/100), `prefilter_reason`,
  `details_fetched`, `llm_score`, `llm_verdict` (зарезервировано под День 2, сейчас NULL).

### Validation / правила score
- **B2B**: все search-тендеры → score=100 (мягкий префильтр, финальный отбор — человеком).
- **Bidzaar**: blacklist приоритетнее whitelist; сравнение по подстроке, регистронезависимо, по полю `name`.
