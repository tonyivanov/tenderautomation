# Logical Components — Unit 2: Platform Adapters

## Структура пакетов

```
src/adapters/
├── __init__.py
├── b2bcenter/
│   ├── __init__.py
│   ├── adapter.py          # B2BCenterAdapter(PlatformAdapter)
│   ├── scraper.py          # HTML fetch + BeautifulSoup parsing
│   ├── parsers.py          # parse_price(), parse_deadline(), parse_total_count()
│   ├── descriptor.yaml     # Platform descriptor
│   └── queries.yaml        # Search queries (migrated from existing)
└── bidzaar/
    ├── __init__.py
    ├── adapter.py          # BidzaarAdapter(PlatformAdapter)
    ├── auth.py             # Three-step auth chain (Playwright headless)
    ├── api_client.py       # httpx wrapper for Bidzaar REST API
    └── descriptor.yaml     # Platform descriptor
```

---

## B2B-Center Components

### `B2BCenterAdapter` (`adapter.py`)

**Тип**: Concrete PlatformAdapter
**Ответственность**: Точка входа адаптера. Делегирует в `B2BCenterScraper`.

```python
class B2BCenterAdapter(PlatformAdapter):
    def platform_id(self) -> str:
        return "b2bcenter"

    async def authenticate(self, credentials: PlatformCredentials) -> AuthSession:
        return AuthSession(platform="b2bcenter")  # no auth for listing

    async def fetch_new(self, session: AuthSession, since: datetime,
                        descriptor: PlatformDescriptor) -> list[RawTender]:
        scraper = B2BCenterScraper(descriptor, queries_path=self._queries_path)
        return scraper.fetch_new(since)

    def map_to_tender(self, raw: RawTender, descriptor: PlatformDescriptor) -> TenderModel:
        return _map_b2bcenter(raw, descriptor)
```

---

### `B2BCenterScraper` (`scraper.py`)

**Тип**: Stateless helper
**Ответственность**: Обход страниц поиска B2B-Center. Загружает queries.yaml. Применяет антибот-паузы и noise guard.

```python
class B2BCenterScraper:
    def __init__(self, descriptor: PlatformDescriptor, queries_path: Path): ...

    def fetch_new(self, since: datetime | None) -> list[RawTender]:
        """Итерирует по всем запросам из queries.yaml."""
        queries = self._load_queries()
        results = []
        with httpx.Client(headers=BROWSER_HEADERS, timeout=30.0,
                          follow_redirects=True) as client:
            for query in queries:
                results.extend(self._fetch_query(client, query, since))
        return results

    def _fetch_query(self, client, query, since) -> list[RawTender]:
        """Один запрос: проверка noise guard, пагинация, incremental stop."""
```

---

### `B2BCenterParsers` (`parsers.py`)

**Тип**: Stateless pure functions
**Ответственность**: HTML-парсинг, парсинг цены, дедлайна, количества результатов. Все функции детерминированы → PBT-целевые.

```python
def parse_total_count(html: str) -> int: ...
def parse_rows(html: str) -> list[B2BCenterRawRow]: ...
def parse_price(text: str | None) -> Decimal | None: ...
def parse_deadline(text: str | None) -> datetime | None: ...
```

---

## Bidzaar Components

### `BidzaarAdapter` (`adapter.py`)

**Тип**: Concrete PlatformAdapter
**Ответственность**: Точка входа. Делегирует auth в `BidzaarAuth`, API-вызовы в `BidzaarApiClient`.

```python
class BidzaarAdapter(PlatformAdapter):
    def platform_id(self) -> str:
        return "bidzaar"

    async def authenticate(self, credentials: PlatformCredentials) -> AuthSession:
        auth = BidzaarAuth(self._descriptor)
        return auth.get_session(credentials)

    async def fetch_new(self, session: AuthSession, since: datetime,
                        descriptor: PlatformDescriptor) -> list[RawTender]:
        client = BidzaarApiClient(session, descriptor)
        return client.fetch_new(since)

    def map_to_tender(self, raw: RawTender, descriptor: PlatformDescriptor) -> TenderModel:
        return _map_bidzaar(raw, descriptor)
```

