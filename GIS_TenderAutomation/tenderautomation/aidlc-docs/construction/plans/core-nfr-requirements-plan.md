# NFR Requirements Plan — Unit 1: Core Library

## Статус выполнения

- [x] Шаг 1: Ответы получены и проанализированы
- [x] Шаг 2: nfr-requirements.md — требования к качеству
- [x] Шаг 3: tech-stack-decisions.md — выбор библиотек и инструментов

---

## Уже зафиксировано (не требует вопросов)

| Область | Решение | Источник |
|---|---|---|
| Язык | Python 3.10+ | Текущий проект |
| База данных | PostgreSQL | Application Design Q6:C |
| Модели данных | Pydantic | Application Design components.md |
| Тестирование | pytest + Hypothesis (PBT) | NFR-05, расширение PBT включено |
| Безопасность | Security Baseline SECURITY-01–15 | Расширение Security включено |
| Формат логов | JSONL append-only | FR-04, BR-16 |
| Планировщик | System cron | Application Design Q4:A |
| Секреты | `.env` (python-dotenv или pydantic-settings) | BR-21 |

---

## Уточняющие вопросы

Заполните [Answer]: для каждого вопроса.

---

### Q1: PostgreSQL — ORM или raw SQL?
Как взаимодействовать с PostgreSQL в TenderRepository?

A) SQLAlchemy ORM — высокоуровневый, автомаппинг, миграции через Alembic
B) SQLAlchemy Core (Expression Language) — SQL без ORM, явные запросы, Alembic для миграций
C) psycopg3 (raw SQL) — минимальные зависимости, явный контроль, миграции через SQL-файлы
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q2: Миграции схемы PostgreSQL
Как управлять версиями схемы БД?

A) Alembic — стандарт для SQLAlchemy, автогенерация миграций
B) SQL-файлы вручную (`migrations/001_init.sql`, `002_add_column.sql`) — без зависимостей
C) Yoyo Migrations — легковесный, SQL-файлы, встроен в Python
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q3: Логирование pipeline
Какой фреймворк использовать для структурированного логирования?

A) Python stdlib `logging` + JSON formatter — никаких доп. зависимостей
B) `structlog` — structured logging, удобен для JSON, богатая конфигурация
C) `loguru` — простой синтаксис, rotation из коробки, хорош для CLI/cron скриптов
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q4: JSONL-файлы — ротация и размер
Как управлять ростом JSONL-файлов (`tenders.jsonl`, `actions.jsonl`)?

A) Неограниченный рост — файлы маленькие (100-150 тендеров/день × 1KB ≈ 50MB/год), ротация не нужна
B) Ротация по дате: `tenders_2026-06.jsonl` — новый файл каждый месяц
C) Ротация по размеру: при достижении N MB — переименовать и создать новый
X) Другое (опишите после [Answer]:)

[Answer]: B

---

### Q5: Async или sync для pipeline-скрипта?
Core Library используется в двух контекстах: cron-скрипт (pipeline) и веб-приложение (Unit 3). Какой подход для DB-операций в Core?

A) Синхронный (sync) — cron-скрипт не нуждается в async; Unit 3 (FastAPI) будет использовать `run_in_executor`
B) Асинхронный (async/await) — единый код для cron и FastAPI; asyncpg или SQLAlchemy async
C) Гибрид: sync-репозитории + async-обёртки для FastAPI
X) Другое (опишите после [Answer]:)

[Answer]: C

---

### Q6: Мониторинг pipeline и алертинг
Как оператор узнаёт о проблемах в pipeline (сбой сбора, ошибка квалификации)?

A) Только логи на диске — оператор проверяет при необходимости
B) Telegram-алерт при ошибке сбора (отдельно от уведомлений специалистам)
C) Запись в `collection_runs` + дашборд в веб-интерфейсе — видно в UI
X) Другое (опишите после [Answer]:)

[Answer]: A
