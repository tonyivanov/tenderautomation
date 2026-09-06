# Component Methods — TenderAutomation

> Детальная бизнес-логика методов определяется в стадии Functional Design (CONSTRUCTION phase).
> Здесь — сигнатуры, типы и высокоуровневое назначение.

---

## Unit 1: Core Library

### PlatformAdapter (ABC)

```python
class PlatformAdapter(ABC):
    @abstractmethod
    def platform_id(self) -> str:
        """Уникальный идентификатор площадки ('b2bcenter', 'bidzaar')."""

    @abstractmethod
    async def authenticate(self, credentials: PlatformCredentials) -> AuthSession:
        """Аутентификация по учётным данным. Возвращает сессию для последующих запросов."""

    @abstractmethod
    async def fetch_new(
        self, session: AuthSession, since: datetime, descriptor: PlatformDescriptor
    ) -> list[RawTender]:
        """Инкрементальный сбор тендеров, появившихся после `since`.
        Применяет rate limits из дескриптора."""

    @abstractmethod
    def map_to_tender(self, raw: RawTender, descriptor: PlatformDescriptor) -> Tender:
        """Маппинг сырых данных площадки в унифицированную модель Tender."""
```

### QualificationEngine

```python
class QualificationEngine:
    def load_rules(self, rules_path: Path) -> KeywordRules:
        """Загружает и валидирует YAML-файл фильтров."""

    def score_tier1(self, tender: Tender, rules: KeywordRules) -> int:
        """Вычисляет prefilter_score (0–100) на основе keyword-правил Tier 1."""

    def apply_tier1_batch(
        self, tenders: list[Tender], rules: KeywordRules
    ) -> list[ScoredTender]:
        """Пакетная Tier 1 квалификация. Возвращает тендеры с проставленным score."""

    def build_tier2_context(self, rules: KeywordRules) -> str:
        """Формирует текстовый блок семантических правил Tier 2 для вставки в AGENTS.md."""
```

### TenderRepository

```python
class TenderRepository:
    def save_batch(self, tenders: list[Tender]) -> int:
        """Сохраняет список тендеров (upsert по platform + external_id). Возвращает кол-во новых."""

    def update_qualification(self, tender_id: str, score: int, tier: str) -> None:
        """Обновляет prefilter_score и qualification_tier после квалификации."""

    def get_qualified(
        self,
        platform: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Tender]:
        """Возвращает квалифицированные тендеры с применением фильтров."""

    def get_by_id(self, tender_id: str) -> Tender | None:
        """Возвращает тендер по внутреннему ID или None."""

    def mark_viewed(self, tender_id: str, user_id: str) -> None:
        """Снимает признак 'новый' для конкретного пользователя."""

    def save_analysis(self, tender_id: str, analysis: AnalysisResult) -> None:
        """Сохраняет результат AI-анализа (эшелон + обоснование) в карточку тендера."""

    def save_action(self, action: TenderAction) -> None:
        """Сохраняет решение специалиста (взять/отклонить/отложить)."""

    def get_history(self, filters: HistoryFilters) -> list[TenderWithAction]:
        """Возвращает историю тендеров с принятыми решениями."""
```

### QualifiedLogRepository

```python
class QualifiedLogRepository:
    def append_batch(self, tenders: list[ScoredTender]) -> None:
        """Дописывает квалифицированные тендеры в JSONL-файл (append-only)."""

    def read_since(self, since: datetime) -> list[dict]:
        """Читает записи из JSONL начиная с `since` (для экспорта)."""
```

### ActionLogRepository

```python
class ActionLogRepository:
    def append(self, action: TenderAction) -> None:
        """Дописывает действие специалиста в JSONL-файл."""

    def read_all(self) -> list[TenderAction]:
        """Читает весь лог действий."""
```

### EventBus

```python
class EventBus:
    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        """Регистрирует обработчик события."""

    def publish(self, event: str, **payload) -> None:
        """Синхронно вызывает всех подписчиков события с переданными данными."""
```

---

## Unit 2: Platform Adapters

### AdapterRegistry

```python
class AdapterRegistry:
    def load_descriptors(self, descriptors_dir: Path) -> None:
        """Сканирует директорию, загружает все YAML-дескрипторы площадок."""

    def get_adapter(self, platform_id: str) -> PlatformAdapter:
        """Возвращает инстанс адаптера для указанной площадки."""

    def get_all_adapters(self) -> list[PlatformAdapter]:
        """Возвращает список всех зарегистрированных адаптеров."""
```

### B2BCenterAdapter / BidzaarAdapter
*(реализуют все абстрактные методы PlatformAdapter — сигнатуры наследуются)*

---

## Unit 3: Web Application

### ExportService

