# TenderAutomation

TenderAutomation собирает тендеры с B2B-Center и Bidzaar, сохраняет их в PostgreSQL,
выполняет детерминированную квалификацию и дополнительную LLM-классификацию, показывает
результаты в защищённом веб-интерфейсе и уведомляет о новых подходящих тендерах.

Проект разработан по AI-DLC. Требования, архитектурные решения, планы реализации и
результаты проверок находятся в [`aidlc-docs/`](aidlc-docs/).

## Возможности

- Сбор с B2B-Center двумя независимыми способами:
  - HTTP endpoint ленты рекомендаций;
  - Playwright-поиск по настроенным поисковым запросам.
- Объединение и дедупликация результатов B2B-Center по идентификатору лота. Если один
  транспорт временно недоступен, второй продолжает работу.
- Сбор с публичного integrator API Bidzaar без логина.
- Инкрементальная загрузка и повторные попытки при временных сетевых ошибках.
  Просроченные процедуры сохраняются и автоматически показываются во вкладке `Архив`.
- Строгое извлечение дедлайна из структурированных данных, а при его отсутствии —
  из явно подписанного поля на странице тендера. Дата без времени означает конец
  локального дня площадки (`23:59:59`).
- Хранение тендеров, пользователей, сессий, истории сборов и действий в PostgreSQL.
- Детерминированная квалификация по правилам и ключевым словам из `filters/`.
- Двухпроходная LLM-классификация V3 с кэшем, моделью-судьёй и очередями
  `P1`, `P2`, `P3`, `reject`.
- Углублённый анализ отдельного тендера через DeepSeek с чтением страницы площадки и,
  для Bidzaar, использованием приватной браузерной сессии.
- Веб-интерфейс со списком, поиском, историей, карточкой тендера, ручными действиями,
  LLM-оценкой, экспортом JSONL/ZIP и административным запуском сбора.
- Telegram-оповещения о новых квалифицированных тендерах.
- Отдельная SMTP-рассылка периодического email-дайджеста.
- Unit/property tests, strict mypy, Bandit, pip-audit, Gitleaks и Docker smoke test в CI.
  Суммарное line coverage всего production-кода в `src/` не может быть ниже 60%.

## Как проходит обработка

```text
B2B-Center endpoint ─┐
B2B-Center Playwright├─> дедупликация ─┐
Bidzaar API ─────────┘                  ├─> PostgreSQL
                                      ├─> rule-based квалификация
                                      ├─> JSONL qualified log
                                      ├─> Telegram event
                                      └─> LLM V3 classification ─> SQLite cache ─> Web UI
```

Основная команда `run-pipeline` выполняет этапы последовательно:

1. Опрашивает B2B-Center и Bidzaar.
2. Сохраняет новые и обновлённые тендеры в PostgreSQL.
3. Квалифицирует записи со статусом `pending` по правилам из `filters/`.
4. Дописывает квалифицированные записи в ежемесячный файл
   `data/tenders_YYYY-MM.jsonl`.
5. Если появились новые квалифицированные тендеры, публикует событие для Telegram.
6. Передаёт ещё не закэшированные тендеры в LLM-классификацию V3.

Сбор из административной панели запускает только шаги 1–4. LLM V3 и Telegram подключены
к CLI-запуску, который используется также сервисом `pipeline-cron`.

## Требования

- Python 3.10 или новее; для локальной разработки и CI рекомендуется Python 3.12.
- Docker с Compose plugin для PostgreSQL и smoke test.
- Chromium для Playwright.
- Доступ к площадкам и, при необходимости, API-ключи LLM/Telegram/SMTP.

## Быстрый локальный запуск

Создайте окружение и установите зависимости:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m playwright install chromium
```

Создайте локальную конфигурацию:

```bash
cp .env.example .env
```

Минимальная конфигурация для локального запуска:

```dotenv
DATABASE_URL=postgresql://tender_user:dev_password@localhost:5432/tender_db?sslmode=disable
B2BCENTER_USERNAME=user@example.com
B2BCENTER_PASSWORD=change-me
```

Файл `.env` игнорируется Git. Не коммитьте пароли, API-ключи, cookies, JWT и файлы
браузерных сессий.

Запустите PostgreSQL и примените миграции:

```bash
docker compose up -d postgres
PYTHONPATH=src .venv/bin/alembic upgrade head
```

Создайте пользователя веб-интерфейса:

```bash
PYTHONPATH=src .venv/bin/python -m web.cli add-user \
  --username admin@example.com \
  --role admin
