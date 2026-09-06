# Unit of Work Plan — TenderAutomation

## Статус выполнения

- [x] Шаг 1: Ответы получены и проанализированы
- [x] Шаг 2: unit-of-work.md — определения и ответственности unit'ов
- [x] Шаг 3: unit-of-work-dependency.md — матрица зависимостей
- [x] Шаг 4: unit-of-work-story-map.md — маппинг историй на unit'ы
- [x] Шаг 5: Валидация: все истории покрыты, границы консистентны

---

## Зафиксированная декомпозиция (из Application Design)

4 unit'а в монорепо `src/`:

| # | Unit | Пакет | Ключевые компоненты |
|---|---|---|---|
| 1 | **Core Library** | `src/core/` | TenderModel, PlatformAdapter ABC, QualificationEngine, Repositories, EventBus, Services |
| 2 | **Platform Adapters** | `src/adapters/` | B2BCenterAdapter, BidzaarAdapter, AdapterRegistry |
| 3 | **Web Application** | `src/web/` | FastAPI app, SessionAuth, Routers, ExportService, Jinja2 templates |
| 4 | **Notification Service** | `src/notifications/` | TelegramNotifier, EmailDigest, NotificationHandler |

Последовательность: Unit 1 → Unit 2 → Unit 3 → Unit 4

---

## Уточняющие вопросы

### Q1: Адаптеры площадок — один unit или два?
Unit 2 объединяет B2BCenterAdapter и BidzaarAdapter в один пакет `src/adapters/`.
Стоит ли трактовать их как один общий unit или два независимо разрабатываемых?

A) Один unit «Platform Adapters» — разрабатываются вместе, один Code Generation цикл
B) Два отдельных sub-unit'а — каждый адаптер проходит Functional Design и Code Generation независимо
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q2: Параллельность разработки после Unit 1
После завершения Unit 1 (Core Library), какой порядок разработки Unit 2, 3, 4?

A) Строго последовательно: 1 → 2 → 3 → 4 (проще для одного разработчика)
B) Unit 2 и Unit 4 параллельно после Unit 1, затем Unit 3 (Unit 3 зависит от Core, не от Adapters)
C) Все три параллельно после Unit 1 (максимальная скорость, если команда)
X) Другое (опишите после [Answer]:)

[Answer]: A

---

# Текущая итерация — Export Integrity

## План декомпозиции

- [x] Загрузить утверждённые requirements, execution plan и Application Design.
- [x] Определить затронутые существующие пакеты и критический dependency path.
- [x] Получить и проверить ответы Q3-Q6 ниже.
- [x] Обновить `unit-of-work.md` определениями и ответственностями текущих units.
- [x] Обновить `unit-of-work-dependency.md` dependency matrix и sequencing.
- [x] Обновить `unit-of-work-story-map.md` mapping требований и acceptance criteria.
- [x] Проверить отсутствие непокрытых требований и циклических зависимостей.
- [x] Проверить Security/PBT ownership по units.
- [x] Валидировать все артефакты и отметить каждый шаг выполненным.

## Вопросы декомпозиции

### Q3: Группировка работы
Как оформить три уже утверждённых блока Core, Adapters и Web/export?

A) Как три последовательных Unit of Work с отдельными design/code checkpoints;
это сохраняет зависимости и упрощает ревью риска (рекомендуется)

B) Как один Unit of Work «Export Integrity» с тремя внутренними модулями

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A

### Q4: Владение и координация
Какая модель команды должна определять последовательность units?

A) Один владелец/ветка с последовательной реализацией Core → Adapters → Web;
интеграция проверяется после каждого блока (рекомендуется)

B) Разные владельцы для Core, B2B-Center, Bidzaar и Web с параллельной работой

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A

### Q5: Граница поставки
Как поставлять эти units?

A) В одной итерации и одном Merge Request, с логическими commit boundaries и
единой финальной миграцией/проверкой совместимости (рекомендуется)

B) Отдельный Merge Request на каждый unit с промежуточными deployments

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A

### Q6: Deployment boundary
Должны ли units оставаться модулями одного FastAPI/pipeline image?

A) Да; не создавать независимо развёртываемые сервисы и новую инфраструктуру
(рекомендуется)

B) Выделить readiness/inspection в отдельный deployable service

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A

## Утверждаемый подход к генерации

- Создать три последовательных Unit of Work: **Core Contracts & Persistence**,
  **Platform Inspection**, **Async Export & Packaging**.
- Реализовывать их одним владельцем в одной ветке строго по зависимости
  Core → Adapters → Web.
- Поставлять одной итерацией и одним Merge Request, сохраняя логические commit
  boundaries и проверки после каждого unit.
- Оставить все units модулями одного существующего FastAPI/pipeline image; не
  создавать новый service или инфраструктуру.
- Notifications не входит в текущую декомпозицию.
- Каждый requirement FR-01–FR-08, NFR-01–NFR-05 и каждый acceptance criterion
  должен получить владельца в `unit-of-work-story-map.md`.
- Security ownership: Core владеет normalized/fail-closed state, Adapters — safe
  external I/O, Web — auth/input/error/prompt integrity.
- PBT ownership: Core — state/idempotency, Adapters — normalization invariants,
  Web — JSONL/hash/ZIP round-trip and member invariants.