```python
class ExportService:
    def export_jsonl(self, tender_ids: list[str] | None = None) -> str:
        """Формирует JSONL-строку. Если tender_ids=None — все квалифицированные за последний цикл."""

    def get_agents_md(self) -> str:
        """Возвращает актуальный AGENTS.md (читает из файла + подставляет динамические секции)."""

    def build_export_bundle(self, tender_ids: list[str] | None = None) -> ExportBundle:
        """Собирает ExportBundle(jsonl: str, agents_md: str) для отдачи как zip/отдельных файлов."""
```

### SessionAuth

```python
class SessionAuth:
    async def login(self, username: str, password: str, request: Request) -> Response:
        """Проверяет учётные данные, создаёт серверную сессию, устанавливает cookie."""

    async def logout(self, request: Request) -> Response:
        """Инвалидирует серверную сессию."""

    async def get_current_user(self, request: Request) -> User:
        """FastAPI dependency: читает сессию из cookie, возвращает User или 401."""
```

---

## Unit 4: Notification Service

### TelegramNotifier

```python
class TelegramNotifier:
    async def send_new_tenders_alert(self, count: int, platform_summary: dict) -> None:
        """Отправляет Telegram-сообщение с количеством новых тендеров и ссылкой на UI."""
```

### EmailDigest

```python
class EmailDigest:
    def build_digest(self, tenders: list[Tender]) -> EmailMessage:
        """Формирует HTML/plain-text письмо с перечнем тендеров."""

    async def send(self, message: EmailMessage, recipients: list[str]) -> None:
        """Отправляет письмо через SMTP."""
```

### NotificationHandler

```python
class NotificationHandler:
    def on_tenders_qualified(self, count: int, platform_summary: dict) -> None:
        """Обработчик события 'tenders_qualified' — вызывает TelegramNotifier."""

    def register(self, event_bus: EventBus) -> None:
        """Подписывается на нужные события EventBus."""
```

---

## Export Integrity — методы текущей итерации

Детальные business rules, timeout budgets и transition tables будут определены
на Functional Design и NFR Design.

### Domain models

```python
class ProcedureState(str, Enum):
    UNKNOWN = "unknown"
    ACTIVE = "active"
    CLOSED = "closed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"


class TenderInspectionResult(BaseModel):
    tender_id: str
    procedure_state: ProcedureState
    checked_at: datetime
    source: str
    buyer: str | None = None
    budget: Decimal | None = None
    deadline: datetime | None = None
    description: str | None = None
    published_at: datetime | None = None
    raw_data_updates: dict[str, object] = Field(default_factory=dict)
    error_category: str | None = None
```

### `PlatformAdapter`

```python
class PlatformAdapter(ABC):
    async def inspect_tender(
        self,
        session: AuthSession,
        tender: TenderModel,
        descriptor: PlatformDescriptor | None,
    ) -> TenderInspectionResult:
        """Получить детали и состояние процедуры без изменения persistence."""
```

### `TenderRepository`

```python
class TenderRepository:
    def get_export_candidates(
        self, tender_ids: list[str] | None, *, limit: int
    ) -> list[TenderModel]:
        """Вернуть явно выбранные либо bulk-кандидаты в стабильном порядке."""

    def apply_inspection(
        self, result: TenderInspectionResult
    ) -> TenderModel | None:
        """Атомарно и идемпотентно сохранить проверенные поля и provenance."""
```

### `V3ExportProjection`

```python
class V3ExportProjection:
    def get_for_tender(
        self, tender_id: str, title: str
    ) -> V3ExportContext | None:
        """Вернуть финальный V3 view с judge override и вычисленной queue."""
```

### `ExportReadinessService`

```python
class ExportReadinessService:
    async def prepare(
        self, request: ExportRequest
    ) -> ExportPreparationResult:
        """Проверить, обогатить и разделить candidates по export outcomes."""
```

`ExportPreparationResult` содержит `ready`, `archived`, `unverified`,
`ineligible`, `missing` и агрегированную статистику. Он не содержит credentials
или сырые ответы площадок.

### `TenderAnalysisPromptProvider`

```python
class TenderAnalysisPromptProvider:
    def load(self) -> PromptArtifact:
        """Вернуть validated content, prompt_version и sha256."""
```

### `ExportBundleService`

```python
class ExportBundleService:
    def build_zip(
        self,
        preparation: ExportPreparationResult,
        prompt: PromptArtifact,
    ) -> ExportBundle:
        """Собрать JSONL, manifest и ZIP из подготовленных active records."""
```

### `ExportRouter`

```python
@router.get("/export/zip")
async def export_zip(request: Request, ids: str | None = None) -> Response:
    """Вернуть ZIP, 409 inactive result page либо 503 unverified result page."""
```