```

Пароль будет запрошен интерактивно. Доступные роли: `analyst`, `manager`, `admin`.

Запустите веб-приложение:

```bash
PYTHONPATH=src .venv/bin/uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
```

После этого откройте `http://127.0.0.1:8000/login`.

## Подключение площадок

### B2B-Center: endpoint и Playwright

Оба режима включены в `src/adapters/b2bcenter/descriptor.yaml`:

```yaml
fetch_modes:
  - endpoint
  - playwright
```

Для полноценного live-сбора сохраните авторизованную браузерную сессию:

```bash
PYTHONPATH=src .venv/bin/python scripts/b2bcenter_login.py
```

Скрипт откроет видимый Chromium. Войдите в B2B-Center вручную и нажмите Enter в
терминале. Состояние будет сохранено в `data/b2bcenter_state.json`, после чего скрипт
проверит реальный endpoint.

Endpoint использует cookies этой сессии. Playwright запускает headless Chromium и
обходит запросы из `src/adapters/b2bcenter/queries.yaml`. Частоты запросов и паузы
настраиваются в descriptor; уменьшать их без необходимости не рекомендуется из-за CAPTCHA
и ограничений площадки.

Чтобы временно диагностировать только один транспорт, оставьте в `fetch_modes` только
`endpoint` или только `playwright`. В штатной конфигурации должны оставаться оба режима.

### Bidzaar

Список тендеров загружается с публичного integrator endpoint. Логин и пароль для обычного
сбора не нужны.

Приватная сессия требуется только для углублённого анализа и доступа к закрытым
вложениям:

```bash
PYTHONPATH=src .venv/bin/python scripts/bidzaar_login.py
```

Скрипт создаёт:

- `data/bidzaar_state.json` — cookies и browser storage;
- `data/bidzaar_token.json` — JWT и время его истечения.

Эти файлы являются секретами, игнорируются Git и при истечении сессии должны быть
пересозданы.

## Запуск pipeline

Полный live pipeline:

```bash
PYTHONPATH=src .venv/bin/python -m core.cli run-pipeline
```

После editable-установки доступен эквивалентный console script:

```bash
tender-pipeline run-pipeline
```

Команда делает реальные запросы к площадкам, изменяет PostgreSQL, может вызывать платные
LLM API и отправлять Telegram-сообщения. Для первой проверки без LLM и Telegram можно
явно переопределить необязательные секреты пустыми значениями:

```bash
GROQ_API_KEY='' \
DEEPSEEK_API_KEY='' \
OPENROUTER_API_KEY='' \
GEMINI_API_KEY='' \
TELEGRAM_BOT_TOKEN='' \
TELEGRAM_CHAT_IDS='' \
PYTHONPATH=src .venv/bin/python -m core.cli run-pipeline
```

Отдельной команды read-only/dry-run сейчас нет: даже запуск без LLM и Telegram сохраняет
результаты сбора и квалификации в локальную БД.

## Как используются LLM

### Детерминированный фильтр перед LLM

Сначала `QualificationEngine` применяет YAML-правила из `filters/`. Это воспроизводимый
этап без внешних API. Он назначает score и категории `qualified`, `in_review` или
`filtered`. Конфигурация семантического профиля используется также при экспорте набора
`JSONL + AGENTS.md` для ручного анализа любым AI-агентом.

### Автоматическая классификация V3

После основного pipeline V3 получает все тендеры, для которых ещё нет записи в локальном
SQLite-кэше `data/cache/llm_classification_v3.db`.

Первый проход классифицирует заголовки пакетами. Текущий waterfall провайдеров:

1. Groq, модель `qwen/qwen3-32b`, если задан `GROQ_API_KEY`.
2. DeepSeek, модель `deepseek-chat`, если задан `DEEPSEEK_API_KEY`.
3. OpenRouter, если задан `OPENROUTER_API_KEY`.

Если провайдер недоступен, pipeline пробует следующий. Ошибка отдельного LLM-пакета не
отменяет уже выполненный сбор; элементы получают безопасную оценку `review`, а ошибка
фиксируется в журнале.

Второй проход — judge — выполняется только для неоднозначных случаев: низкая уверенность,
вердикт `review`, конфликт с rule-based оценкой, смешанный тип закупки или специальные
risk flags. Для judge применяется тот же waterfall, но отдельный системный prompt.

Результаты двух проходов агрегируются в:

- `P1` — наиболее релевантные и уверенные инфраструктурные услуги;
- `P2` — ручная проверка, неоднозначность или расхождение классификаторов;
- `P3` — воспроизводимая контрольная выборка из отклонённых тендеров;
- `reject` — нерелевантные тендеры.

