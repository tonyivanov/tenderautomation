# Domain Entities — Unit 1: Core Library

## Tender

Основная сущность системы. Унифицированное представление тендера вне зависимости от площадки.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `str` | `{platform}_{external_id}` (например `bidzaar_12345`, `b2bcenter_abc`) |
| `platform` | `str` | Идентификатор площадки (`bidzaar`, `b2bcenter`) |
| `external_id` | `str` | ID тендера на площадке |
| `title` | `str` | Название тендера |
| `buyer` | `str \| None` | Заказчик |
| `budget` | `Decimal \| None` | НМЦК (начальная максимальная цена контракта) |
| `deadline` | `datetime \| None` | Дедлайн подачи заявок |
| `description` | `str \| None` | Описание / предмет закупки |
| `url` | `str` | Ссылка на тендер на площадке |
| `raw_data` | `dict` | Оригинальные данные площадки (не нормализованные) |
| `content_hash` | `str` | SHA-256 от нормализованных контентных полей (для upsert) |
| `prefilter_score` | `int` | Результат Tier 1 скоринга (0 = не прошёл или в blacklist) |
| `qualification_tier` | `str \| None` | `qualified` или `filtered` (None = ещё не квалифицирован) |
| `matched_keywords` | `list[str]` | Ключевые слова, которые совпали при скоринге |
| `status` | `TenderStatus` | Текущий статус (см. ниже) |
| `published_at` | `datetime \| None` | Дата публикации на площадке |
| `collected_at` | `datetime` | Момент сбора системой |
| `updated_at` | `datetime` | Последнее обновление записи |

**Поля, покрываемые content_hash**: `title`, `buyer`, `budget`, `deadline`, `description`.
`raw_data`, `url`, `collected_at`, `updated_at` в хеш не входят.

---

## TenderStatus (enum)

Статусная машина тендера:

```
pending → qualified (score ≥ threshold)
pending → filtered  (score < threshold)

qualified → in_review (специалист открывает карточку)
in_review → taken
in_review → rejected
in_review → deferred

deferred → in_review (специалист возвращается к тендеру)
```

| Значение | Описание |
|---|---|
| `pending` | Собран, ещё не квалифицирован |
| `qualified` | Прошёл Tier 1 (score ≥ threshold) |
| `filtered` | Не прошёл Tier 1 (score < threshold) |
| `in_review` | Специалист просматривает |
| `taken` | Взят в работу |
| `rejected` | Отклонён |
| `deferred` | Отложен |

**Недопустимые переходы**: `filtered → qualified` без повторной квалификации; любой переход назад кроме `deferred → in_review`.

---

## TenderAction

Запись о действии специалиста или загруженном AI-анализе. Хранится в PostgreSQL и дублируется в JSONL (append-only).

| Поле | Тип | Описание |
|---|---|---|
| `id` | `UUID` | Первичный ключ |
| `tender_id` | `str` | FK → Tender.id |
| `action_type` | `str` | `taken` \| `rejected` \| `deferred` \| `ai_analysis` |
| `user_id` | `str` | Идентификатор специалиста |
| `notes` | `str \| None` | Заметка (макс. 500 символов) |
| `ai_tier` | `str \| None` | Эшелон AI-анализа (⭐/🟡/🟠/🔴) — только для `ai_analysis` |
| `ai_rationale` | `str \| None` | Обоснование AI-агента (макс. 2000 символов) |
| `ai_tool` | `str \| None` | Инструмент анализа (`claude.ai`, `chatgpt`, ...) |
| `created_at` | `datetime` | Момент создания записи |

---

## CollectionRun

Запись о попытке сбора тендеров с площадки.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `UUID` | Первичный ключ |
| `platform` | `str` | Идентификатор площадки |
| `started_at` | `datetime` | Начало сбора |
| `completed_at` | `datetime \| None` | Завершение (None если ещё выполняется) |
| `status` | `str` | `running` \| `success` \| `failed` \| `auth_error` |
| `new_tenders_count` | `int` | Количество новых тендеров в этом запуске |
| `updated_tenders_count` | `int` | Количество обновлённых тендеров (контент изменился) |
| `error_message` | `str \| None` | Сообщение об ошибке |
| `attempt_number` | `int` | Номер попытки (1-3 при retry) |

**Быстрый доступ к последнему успешному сбору**: `SELECT MAX(completed_at) FROM collection_runs WHERE platform=? AND status='success'`.

---

## KeywordRule

Одно правило фильтрации. Загружается из `filters/keywords.yaml`.

| Поле | Тип | Описание |
|---|---|---|
| `term` | `str` | Ключевое слово / фраза / regex-паттерн |
| `weight` | `int` | Положительный = whitelist (вес в score), отрицательный = blacklist |
| `category` | `str \| None` | Категория правила (например `cloud`, `infosec`, `exclude`) |
| `match_type` | `str` | `exact` \| `contains` \| `regex` |

---

## QualificationConfig

Параметры квалификации, загружаемые из `filters/config.yaml`.

| Поле | Тип | Описание |
|---|---|---|
| `threshold` | `int` | Минимальный score для статуса `qualified` (по умолчанию 50) |
| `rules` | `list[KeywordRule]` | Список правил фильтрации |
| `version` | `str \| None` | Версия конфига для аудита |

---

## PlatformCredentials

Учётные данные площадки. Загружается из `.env`, не хранится в БД.

| Поле | Тип | Описание |
|---|---|---|
| `platform` | `str` | Идентификатор площадки |
| `username` | `str` | Логин |
| `password` | `str` | Пароль |
| `extra` | `dict` | Дополнительные параметры (специфичны для площадки) |

---

## AuthSession

Результат аутентификации на площадке. Не персистируется.

| Поле | Тип | Описание |
|---|---|---|
| `platform` | `str` | Идентификатор площадки |
| `token` | `str \| None` | Bearer / JWT токен |
| `cookies` | `dict` | Сессионные cookies |
| `expires_at` | `datetime \| None` | Время истечения сессии |

---

## RawTender

Сырые данные с площадки до нормализации. Промежуточный объект.

| Поле | Тип | Описание |
|---|---|---|
| `platform` | `str` | Идентификатор площадки |
| `external_id` | `str` | ID на площадке |
| `raw` | `dict` | Оригинальный ответ API или спарсенные данные |

---

## PBT-01: Тестируемые свойства (Hypothesis)

| Свойство | Категория | Компонент |
|---|---|---|
| Один и тот же input → один и тот же content_hash (детерминизм) | Invariant | content_hash |
| Разные контентные поля → разный content_hash | Invariant | content_hash |
| score_tier1 ≥ 0 всегда | Invariant | QualificationEngine |
| Blacklist-совпадение → score == 0 независимо от whitelist | Invariant | QualificationEngine |
| score детерминирован (одни и те же rules + tender → тот же score) | Idempotence | QualificationEngine |
| save_batch дважды с одинаковыми тендерами → new_count=0 вторая раз | Idempotence | TenderRepository |
| Tender → JSONL-строка → parse → те же поля (round-trip) | Round-trip | QualifiedLogRepository |
| Только допустимые переходы статуса принимаются | Invariant | TenderStatus |
