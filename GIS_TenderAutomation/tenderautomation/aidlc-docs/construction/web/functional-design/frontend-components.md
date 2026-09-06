# Frontend Components — Unit 3: Web Application

Stack: Jinja2 SSR + минимальный JavaScript (нет фреймворков).

## Структура шаблонов

```
src/web/templates/
├── base.html                   # Базовый layout
├── auth/
│   └── login.html              # Форма входа
├── tenders/
│   ├── list.html               # Список квалифицированных тендеров
│   └── detail.html             # Карточка тендера
└── history/
    └── list.html               # История обработанных тендеров
```

---

## `base.html` — Базовый layout

**Компоненты**:
- Шапка навигации: лого GIS, имя пользователя (роль), кнопка «Выйти»
- Badge «Новых: N» — количество непросмотренных qualified тендеров (передаётся в контекст)
- Навигационные ссылки: «Тендеры», «История»

**Props (context)**:
- `current_user: User`
- `unread_count: int`
- `active_page: str` (для подсветки активного пункта меню)

**data-testid**:
- `nav-tenders-link`, `nav-history-link`, `nav-logout-btn`
- `nav-unread-badge`

---

## `auth/login.html` — Форма входа

**Состояние**: нет (stateless — серверный рендер)

**Элементы**:
- Поле `username` (text/email input)
- Поле `password` (password input)
- Кнопка «Войти» (submit)
- Блок ошибки (условный — если `error` в контексте)

**Props**:
- `error: str | None`

**Валидация**: server-side. Клиентская валидация — только HTML5 `required`.

**data-testid**:
- `login-username-input`, `login-password-input`, `login-submit-btn`, `login-error-msg`

---

## `tenders/list.html` — Список тендеров (US-04)

**Элементы**:

1. **Панель фильтров** (форма GET):
   - Выбор площадки (select: все / b2bcenter / bidzaar)
   - Поиск по тексту (text input)
   - Кнопка «Применить»

2. **Таблица тендеров** (одна строка = один тендер):
   - 🔴 красная точка (`●`) если `is_new` для текущего пользователя
   - Название (ссылка на `/tenders/{id}`)
   - Площадка (badge)
   - Заказчик
   - НМЦК (форматированное число)
   - Дедлайн (дата)
   - Эшелон AI (если есть: ⭐/🟡/🟠/🔴)
   - Статус (badge: новый / в работе / отклонён / отложен)

3. **Кнопка «Скачать для AI-анализа»**:
   - Скачивает все qualified тендеры как ZIP
   - `href="/export/zip"`

4. **Пагинация**: «← Пред.» / «Стр. N» / «След. →»

**Props**:
- `tenders: list[TenderModel]`
- `is_new_map: dict[str, bool]` (tender_id → is_new)
- `page: int`, `has_next: bool`
- `filters: dict` (текущие фильтры)

**data-testid**:
- `tenders-list-table`, `tender-row-{id}`, `tender-new-indicator-{id}`
- `tenders-filter-platform`, `tenders-filter-search`, `tenders-filter-submit`
- `tenders-export-btn`, `tenders-pagination-prev`, `tenders-pagination-next`

---

## `tenders/detail.html` — Карточка тендера (US-04, US-05, US-06)

**Секции**:

1. **Основные поля** (read-only):
   - Название, площадка, заказчик, НМЦК, дедлайн, URL на оригинал (внешняя ссылка)
   - Описание (если есть)
   - Дата сбора

2. **Кнопка «Скачать для AI-анализа»** (только этот тендер):
   - `href="/export/zip?ids={id}"`

3. **Секция AI-анализа** (US-05):
   - Если анализ есть: отображает эшелон (большой emoji), обоснование, инструмент, автора, дату
   - Если нет: форма загрузки анализа:
     - Select эшелона: ⭐ Прямое попадание / 🟡 Стоит изучить / 🟠 Тяжёлая конкуренция / 🔴 Шум
     - Textarea обоснования (1–2000 символов)
     - Input AI-инструмент (необязательный)
     - Кнопка «Сохранить анализ»

4. **Секция решения** (US-06):
   - Если решения нет: три кнопки: «✅ Взять в работу», «❌ Отклонить», «⏸ Отложить»
   - Поле «Заметка» (textarea, опциональное, max 500)
   - Если решение есть: статус + кнопки для изменения

5. **История действий** (collapsible):
   - Хронологический список actions: тип, пользователь, дата, заметка

**Props**:
- `tender: TenderModel`
- `ai_analysis: TenderAction | None`
- `actions: list[TenderAction]`
- `current_user: User`
- `ai_tier_options: list[str]`

**data-testid**:
- `tender-title`, `tender-buyer`, `tender-budget`, `tender-deadline`
- `tender-export-single-btn`
- `ai-analysis-section`, `ai-tier-select`, `ai-rationale-textarea`, `ai-tool-input`, `ai-submit-btn`
- `action-taken-btn`, `action-rejected-btn`, `action-deferred-btn`
- `action-notes-textarea`, `action-history-list`

---

## `history/list.html` — История (US-07)

**Элементы**:

1. **Панель фильтров** (форма GET):
   - Площадка (select)
   - Статус (select: взят / отклонён / отложен)
   - Период от/до (date inputs)
   - Поиск по тексту
   - Кнопка «Применить»

2. **Таблица истории**:
   - Название тендера (ссылка на `/tenders/{id}`)
   - Площадка
   - Заказчик
   - Решение (badge с цветом)
   - Специалист
   - Дата решения
   - Заметка (truncated)

3. **Пагинация**: страницы по 50

**Props**:
- `items: list[dict]` (tender + action merged)
- `page: int`, `has_next: bool`
- `filters: dict`

**data-testid**:
- `history-list-table`, `history-filter-platform`, `history-filter-status`
- `history-filter-from`, `history-filter-to`, `history-filter-search`, `history-filter-submit`

---

## User Interaction Flows

### Флоу «Просмотр и AI-анализ»
```
Тендеры (список) → клик на тендер (красная точка исчезает) →
  карточка → «Скачать для AI» → открывает в claude.ai/ChatGPT →
  вернуться в карточку → заполнить AI-анализ → «Сохранить» →
  карточка (эшелон отображается) → «Взять в работу» → список
```

### Флоу «Быстрое решение без AI»
```
Список → клик → карточка → «Отклонить» + заметка → список
```