Prompts находятся в `prompts/`. Ключ кэша зависит от нормализованного заголовка, версии
prompt и основной модели. Изменение `PROMPT_VERSION` или модели создаёт новую область
кэша и приводит к повторной классификации.

Основные переменные LLM:

| Переменная | Назначение |
|---|---|
| `GROQ_API_KEY` | Первый backend автоматической V3-классификации |
| `DEEPSEEK_API_KEY` | Второй backend V3 и обязательный ключ deep analysis |
| `OPENROUTER_API_KEY` | Третий backend V3 |
| `OPENROUTER_MODEL_PRIMARY` | Основная модель OpenRouter, по умолчанию `openai/gpt-4o-mini` |
| `OPENROUTER_MODEL_JUDGE` | Judge-модель OpenRouter, по умолчанию `anthropic/claude-3.5-haiku` |
| `OPENROUTER_MODEL_FALLBACKS` | Дополнительные OpenRouter-модели через запятую |
| `LLM_BATCH_SIZE` | Размер пакета, по умолчанию `20` |
| `PROMPT_VERSION` | Версия prompt, входящая в ключ кэша |

В репозитории есть экспериментальный Gemini-клиент и переменная `GEMINI_API_KEY`, но
Gemini в текущий автоматический waterfall `ScoringV3Pipeline` не включён.
`OPENROUTER_DAILY_BUDGET` и `OPENROUTER_MAX_CONCURRENCY` загружаются конфигурацией, но
в текущем pipeline не являются принудительными runtime-ограничителями. Контроль расходов
следует настроить также на стороне провайдера.

### Углублённый анализ

Кнопка deep analysis в карточке тендера:

1. Загружает текст страницы площадки.
2. Для Bidzaar пытается использовать сохранённую приватную сессию и вложения.
3. Отправляет собранный контекст напрямую в `deepseek-chat`.
4. Сохраняет tier и обоснование в истории действий PostgreSQL.

Для этого сценария обязателен `DEEPSEEK_API_KEY`. Это отдельный live-вызов и он не
использует кэш пакетной V3-классификации.

## Telegram

Создайте Telegram-бота, добавьте его в нужный чат и задайте:

```dotenv
TELEGRAM_BOT_TOKEN=123456:replace-with-real-token
TELEGRAM_CHAT_IDS=123456789,-1001234567890
WEB_BASE_URL=https://tenders.example.com
```

`TELEGRAM_CHAT_IDS` — список идентификаторов через запятую. `WEB_BASE_URL` необязателен;
если он задан, сообщение содержит ссылку `${WEB_BASE_URL}/tenders`.

Механизм уведомления:

1. CLI pipeline завершает rule-based квалификацию.
2. Если в текущем запуске появились новые `qualified` тендеры, публикуется событие
   `tenders_qualified`.
3. `TelegramNotifier` отправляет каждому chat ID сообщение с количеством новых тендеров
   и ссылкой на веб-интерфейс.

Если список chat ID пуст, отправка пропускается. Ошибка Telegram логируется и не прерывает
pipeline. Запуск сбора кнопкой в `/admin` сейчас не регистрирует Telegram handler; для
уведомлений используйте `run-pipeline` или production `pipeline-cron`.

Unit и smoke tests не выполняют live-вызовы Telegram. Перед production-эксплуатацией
проверьте доставку на отдельном тестовом chat ID и не выводите token в логи.

## Email-дайджест

