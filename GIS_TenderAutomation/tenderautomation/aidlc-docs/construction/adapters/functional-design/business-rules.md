# Business Rules — Unit 2: Platform Adapters

## Общие правила (оба адаптера)

**BR-A01**: Каждый адаптер реализует `PlatformAdapter` ABC из `core.adapters.base`. Нарушение контракта → ошибка на этапе регистрации в `AdapterRegistry`.

**BR-A02**: Tender ID всегда формируется как `{platform_id}_{external_id}`. Пример: `bidzaar_12345`, `b2bcenter_9876543`.

**BR-A03**: `map_to_tender()` — синхронный метод. Не содержит HTTP-запросов, только маппинг полей.

**BR-A04**: Если обязательное поле (`title`, `url`) отсутствует в сырых данных — поднять `ValueError` (не возвращать модель с пустыми полями).

**BR-A05**: `raw_data` в TenderModel хранит оригинальный ответ площадки без изменений. Не сжимать, не удалять поля.

---

## Bidzaar

**BR-B01**: Аутентификация — исключительно через Playwright headless. Никаких HTTP-запросов напрямую к эндпоинтам авторизации (ROPC не используется).

**BR-B02**: Учётные данные (username, password) — только из `PlatformCredentials`, полученных из `Settings` (.env). Не хардкодировать.

**BR-B03**: Токен кэшируется в файл `descriptor.token_cache_file`. Файл создаётся при первом логине. Кэш считается свежим если `expires_at - 60s > now()`.

**BR-B04**: При `state_path.exists()` сначала пробуем тихое обновление (headless + существующий state). Полный логин (заполнение формы) только если тихое обновление не дало токен.

**BR-B05**: При полном автологине: таймаут ожидания токена — `descriptor.login_timeout_sec` (60с). Если за это время токен не появился — `AuthError`.

**BR-B06**: Между страницами API — пауза `descriptor.rate_limit_sec` (1.0с). Это минимальная вежливая задержка.

**BR-B07**: Инкрементальный сбор: если `since` задан и `published_at < since` для текущей записи — остановить обход (записи отсортированы по дате, старые не нужны).

**BR-B08**: Пагинация: `paging.page` начинается с 1. `paging.size = descriptor.page_size` (25). Обход продолжается пока `total_seen < totalCount` и ответ содержит `items`.

**BR-B09**: `x-user-companyid` заголовок извлекается из cookies (`x-company-id` cookie, последняя часть после `%3B`). Если отсутствует — запрос всё равно выполняется (некоторые аккаунты не имеют company).

---

## B2B-Center

**BR-C01**: Режим сбора — исключительно поиск по ключевым словам (queries.yaml). Сплошной обход секций не используется.

**BR-C02**: Аутентификация для листинга и поиска — не требуется. `authenticate()` для B2B-Center возвращает пустую `AuthSession`. Реализация recon-аутентификации — отложена на Unit 3+.

**BR-C03**: Шумовая защита: если `total_count > descriptor.max_results_per_query` (1000) — пропустить запрос, залогировать WARNING с `{"query": term, "total": total_count}`. Не прерывать обход остальных запросов.

**BR-C04**: Антибот: случайная пауза между запросами. Параметры берутся из дескриптора:
- Обычная пауза: `uniform(rate_limit_sec_min=1.5, rate_limit_sec_max=4.0)`
- Длинная пауза (p=0.15): `uniform(long_pause_sec_min=8.0, long_pause_sec_max=15.0)`

**BR-C05**: Инкрементальный стоп: если на странице подряд `incremental_stop_after` (5) записей с `lot_id`, уже известным системе (есть в `TenderRepository`) — прекратить обход этого запроса.

**BR-C06**: HTML парсинг: при изменении структуры страницы B2B-Center (селекторы не находят элементы) — поднять `ParseError` с URL и именем адаптера. Не возвращать частичные результаты.

**BR-C07**: Поле `published_at` из листинга B2B-Center недоступно — устанавливать `None`. Дата будет доступна только при recon карточки.

**BR-C08**: Бюджет "договорная" / пустой / нечисловой → `budget = None`.

**BR-C09**: Дедлайн считается в московском времени (UTC+3). При сохранении конвертировать в UTC.

**BR-C10**: User-Agent заголовок — правдоподобный браузерный UA. Без него B2B-Center возвращает 403. Значение берётся из дескриптора (или константы в адаптере).

---

## PBT-01: Compliance Summary

| Компонент | Свойство | Категория | Статус |
|---|---|---|---|
| `BidzaarAdapter.map_to_tender` | Детерминизм (один RawTender → один TenderModel) | Idempotence | Идентифицировано |
| `BidzaarAdapter.map_to_tender` | Обязательные поля всегда заполнены | Invariant | Идентифицировано |
| `B2BCenterAdapter.map_to_tender` | Детерминизм | Idempotence | Идентифицировано |
| `B2BCenterAdapter.map_to_tender` | Обязательные поля всегда заполнены | Invariant | Идентифицировано |
| `parse_price` | Валидные строки → Decimal ≥ 0 | Invariant | Идентифицировано |
| `parse_price` | Round-trip: parse(format(x)) ≈ x | Round-trip | Идентифицировано |
| `parse_deadline` | Валидные строки → datetime без исключений | Invariant | Идентифицировано |
| Tender ID | Всегда `{platform}_{external_id}` | Invariant | Идентифицировано |
> Current collection rules are superseded by
> `../current-collection-design.md`; legacy rules below are historical context.
