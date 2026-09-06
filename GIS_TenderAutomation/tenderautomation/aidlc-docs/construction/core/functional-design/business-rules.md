# Business Rules — Unit 1: Core Library

## Идентификация тендеров

**BR-01**: Внутренний ID тендера формируется как `{platform}_{external_id}`, где `platform` — нижний регистр без спецсимволов (например `bidzaar`, `b2bcenter`).

**BR-02**: Пара `(platform, external_id)` уникальна в системе. Дубликаты обрабатываются через upsert, а не insert.

**BR-03**: `content_hash` вычисляется от нормализованных полей: `title`, `buyer`, `budget`, `deadline`, `description`. Поля `raw_data`, `url`, `collected_at`, `status` в хеш не входят.

---

## Квалификация и скоринг

**BR-04**: Blacklist имеет абсолютный приоритет. Единственное совпадение с правилом `weight < 0` → `score = 0`, дальнейший обход правил прекращается.

**BR-05**: `prefilter_score` всегда ≥ 0.

**BR-06**: Порог квалификации (`threshold`) задаётся в `filters/config.yaml`. Значение по умолчанию — 50. Изменение threshold без перезапуска сервиса применяется к следующему циклу квалификации.

**BR-07**: Тендер со `score ≥ threshold` получает статус `qualified`, со `score < threshold` — `filtered`.

**BR-08**: Повторный сбор и upsert NOT сбрасывает квалификацию. Статус `qualified` или `filtered` сохраняется при обновлении контентных полей. Повторная квалификация — явная операция.

---

## Статусная машина

**BR-09**: Допустимые переходы статуса:
- `pending → qualified` (после score_tier1 ≥ threshold)
- `pending → filtered` (после score_tier1 < threshold)
- `qualified → in_review` (специалист открывает карточку)
- `in_review → taken | rejected | deferred`
- `deferred → in_review` (специалист возвращается)

**BR-10**: Переход `filtered → qualified` без повторной квалификации запрещён. Любой переход назад кроме `deferred → in_review` запрещён.

**BR-11**: Статус `taken`, `rejected`, `deferred` устанавливается только специалистом через явное действие с записью в `TenderAction`.

---

## Сбор и retry

**BR-12**: Ошибка сбора с одной площадки не прерывает pipeline — cбор продолжается для остальных площадок.

**BR-13**: Retry выполняется до 3 раз с exponential backoff (1с, 2с, 4с) только для transient-ошибок (сеть, HTTP 5xx).

**BR-14**: Ошибки аутентификации (HTTP 401, 403, `AuthError`) — не retryable. Площадка помечается как `auth_error` и пропускается.

**BR-15**: После исчерпания retry площадка пропускается, `CollectionRun.status = 'failed'`, ошибка логируется. Telegram-оповещение об ошибке сбора — зона ответственности Unit 4 (Notification Service), не Core.

---

## Хранилище и логи

**BR-16**: JSONL-файлы (`tenders.jsonl`, `actions.jsonl`) — append-only. Удаление и модификация строк запрещены из кода приложения.

**BR-17**: Каждая строка JSONL — валидный JSON (не массив, не объект верхнего уровня с вложением). Кодировка UTF-8.

**BR-18**: `budget` сериализуется как строка с двумя знаками после запятой (избегаем float-проблем при round-trip).

**BR-19**: Все datetime в JSONL — ISO 8601, UTC (`Z`-суффикс).

**BR-20**: В JSONL-лог квалифицированных тендеров (`tenders.jsonl`) попадают только тендеры с `qualification_tier = 'qualified'`. Отфильтрованные (`filtered`) не экспортируются.

---

## Конфигурация и секреты

**BR-21**: Учётные данные площадок хранятся только в `.env`. Они никогда не сохраняются в БД, не логируются, не попадают в JSONL.

**BR-22**: `QualificationConfig` загружается из файла при каждом запуске pipeline. Кэширование в памяти между запусками не используется (cron = новый процесс каждый раз).

---

## PBT-01: Compliance Summary

Согласно правилу PBT-01, для каждого компонента с бизнес-логикой определены тестируемые свойства:

| Компонент | Свойство | Категория PBT | Статус |
|---|---|---|---|
| `content_hash` | Детерминизм: те же поля → тот же хеш | Invariant | Идентифицировано |
| `content_hash` | Разные поля → разный хеш | Invariant | Идентифицировано |
| `QualificationEngine.score_tier1` | score ≥ 0 всегда | Invariant | Идентифицировано |
| `QualificationEngine.score_tier1` | blacklist match → score == 0 | Invariant | Идентифицировано |
| `QualificationEngine.score_tier1` | Детерминизм (те же rules+tender → тот же score) | Idempotence | Идентифицировано |
| `TenderRepository.save_batch` | Двойной вызов с одинаковыми тендерами → new_count=0 вторая раз | Idempotence | Идентифицировано |
| `QualifiedLogRepository` | Tender → JSONL-строка → parse → те же поля | Round-trip | Идентифицировано |
| `TenderStatus` | Только допустимые переходы принимаются | Invariant | Идентифицировано |
