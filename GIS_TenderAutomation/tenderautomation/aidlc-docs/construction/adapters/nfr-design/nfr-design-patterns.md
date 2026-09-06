# NFR Design Patterns — Unit 2: Platform Adapters

## Resilience Patterns

### 1. Browser Resource Cleanup (SECURITY-15 / Fail-Safe)

**Паттерн**: Context Manager + Finally

Playwright браузер **всегда** закрывается — даже при исключении:

```python
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    try:
        context = browser.new_context(...)
        page = context.new_page()
        # ... auth logic ...
    finally:
        browser.close()  # освобождаем ресурс в любом случае
```

Если `browser.close()` сам падает — исключение проглатывается (оригинальная ошибка важнее).

---

### 2. Token Cache — Fail-Fast на устаревший кэш

**Паттерн**: Guard Clause + Early Return

```python
def _get_cached_token(cache_path: Path, buffer_sec: int = 60) -> str | None:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if data.get("expires_at", 0) - buffer_sec > time.time():
            return data["access_token"]
    except (json.JSONDecodeError, OSError, KeyError):
        pass  # повреждённый кэш → None → полный логин
    return None
```

Повреждённый или устаревший кэш → `None` → следующий шаг в цепочке (state refresh → full login). Никаких partial-state exceptions.

---

### 3. Three-Step Auth Chain (Bidzaar)

**Паттерн**: Chain of Responsibility

```
Step 1: Cached token fresh?  →  return immediately
   ↓ No
Step 2: State file exists?   →  headless refresh
   ↓ No / failed
Step 3: Full auto-login      →  fill form headless
   ↓ Failed (60s timeout)
AuthError raised → CollectionService catches, marks platform 'auth_error'
```

Каждый шаг пробует быстрый путь, падает только на медленный если нужно. Нет ручного вмешательства.

---

### 4. Noise Guard (B2B-Center)

**Паттерн**: Guard Clause before expensive work

```python
total = parse_total_count(first_page_html)
if total > descriptor.max_results_per_query:
    log.warning("noisy_query_skipped",
                extra={"context": {"query": query.term, "total": total}})
    continue  # skip this query, don't fetch all pages
```

Применяется **до** начала пагинации — не после. Экономит время и нагрузку на площадку.

---

### 5. Incremental Stop (B2B-Center)

**Паттерн**: Early Exit / Sentinel

```python
INCREMENTAL_STOP_AFTER = descriptor.incremental_stop_after  # default 5

known_streak = 0
for row in rows:
    if tender_already_in_db(row.lot_id):
        known_streak += 1
        if known_streak >= INCREMENTAL_STOP_AFTER:
            return results  # достигли старых данных
    else:
        known_streak = 0
        results.append(map_row_to_raw(row))
```

Останавливает обход когда N подряд идущих строк уже известны — сигнал что дальше только старые записи.

---

## Security Patterns

### 6. HTTPS Enforcement (SECURITY-01)

httpx по умолчанию проверяет SSL-сертификаты. Явный запрет `verify=False`:

```python
# ПРАВИЛЬНО:
client = httpx.Client(timeout=30.0)  # SSL verification ON by default

# ЗАПРЕЩЕНО:
client = httpx.Client(verify=False)  # никогда не использовать
```

---

### 7. Safe HTML Parser (SECURITY-13)

```python
# ПРАВИЛЬНО: встроенный html.parser
soup = BeautifulSoup(response.text, "html.parser")

# ЗАПРЕЩЕНО: lxml с внешним контентом (потенциальный SSRF)
soup = BeautifulSoup(response.text, "lxml")
```

`html.parser` — встроенный Python, не требует C-зависимостей, безопасен для внешнего HTML.

---

### 8. State File Isolation

**Паттерн**: Externalized Secrets Storage

State-файлы (JWT-токены, cookies) хранятся **за пределами репозитория**:
- Путь задаётся в `descriptor.yaml` (например `data/bidzaar_state.json`)
- `data/` добавлен в `.gitignore`
- Никогда не логируются (JsonFormatter маскирует `token`, `cookie`, `secret`)

---

## Performance Patterns

### 9. Descriptor-Driven Rate Limiting

**Паттерн**: Configuration over Code

Все задержки — из дескриптора, не хардкод:

```python
import random, time

def _antibot_sleep(descriptor: PlatformDescriptor) -> None:
    if random.random() < descriptor.extra.get("long_pause_prob", 0.15):
        delay = random.uniform(
            descriptor.extra.get("long_pause_sec_min", 8.0),
            descriptor.extra.get("long_pause_sec_max", 15.0),
        )
    else:
        delay = random.uniform(
            descriptor.extra.get("rate_limit_sec_min", 1.5),
            descriptor.extra.get("rate_limit_sec_max", 4.0),
        )
    time.sleep(delay)
```

Изменение поведения — только в `descriptor.yaml`, не в коде.

---

### 10. httpx Client Reuse

**Паттерн**: Session Pooling

Один `httpx.Client` на весь `fetch_new()` вызов — не создавать per-request:

```python
async def fetch_new(self, session, since, descriptor):
    with httpx.Client(headers=self._build_headers(session), timeout=30.0) as client:
        page = 1
        while True:
            response = client.get(api_url, params={...})
            # ... процесс страницы ...
            page += 1
    # клиент закрывается при выходе из with — соединение возвращается в пул
```
