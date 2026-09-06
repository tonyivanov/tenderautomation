# Functional Design Plan — Unit 1: Core Library

## Статус выполнения

- [x] Шаг 1: Ответы получены и проанализированы
- [x] Шаг 2: domain-entities.md — сущности и их атрибуты
- [x] Шаг 3: business-logic-model.md — алгоритмы и процессы
- [x] Шаг 4: business-rules.md — правила валидации и ограничения
- [x] Шаг 5: Валидация PBT-01 (идентификация тестируемых свойств)

---

## Контекст Unit 1

**Покрываемые истории**: US-01◐ (инфраструктура сбора), US-02● (квалификация), US-03◐ (JSONL-генерация)

**Ключевые компоненты**: TenderModel, PlatformAdapter ABC, QualificationEngine, TenderRepository, QualifiedLogRepository, ActionLogRepository, EventBus, CollectionService, QualificationService, PipelineOrchestrator

---

## Уточняющие вопросы

Заполните [Answer]: для каждого вопроса.

---

### Q1: Унифицированный ID тендера
Как формировать внутренний `id` тендера в системе?

A) `{platform}_{external_id}` — простая конкатенация (например, `bidzaar_12345`)
B) UUID4 — генерируется при сохранении, external_id хранится отдельно
C) Hash от `platform + external_id` — детерминированный, удобен для upsert
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q2: Инкрементальный сбор — маркер «последний запуск»
Как хранить момент времени последнего успешного сбора для каждой площадки?

A) В PostgreSQL — отдельная таблица `collection_runs` (platform, last_success_at, status)
B) В файле `.last_run_{platform}.json` рядом с кодом
C) В таблице `tenders` — брать MAX(collected_at) для данной площадки
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q3: Схема keyword-фильтров (Tier 1)
Текущий `keywords.yaml` содержит whitelist/blacklist с весами. Нужно расширить формат. Какая структура предпочтительна?

A) Плоский список с полями: `term`, `weight` (+/-), `category`, `match_type` (exact/contains/regex)
B) Иерархический: группы правил → внутри каждой группы — термины + оператор (ANY/ALL/NONE)
C) Двухсекционный: `whitelist` (термины со score) + `blacklist` (термины-исключения) — близко к текущему, но с категориями
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q4: Пороговые значения скоринга
Как определяется «прошёл квалификацию» по Tier 1?

A) Фиксированный порог: score ≥ 50 → кандидат (текущий подход с 0/50/100)
B) Настраиваемый порог из конфига — без hardcode в коде
C) Любой score > 0 при наличии хотя бы одного whitelist-совпадения
X) Другое (опишите после [Answer]:)

[Answer]: B

---

### Q5: Обработка ошибок сбора
Что происходит при ошибке сбора с одной из площадок (сетевая ошибка, авторизация)?

A) Логируем ошибку, пропускаем площадку, продолжаем с остальными — сбой не блокирует pipeline
B) Retry 3 раза с exponential backoff, затем пропускаем и логируем
C) Retry 3 раза, затем всё равно пропускаем, но отправляем Telegram-оповещение об ошибке
X) Другое (опишите после [Answer]:)

[Answer]: B

---

### Q6: Дубликаты тендеров
Как обрабатывать тендер, который уже есть в БД (повторный сбор)?

A) Upsert: обновляем поля если тендер изменился (по хешу содержимого), иначе пропускаем
B) Пропускаем полностью — если external_id + platform уже есть, не трогаем запись
C) Всегда обновляем мета-поля (updated_at, raw_data), но не меняем квалификацию
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q7: Статусная машина тендера
Через какие статусы проходит тендер в системе?

A) `pending` → `qualified` / `filtered` → `in_review` → `taken` / `rejected` / `deferred`
B) `new` → `scored` → `reviewed` → `decided` (+ decision: taken/rejected/deferred)
C) Только флаги без явного статуса: `is_qualified`, `is_viewed`, `decision` (nullable)
X) Другое (опишите после [Answer]:)

[Answer]: A

---

### Q8: Формат JSONL-записи квалифицированного тендера
Какие поля включать в каждую строку JSONL-файла квалифицированных тендеров?

A) Минимум: id, platform, title, buyer, budget, deadline, url, prefilter_score, exported_at
B) Стандарт: минимум + description, qualification_tier, matched_keywords, published_at
C) Полный: стандарт + raw_data (оригинальные данные площадки в виде объекта)
X) Другое (опишите после [Answer]:)

[Answer]: B