Email не отправляется автоматически основным pipeline. Настройте SMTP:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=mailer@example.com
SMTP_PASSWORD=replace-with-app-password
SMTP_FROM=mailer@example.com
EMAIL_RECIPIENTS=user1@example.com,user2@example.com
```

Ручная отправка квалифицированных тендеров за последние 24 часа:

```bash
PYTHONPATH=src .venv/bin/python -m notifications.cli send-digest
```

Другой период:

```bash
PYTHONPATH=src .venv/bin/python -m notifications.cli send-digest --hours 48
```

Команда использует SMTP с STARTTLS.

## Веб-интерфейс

После авторизации доступны:

- `/tenders` — активные тендеры, поиск, фильтры и очереди P1/P2;
- `/tenders/{id}` — карточка, ручной статус, заметки и AI-анализ;
- `/history` — история и архив;
- `/v3` — обзор LLM-классификации;
- `/export/zip` — ZIP с JSONL и подготовленным `AGENTS.md`;
- `/admin` — история сборов и ручной запуск для пользователя с ролью `admin`.

### Архив и исправление существующих записей

Вкладка `Архив` вычисляется по дедлайну и не является workflow-статусом. Просроченный
тендер сохраняет состояние `taken`, `deferred` или `rejected`; P1/P2 его больше не
показывают, а вкладка `Все` продолжает показывать.

Администратор может запустить ограниченное исправление записей на странице `/admin`.
Операция находит тендеры без дедлайна и Bidzaar-ссылки старого формата, открывает только
канонические страницы площадок и не перезаписывает уже известный дедлайн. Размер пакета
по умолчанию 50, допустимый диапазон — 1..200.

Та же операция доступна в CLI:

```bash
PYTHONPATH=src .venv/bin/python -m core.cli reconcile-deadlines --batch-size 50
```

Повторный запуск идемпотентен. Одновременный запуск из CLI и `/admin` отклоняется через
PostgreSQL advisory lock, поэтому площадки не получают дублирующие запросы.

Сессия веб-пользователя хранится в PostgreSQL и действует 8 часов. Пароли хэшируются
bcrypt. OpenAPI/Swagger в production-приложении отключены.

## Production Docker Compose

Production stack описан в `docker-compose.server.yml` и включает PostgreSQL, миграции,
веб-приложение и периодический pipeline runner.

Минимально нужны `TENDERAUTOMATION_IMAGE`, `POSTGRES_PASSWORD` и B2B-Center credentials.
Внутренний `DATABASE_URL` Compose формирует для контейнеров автоматически. Запуск:

```bash
docker compose --env-file .env -f docker-compose.server.yml pull
docker compose --env-file .env -f docker-compose.server.yml up -d --remove-orphans
docker compose --env-file .env -f docker-compose.server.yml logs -f app pipeline-cron
```

Интервал pipeline задаётся `PIPELINE_INTERVAL_SECONDS`, по умолчанию 21600 секунд
(6 часов). Переменная `PIPELINE_CRON_SCHEDULE` присутствует в Compose, но текущий runner
использует именно интервал и цикл `sleep`.

Для B2B-Center production runner должен видеть актуальный
`/app/data/b2bcenter_state.json` в общем volume `app_data`. Передавайте сессию на сервер
по защищённому каналу и ограничьте права доступа к файлу.

Создание первого пользователя в production:

```bash
docker compose --env-file .env -f docker-compose.server.yml exec app \
  python -m web.cli add-user --username admin@example.com --role admin
```

## Проверки перед merge

Unit/property tests и coverage:

```bash
.venv/bin/python -m pytest \
  --hypothesis-seed=20260717 \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-fail-under=60
```

Порог 60% считается агрегированно по всем модулям `src/`. Unit/property tests не делают
live-вызовов площадок, LLM, Telegram или SMTP; внешние клиенты заменяются тестовыми
двойниками.

Типы, безопасность и зависимости:

```bash
.venv/bin/python -m mypy src --ignore-missing-imports
.venv/bin/python -m bandit -q -r src
.venv/bin/python -m pip_audit -r requirements.txt
.venv/bin/python -m pip check
```

Production image и изолированный smoke test:

```bash
docker build -t tenderautomation:local .
scripts/smoke_test.sh tenderautomation:local
```

Smoke test поднимает отдельный PostgreSQL, применяет Alembic migrations, создаёт
пользователя, запускает production-приложение, проверяет Chromium, login/session,
защищённые маршруты и security headers. Live-вызовы площадок, LLM, Telegram и SMTP в
smoke test намеренно не выполняются.

## Структура проекта

```text
src/adapters/       интеграции B2B-Center и Bidzaar
src/core/           модели, БД, репозитории, события и pipeline
src/notifications/  Telegram и email
src/web/            FastAPI, маршруты, шаблоны и статика
filters/            правила детерминированной квалификации
prompts/            prompts для V3 primary/judge
migrations/         Alembic migrations
scripts/            login, отчёты и smoke test
tests/              unit, property и web tests
aidlc-docs/         AI-DLC requirements, design, plans и evidence
data/               локальные логи, LLM-кэш и секретные browser states
```

## AI-DLC и внесение изменений

Для значимых изменений сохраняйте трассируемость AI-DLC:

1. Зафиксируйте требования или change request в `aidlc-docs/inception/`.
2. Обновите функциональный/NFR design и construction plan.
3. Реализуйте изменение небольшими проверяемыми инкрементами.
4. Запустите релевантные quality gates и smoke test.
5. Сохраните результаты и известные ограничения в
   `aidlc-docs/construction/build-and-test/`.

Не добавляйте в AI-DLC evidence реальные секреты или полные live-ответы площадок с
чувствительными данными.
