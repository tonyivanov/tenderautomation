# Domain Entities — Unit 2: Platform Adapters

## Платформо-специфичные сырые данные

### BidzaarRawItem
Одна запись из JSON API Bidzaar (`/api/process/light/procedures/available`).

| Поле API | Тип | Описание |
|---|---|---|
| `id` | `int` | Уникальный ID тендера на площадке |
| `name` | `str` | Название тендера |
| `organizationName` | `str \| None` | Заказчик |
| `startPrice` | `float \| None` | НМЦК |
| `finishDate` | `str \| None` | Дедлайн (ISO строка) |
| `startDate` | `str \| None` | Дата публикации |
| `description` | `str \| None` | Описание (может отсутствовать в списке) |

**Маппинг в TenderModel:**
```
id:           f"bidzaar_{item['id']}"
external_id:  str(item['id'])
platform:     "bidzaar"
title:        item['name']
buyer:        item.get('organizationName')
budget:       Decimal(str(item['startPrice'])) if startPrice else None
deadline:     datetime.fromisoformat(item['finishDate']) if finishDate else None
published_at: datetime.fromisoformat(item['startDate']) if startDate else None
url:          f"https://bidzaar.com/requests/public/{item['id']}"
description:  item.get('description')
raw_data:     dict(item)
```

---

### B2BCenterRawRow
Одна строка из HTML-таблицы листинга / поиска B2B-Center.

| Поле | Тип | Источник |
|---|---|---|
| `lot_id` | `str` | Из ссылки `/market/{id}/` |
| `title` | `str` | Текст 2-й колонки |
| `buyer` | `str \| None` | Текст 3-й колонки |
| `budget_raw` | `str \| None` | Текст колонки цены (например "1 500 000 руб.") |
| `deadline_raw` | `str \| None` | Текст колонки дедлайна (например "15.07.2026 23:59") |
| `url` | `str` | `https://www.b2b-center.ru/market/{lot_id}/` |
| `section` | `str` | `"commercial"` или `"fz223"` |
| `search_query` | `str \| None` | Ключевое слово запроса (если режим поиска) |

**Маппинг в TenderModel:**
```
id:           f"b2bcenter_{lot_id}"
external_id:  lot_id
platform:     "b2bcenter"
title:        title (stripped)
buyer:        buyer (stripped) or None
budget:       parse_price(budget_raw) → Decimal or None
deadline:     parse_deadline(deadline_raw) → datetime or None
published_at: None (не доступна в листинге)
url:          url
description:  None (не доступна в листинге — будет в recon, Unit 3+)
raw_data:     {"lot_id": ..., "section": ..., "search_query": ...}
```

---

## Дескрипторы платформ

### B2BCenterDescriptor (`src/adapters/b2bcenter/descriptor.yaml`)

```yaml
platform_id: b2bcenter
display_name: "B2B-Center"
base_url: "https://www.b2b-center.ru"
auth_method: none          # no auth for listing/search
auth_method_recon: playwright  # stub for future recon (Unit 3+)
rate_limit_sec_min: 1.5
rate_limit_sec_max: 4.0
long_pause_prob: 0.15
long_pause_sec_min: 8.0
long_pause_sec_max: 15.0
max_results_per_query: 1000   # noise protection threshold
page_size: 20
incremental_stop_after: 5
sections:
  commercial: "/market/"
  fz223: "/search-tender/zakupki/"
search_url_template: "{base_url}/market/?search={query}&from={offset}"
```

### B2BCenterQueries (`src/adapters/b2bcenter/queries.yaml`)

```yaml
# Search queries — migrated and curated from existing search_queries.yaml
queries:
  - term: "devops"
    category: cloud
  - term: "kubernetes"
    category: cloud
  - term: "мониторинг инфраструктур"
    category: infrastructure
  - term: "виртуализация"
    category: infrastructure
  # ... (полный список из существующего search_queries.yaml)
```

### BidzaarDescriptor (`src/adapters/bidzaar/descriptor.yaml`)

```yaml
platform_id: bidzaar
display_name: "Bidzaar"
base_url: "https://bidzaar.com"
auth_method: playwright_credentials
login_url: "https://bidzaar.com/auth/login"
app_url: "https://bidzaar.com/requests/public"
api_endpoint: "/api/process/light/procedures/available"
rate_limit_sec: 1.0
page_size: 25
token_expiry_buffer_sec: 60
login_timeout_sec: 60
state_file: "data/bidzaar_state.json"
token_cache_file: "data/bidzaar_token.json"
```

---

## PBT-01: Тестируемые свойства (Unit 2)

| Свойство | Категория | Компонент |
|---|---|---|
| `map_to_tender` детерминирован: те же RawTender → тот же TenderModel | Idempotence | оба адаптера |
| `map_to_tender` всегда заполняет обязательные поля: `id`, `platform`, `title`, `url` | Invariant | оба адаптера |
| `parse_price`: валидные строки → Decimal ≥ 0 | Invariant | B2BCenterAdapter |
| `parse_price`: round-trip — parse(format(x)) ≈ x | Round-trip | B2BCenterAdapter |
| `parse_deadline`: валидные строки дедлайна → datetime без исключений | Invariant | B2BCenterAdapter |
| Tender ID формат: всегда `{platform}_{external_id}` | Invariant | оба адаптера |
> Current descriptors and transport ownership are documented in
> `../current-collection-design.md`; legacy examples below are historical context.
