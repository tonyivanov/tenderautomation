# NFR Requirements — Unit 1: Core Library

## Производительность

| Требование | Метрика | Обоснование |
|---|---|---|
| Полный цикл pipeline | < 30 мин | NFR-03 (требования проекта) |
| Batch scoring (Tier 1) | ≥ 1000 тендеров/цикл без деградации | B2B-Center может давать большие выдачи |
| Запись в JSONL | O(1) на запись (append, без rewrite) | BR-16 (append-only) |
| DB-запросы | Индексы на `(platform, status)`, `(platform, collected_at)` | Запросы по статусу и дате — основные паттерны |
| Загрузка YAML-конфига | < 100ms | Загружается при каждом запуске cron |

## Масштабируемость

- **Текущая нагрузка**: 2 площадки, ~150–200 новых тендеров/день
- **Целевой горизонт**: до 5 площадок за 1–3 месяца (NFR-01)
- **Горизонтальное масштабирование**: не требуется (единственный VPS, cron-процесс)
- **Расширяемость**: добавление площадки = новый адаптер + дескриптор, без изменений в Core (FR-02)

## Доступность

- **Pipeline-процесс**: нет требований к HA. Cron на Linux VPS — стандартная надёжность OS-планировщика.
- **Изоляция сбоев**: сбой одной площадки не останавливает pipeline (BR-12)
- **Потеря цикла**: если cron-задача не запустилась — следующий запуск подберёт тендеры инкрементально (маркер `last_success_at` в `collection_runs`)

## Безопасность (Security Baseline — все правила блокирующие)

| Правило | Применение к Core Library |
|---|---|
| SECURITY-01 (Encryption at rest/transit) | PostgreSQL: TLS-соединение обязательно (`sslmode=require`). JSONL-файлы на зашифрованном разделе VPS или шифрование средствами ОС |
| SECURITY-03 (Application logging) | Лог-записи не содержат: пароли, токены, cookies, PII специалистов. Формат: JSON с полями `timestamp`, `level`, `message`, `context`. Вывод в stdout (systemd journald подхватит) |
| SECURITY-10 (Supply chain) | Точные версии в `pyproject.toml` / `requirements.txt`. Lock-файл (`pip freeze`) в репозитории. Зависимостей должно быть минимально |
| SECURITY-12 (No hardcoded credentials) | Учётные данные только в `.env`. Проверка наличия нужных переменных при старте — аварийное завершение если отсутствуют |
| SECURITY-13 (Deserialization) | JSONL-парсинг только через `json.loads()`. `pickle` запрещён. YAML-конфиг: только `yaml.safe_load()` |
| SECURITY-15 (Error handling / fail closed) | DB-соединения освобождаются в `finally`-блоках или через context manager. При ошибке — откат транзакции, не утечка соединения |

SECURITY-02 (Load balancer logging), SECURITY-04 (HTTP headers), SECURITY-06 (IAM), SECURITY-07 (Network) — **N/A** для Core Library (нет сетевых эндпоинтов, нет IAM).

SECURITY-08 (App-level access control) — **N/A** для Core (нет HTTP-эндпоинтов, это backend-библиотека).

## Надёжность

- **Retry**: 3 попытки, exponential backoff 1s/2s/4s (BR-13)
- **Connection pool**: SQLAlchemy `pool_size=5`, `max_overflow=2`, `pool_timeout=30`. Обязательный context manager для сессий
- **JSONL-запись**: `file.write(line + '\n')` + `file.flush()` + `os.fsync()` после каждого пакета — атомарная видимость записей
- **Нет глобального состояния**: каждый cron-запуск — новый процесс, новый экземпляр всех объектов

## Сопровождаемость

- **Type hints**: все публичные методы аннотированы. mypy в CI
- **Docstrings**: только для публичных методов с неочевидным контрактом (не для каждого метода)
- **PBT (Hypothesis)**: тестируемые свойства согласно PBT-01 (см. domain-entities.md)
- **Тестовое покрытие**: ≥ 80% для QualificationEngine, TenderRepository; 100% для бизнес-правил статусной машины
- **JSONL-ротация**: ежемесячная. Формат имени: `tenders_YYYY-MM.jsonl`, `actions_YYYY-MM.jsonl`. Чтение охватывает все файлы по паттерну

## Мониторинг и наблюдаемость

- **Оператор**: проверяет логи на диске при необходимости (Q6:A). Лог cron-задачи → stdout → systemd journal
- **Таблица `collection_runs`**: каждый запуск записывает статус, количество тендеров, ошибки — основной audit trail для диагностики
- **Нет realtime-алертинга** из Core: ошибки сбора видны через `collection_runs.status = 'failed'`. Telegram-алерты — зона Unit 4, не Core
- **Логи**: уровни DEBUG/INFO/WARNING/ERROR. Production: WARNING+

## Sync/Async стратегия

- **Core Library**: полностью **синхронный** (Q5:C)
  - Cron-скрипт: native sync
  - SQLAlchemy: sync engine + psycopg2
- **Unit 3 (FastAPI)**: оборачивает Core в `asyncio.get_event_loop().run_in_executor()` или `anyio.to_thread.run_sync()`
- **Обоснование**: pipeline-логика линейная и CPU-bound (скоринг), async не даёт выигрыша; sync проще тестировать PBT
