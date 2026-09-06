# NFR Requirements Plan — Unit 2: Platform Adapters

## Статус выполнения

- [x] Шаг 1: Ответы получены и проанализированы
- [x] Шаг 2: nfr-requirements.md
- [x] Шаг 3: tech-stack-decisions.md

---

## Унаследовано из Unit 1 (вопросы не нужны)

| Область | Решение |
|---|---|
| Retry / backoff | 3×, 1s/2s/4s — в CollectionService (Unit 1) |
| Credentials | Только из `.env` / `PlatformCredentials` |
| Logs | Без секретов, JSON formatter из `core.logging` |
| PBT framework | Hypothesis (уже в requirements-dev.txt) |
| Security Baseline | SECURITY-01–15 (блокирующие) |

---

## Уточняющие вопросы

### Q1: HTTP-клиент для B2B-Center (HTML-скрейпинг)
Существующий код B2B-Center использует `httpx`, Bidzaar — `requests`. Для нового Unit 2:

A) `httpx` для B2B-Center — современный, sync+async, уже в экосистеме
B) `requests` для B2B-Center — проще, однородно с тем что было в Bidzaar, sync-only (достаточно)
C) `httpx` для обоих (и Bidzaar HTTP-запросов вне Playwright) — единый клиент
X) Другое (опишите после [Answer]:)

[Answer]: C

---

### Q2: Хранение Playwright state-файлов
Где хранить `bidzaar_state.json` и `bidzaar_token.json` (Playwright сессия)?

A) `data/` в корне проекта — рядом с JSONL-логами, gitignored
B) Отдельная директория `playwright_state/` в корне
C) Путь настраивается в `descriptor.yaml` (уже так спроектировано — `data/bidzaar_state.json`)
X) Другое (опишите после [Answer]:)

[Answer]: C
