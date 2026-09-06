# NFR Requirements — Unit 2: Platform Adapters

## Производительность

| Требование | Метрика | Источник |
|---|---|---|
| B2B-Center: пауза между запросами | Случайная 1.5–4.0с, длинная 8–15с (p=0.15) | descriptor.yaml, BR-C04 |
| Bidzaar: пауза между страницами API | `rate_limit_sec` из descriptor (1.0с) | BR-B06 |
| Playwright launch | Однократно per auth attempt, headless=True | business-logic-model.md §1 |
| httpx timeout | 30с для B2B-Center страниц и Bidzaar API | — |
| Playwright page load timeout | 30 000ms (`wait_until="domcontentloaded"`) | business-logic-model.md §1 |

## Масштабируемость

- Добавление новой площадки = новый файл-адаптер + descriptor.yaml + queries.yaml (если нужен поиск). Ядро (Unit 1) не меняется.
- Адаптеры не имеют состояния между запусками — каждый cron-запуск создаёт свежие экземпляры.

## Безопасность (Security Baseline — блокирующие правила)

| Правило | Применение к Unit 2 |
|---|---|
| SECURITY-01 (Encryption in transit) | httpx использует HTTPS для всех запросов (Bidzaar API, B2B-Center). Нет `verify=False`. |
| SECURITY-03 (No secrets in logs) | `core.logging.get_logger()` + JsonFormatter с sanitization. Playwright-логи на уровне WARNING+ (без dump cookies). |
| SECURITY-10 (Pinned dependencies) | playwright, httpx, beautifulsoup4 — точные версии в requirements.txt |
| SECURITY-12 (No hardcoded credentials) | Все учётные данные только из `PlatformCredentials` → `.env`. Никаких констант в коде адаптеров. |
| SECURITY-13 (Safe deserialization) | `json.loads()` для API-ответов Bidzaar. `BeautifulSoup(html, "html.parser")` — безопасный парсер (не `lxml` с SSRF-рисками). Нет `pickle`, нет `eval`. |
| SECURITY-15 (Error handling / fail closed) | Playwright браузер закрывается в `finally` (context manager). httpx-клиент создаётся с `with`. |

**State-файлы Bidzaar** (`data/bidzaar_state.json`, `data/bidzaar_token.json`):
- Пути задаются в `descriptor.yaml` — не хардкодятся.
- Файлы содержат сессионные cookies и JWT — добавить в `.gitignore`.
- State-файлы **не содержат** паролей — только токены, полученные после аутентификации.

**SECURITY N/A для Unit 2**: SECURITY-02 (нет LB), SECURITY-04 (нет HTTP-сервера), SECURITY-06 (нет IAM), SECURITY-07 (нет VPC), SECURITY-08 (нет эндпоинтов), SECURITY-09 (нет web-сервера), SECURITY-11 (адаптеры — не self-contained приложение), SECURITY-14 (алертинг — Unit 4).

## Надёжность

- **Playwright failure** → `AuthError` → CollectionService ловит как non-retryable, платформа помечается `auth_error`
- **HTTP 5xx / timeout** → `httpx.HTTPStatusError` / `httpx.TimeoutException` → retryable, CollectionService retry 3×
- **ParseError (B2B-Center HTML)** → retryable exception → после 3 попыток платформа пропускается
- **Браузер всегда закрывается**: `with sync_playwright() as p` + `try/finally` внутри

## Тестирование (PBT — Hypothesis)

PBT-09 (фреймворк): Hypothesis уже выбран в Unit 1, используется и здесь.

PBT-01 свойства (из domain-entities.md):

| Компонент | Свойство | Категория |
|---|---|---|
| `BidzaarAdapter.map_to_tender` | Детерминизм (тот же RawTender → тот же TenderModel) | Idempotence |
| `B2BCenterAdapter.map_to_tender` | Детерминизм | Idempotence |
| `parse_price` | Валидные строки → Decimal ≥ 0 | Invariant |
| `parse_price` | round-trip: parse(format(x)) ≈ x | Round-trip |
| `parse_deadline` | Валидные строки → datetime без исключений | Invariant |
| Tender ID | Всегда `{platform}_{external_id}` | Invariant |

## .gitignore — дополнить

```gitignore
# Bidzaar Playwright session files (contain auth tokens)
data/bidzaar_state.json
data/bidzaar_token.json
data/
```
