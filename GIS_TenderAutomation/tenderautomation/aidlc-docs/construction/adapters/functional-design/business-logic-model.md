# Business Logic Model — Unit 2: Platform Adapters

> Current collection behavior is superseded by
> `../current-collection-design.md`. The original design below is retained as historical
> AI-DLC decision context.

## 1. Bidzaar — Автоматический логин (Playwright headless)

**Алгоритм `authenticate(credentials)`**:
```
state_path  = Path(descriptor.state_file)       # data/bidzaar_state.json
token_cache = Path(descriptor.token_cache_file) # data/bidzaar_token.json

# Шаг 1: Попытка использовать кэш
if token_cache.exists():
    cached = json.loads(token_cache.read_text())
    if cached["expires_at"] - buffer_sec > now():
        return AuthSession(token=cached["access_token"], ...)

# Шаг 2: Обновление через сохранённое состояние (headless)
if state_path.exists():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()
        page.goto(descriptor.app_url, wait_until="domcontentloaded")
        sleep(3)  # дать JS время обновить токен
        token, expires_at = extract_token_from_localstorage(page)
        if token:
            context.storage_state(path=str(state_path))  # обновить state
            save_token_cache(token, expires_at)
            return AuthSession(token=token, ...)
        # state устарел → идём на полный логин

# Шаг 3: Полный автоматический логин (заполняем форму)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto(descriptor.login_url)
    
    # Заполняем форму — селекторы стабильны на bidzaar.com
    page.fill('input[name="username"]', credentials.username)
    page.fill('input[name="password"]', credentials.password)
    page.click('button[type="submit"]')
    
    # Ждём токен в localStorage (max login_timeout_sec=60)
    deadline = time() + descriptor.login_timeout_sec
    while time() < deadline:
        token, expires_at = extract_token_from_localstorage(page)
        if token: break
        sleep(2)
    
    if not token:
        raise AuthError("Bidzaar login failed: token not found after login")
    
    context.storage_state(path=str(state_path))
    save_token_cache(token, expires_at)
    return AuthSession(token=token, expires_at=datetime.fromtimestamp(expires_at))
```

---

## 2. Bidzaar — Инкрементальный сбор тендеров

**Алгоритм `fetch_new(session, since, descriptor)`**:
```
headers = {
    "Authorization": f"Bearer {session.token}",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 ...",
    "x-user-companyid": extract_company_id(session.cookies),
}

page = 1
results = []

while True:
    response = GET(
        f"{base_url}{descriptor.api_endpoint}",
        params={"paging.page": page, "paging.size": descriptor.page_size},
        headers=headers,
        cookies=session.cookies,
        timeout=30,
    )
    data = response.json()
    items = data.get("items", [])
    total_count = data.get("totalCount", 0)
    
    if not items: break
    
    new_items = []
    for item in items:
        published = parse_iso_datetime(item.get("startDate"))
        # Инкрементальный фильтр: если since задан и дата публикации раньше — стоп
        if since and published and published < since:
            return results  # достигли старых записей
        results.append(RawTender(platform="bidzaar", external_id=str(item["id"]), raw=item))
    
    if len(results) >= total_count: break
    page += 1
    sleep(descriptor.rate_limit_sec)

return results
```

---

## 3. B2B-Center — Сбор в режиме поиска по ключевым словам

**Алгоритм `fetch_new(session, since, descriptor)`** (auth=None для B2B-Center):
```
queries = load_queries(queries_yaml_path)  # из queries.yaml
results = []

for query in queries:
    url = descriptor.search_url_template.format(
        base_url=descriptor.base_url,
        query=quote(query.term),
        offset=0,
    )
    
    # Получаем первую страницу + общее количество
    html = GET(url, headers=BROWSER_HEADERS, timeout=30)
    total = parse_total_count(html)
    
    # Шумовая защита
    if total > descriptor.max_results_per_query:
        log.warning("noisy_query_skipped", context={"query": query.term, "total": total})
        continue
    
    offset = 0
    known_streak = 0  # счётчик последовательных «знакомых» строк
    
    while offset < total:
        if offset > 0:  # первая страница уже получена
            html = GET(url_with_offset(url, offset), headers=BROWSER_HEADERS)
        
        rows = parse_html_rows(html)  # BeautifulSoup → list[B2BCenterRawRow]
        
        for row in rows:
            tender_id = f"b2bcenter_{row.lot_id}"
            if since and row_is_older_than(row, since):
                return results  # инкремент: прекращаем обход
            results.append(RawTender(
                platform="b2bcenter",
                external_id=row.lot_id,
                raw={...row fields..., "search_query": query.term},
            ))
        
        offset += descriptor.page_size
        _antibot_sleep(descriptor)  # случайная пауза

return results
```

---

## 4. B2B-Center — Антибот-паузы

```python
import random

def _antibot_sleep(descriptor):
    if random.random() < descriptor.long_pause_prob:
        sleep(random.uniform(descriptor.long_pause_sec_min, descriptor.long_pause_sec_max))
    else:
        sleep(random.uniform(descriptor.rate_limit_sec_min, descriptor.rate_limit_sec_max))
```

---

## 5. B2B-Center — Парсинг HTML-строк

```
parse_html_rows(html: str) → list[B2BCenterRawRow]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="lots-list")  # или аналогичный селектор
    rows = []
    for tr in table.find_all("tr", class_=lambda c: c and "lot" in c):
        a = tr.find("a", href=re.compile(r"/market/\d+/"))
        lot_id = re.search(r"/market/(\d+)/", a["href"]).group(1)
        rows.append(B2BCenterRawRow(
            lot_id=lot_id,
            title=tr.select_one("td.title").get_text(strip=True),
            buyer=tr.select_one("td.buyer").get_text(strip=True) or None,
            budget_raw=tr.select_one("td.price").get_text(strip=True) or None,
            deadline_raw=tr.select_one("td.deadline").get_text(strip=True) or None,
            url=f"https://www.b2b-center.ru/market/{lot_id}/",
        ))
    return rows
```

**Примечание**: точные CSS-классы уточняются при тестировании. Структура HTML B2B-Center стабильна годами.

---

## 6. Вспомогательные парсеры

### parse_price (B2B-Center)
```
"1 500 000 руб."  → Decimal("1500000.00")
"от 500 000"      → Decimal("500000.00")
""                → None

algorithm:
  text = strip price field
  if not text or text.lower() in ("", "не указана", "договорная"): return None
  digits = re.sub(r"[^\d,.]", "", text).replace(",", ".")
  return Decimal(digits) if digits else None
```

### parse_deadline (B2B-Center)
```
"15.07.2026 23:59"  → datetime(2026, 7, 15, 23, 59, tzinfo=UTC+3)
"15.07.2026"        → datetime(2026, 7, 15, 0, 0, tzinfo=UTC+3)
""                  → None

MOSCOW_TZ = timezone(timedelta(hours=3))

algorithm:
  for fmt in ["%d.%m.%Y %H:%M", "%d.%m.%Y"]:
      try: return datetime.strptime(text, fmt).replace(tzinfo=MOSCOW_TZ)
  return None
```

### extract_token_from_localstorage (Bidzaar)
```
items = page.evaluate("() => { out={}; for(let i=0;i<localStorage.length;i++){...}; return out }")
token_raw = items.get("access_token", "")
token = token_raw.strip().strip('"')
exp = decode_jwt_exp(token)  # base64 decode JWT payload → exp field
return token, exp
```
