# EI-1 NFR Design Plan — Core Contracts & Persistence

## План

- [x] Проанализировать утверждённые Functional Design и NFR Requirements EI-1.
- [x] Проверить существующие Core, repository, V3 projection и async boundaries
  по Application Design и Graphify.
- [x] Получить и проверить ответы Q1-Q5 ниже.
- [x] Создать `nfr-design-patterns.md` с patterns для timeout/cancellation,
  bounded concurrency, transaction isolation, fail-closed и observability.
- [x] Создать `logical-components.md` с ответственностью компонентов,
  ownership ресурсов и interaction contracts.
- [x] Проверить соответствие SECURITY-01–SECURITY-15.
- [x] Проверить, что NFR Design сохраняет TP-01–TP-09 и обязательства PBT.
- [x] Валидировать согласованность NFR Design с EI-2 и EI-3 contracts.

## Оценка обязательных категорий

| Категория | Применимость | Решение |
|---|---|---|
| Resilience Patterns | Применима: есть per-operation и batch timeout | Q1 |
| Scalability Patterns | Применима: возможны concurrent requests одного tender | Q2 |
| Performance Patterns | Применима: Core async, существующие DB/SQLite API синхронные | Q3 |
| Security Patterns | Применима: inspection provenance является внешними данными | Q4 |
| Logical Components | Применима: V3 projection зависит от отдельного SQLite cache | Q5 |

## Вопросы NFR Design

### Q1: Завершение batch при общем timeout

Что делать с незавершёнными inspection tasks при достижении 120-секундного
deadline?

A) Кооперативно отменить незавершённые tasks, дождаться cleanup context managers,
сохранить уже завершённые outcomes, а отменённые вернуть как `unverified` с
безопасной категорией `batch_timeout` (рекомендуется)

B) Прекратить ожидание и оставить tasks работать в фоне после HTTP request

C) Дождаться всех tasks сверх 120 секунд, сохранив timeout только как metric

X) Другое (опишите поведение после тега [Answer]: ниже)

[Answer]: A

### Q2: Одновременная проверка одного тендера разными requests

Как разрешать гонку, если два export requests одновременно инспектируют один
tender и результаты завершаются в разном порядке?

A) Не вводить cross-request lock; применять verified result только если его
`attempted_at` не старше сохранённого успешного результата, а failure обновляет
attempt metadata только монотонно (рекомендуется)

B) Сериализовать проверки одного tender через PostgreSQL advisory lock на всё
время внешнего вызова

C) Использовать process-local registry активных inspections и переиспользовать
одну task между requests

X) Другое (опишите coordination policy после тега [Answer]: ниже)

[Answer]: A

### Q3: Синхронные PostgreSQL и SQLite операции внутри async readiness flow

Как не блокировать event loop существующими синхронными repository и
`sqlite3` вызовами?

A) Выносить ограниченные DB/V3 operations через `asyncio.to_thread`; создавать,
использовать и закрывать session/connection внутри одного worker call
(рекомендуется, без новых dependencies)

B) В рамках EI-1 перевести весь persistence слой на SQLAlchemy AsyncSession и
добавить async PostgreSQL driver

C) Вызывать синхронные repository/SQLite методы прямо из event loop

X) Другое (опишите async boundary после тега [Answer]: ниже)

[Answer]: A

### Q4: Ограничение inspection provenance

Какой контракт применить к `raw_data_updates`, чтобы внешние данные не создавали
неограниченный payload и не управляли persistence columns?

A) Разрешить только фиксированный allowlist скалярных provenance keys, не более
16 ключей и 8 KiB после JSON-сериализации; превышение считать contract violation
и возвращать `unverified` (рекомендуется)

B) Разрешить любые JSON-compatible keys с общим лимитом 64 KiB

C) Не сохранять provenance совсем, только `procedure_source` и timestamps

X) Другое (укажите allowlist/limits после тега [Answer]: ниже)

[Answer]: A

### Q5: Недоступность или повреждение V3 SQLite cache

Как классифицировать кандидатов, когда `V3ExportProjection` не может прочитать
cache?

A) Fail closed для решений, зависящих от V3: legacy `qualified` продолжает путь,
а legacy `filtered` получает `unverified` с `v3_unavailable`, но не ложный
`ineligible`; весь batch не падает (рекомендуется)

B) Считать V3 context отсутствующим: legacy `filtered` становится `ineligible`,
legacy `qualified` продолжает путь

C) Отклонить весь batch независимо от legacy qualification

X) Другое (опишите fallback после тега [Answer]: ниже)

[Answer]: A