---

### `BidzaarAuth` (`auth.py`)

**Тип**: Stateful (читает/пишет state-файлы)
**Ответственность**: Three-step auth chain. Кэш токена → headless refresh → full auto-login.

```python
class BidzaarAuth:
    def __init__(self, descriptor: PlatformDescriptor): ...

    def get_session(self, credentials: PlatformCredentials) -> AuthSession:
        """Главная точка входа. Возвращает AuthSession с валидным токеном."""

    def _get_cached_token(self) -> str | None: ...
    def _refresh_token_headless(self) -> str | None: ...
    def _full_auto_login(self, credentials: PlatformCredentials) -> str: ...
    def _extract_token_from_localstorage(self, page) -> tuple[str, int]: ...
    def _save_token_cache(self, token: str, expires_at: int) -> None: ...
```

**state_path** и **token_cache_path** берутся из `descriptor.extra["state_file"]` и `descriptor.extra["token_cache_file"]`.

---

### `BidzaarApiClient` (`api_client.py`)

**Тип**: Stateless HTTP wrapper
**Ответственность**: Пагинированные запросы к Bidzaar REST API. Инкрементальная остановка.

```python
class BidzaarApiClient:
    def __init__(self, session: AuthSession, descriptor: PlatformDescriptor): ...

    def fetch_new(self, since: datetime | None) -> list[RawTender]:
        """Постраничный сбор. Останавливается при since или исчерпании totalCount."""

    def _build_headers(self) -> dict[str, str]:
        """Authorization: Bearer token + User-Agent + x-user-companyid."""

    def _fetch_page(self, client: httpx.Client, page: int) -> dict:
        """GET /api/.../available?paging.page=N&paging.size=25."""
```

---

## Взаимодействие компонентов при запуске сбора

```
CollectionService.run_for_platform("bidzaar")
    │
    ├── BidzaarAdapter.authenticate(credentials)
    │       └── BidzaarAuth.get_session()
    │               ├── _get_cached_token()  → token (fast path)
    │               ├── _refresh_token_headless() → token (medium path)
    │               └── _full_auto_login()   → token (slow path, fills form)
    │                     └── [Playwright headless Chromium]
    │
    └── BidzaarAdapter.fetch_new(session, since, descriptor)
            └── BidzaarApiClient.fetch_new(since)
                    └── httpx.Client GET /api/.../available?paging.page=N
                            → list[RawTender]

    └── BidzaarAdapter.map_to_tender(raw, descriptor)
            → TenderModel (id="bidzaar_{id}", ...)

CollectionService.run_for_platform("b2bcenter")
    │
    ├── B2BCenterAdapter.authenticate() → AuthSession() [empty, no-op]
    │
    └── B2BCenterAdapter.fetch_new(session, since, descriptor)
            └── B2BCenterScraper.fetch_new(since)
                    └── [for query in queries.yaml]
                            ├── httpx.Client GET /market/?search=...
                            ├── parse_total_count() → noise guard
                            ├── parse_rows() → list[B2BCenterRawRow]
                            └── _antibot_sleep(descriptor)

    └── B2BCenterAdapter.map_to_tender(raw, descriptor)
            → TenderModel (id="b2bcenter_{lot_id}", ...)
```

---

## Интерфейс регистрации в CLI (Unit 1)

После Unit 2 в `src/core/cli.py` раскомментировать:

```python
from adapters.b2bcenter.adapter import B2BCenterAdapter
from adapters.bidzaar.adapter import BidzaarAdapter

registry.register(B2BCenterAdapter())
registry.register(BidzaarAdapter())
```
> Current async collection components are documented in
> `../current-collection-design.md`; legacy sync/JWT examples below are historical context.
