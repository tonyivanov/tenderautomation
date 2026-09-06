# System Architecture

## System Overview

Две независимые, структурно похожие CLI-системы на Python, реализующие один паттерн обработки: **fetch → store(SQLite) → prefilter → export(TXT) → ручной разбор в чате с Claude**. Различие — транспорт: `b2bcenter-scout` скрейпит HTML, `bidzaar-scout` использует JSON API. Оркестрация — Windows `.bat`-обёртки (в архиве присутствуют только Python; `.bat` упоминаются в документации). Общего кода между конвейерами нет — это два отдельных «слепка» одной идеи.

## Architecture Diagram

```mermaid
flowchart TD
    subgraph B2B["b2bcenter-scout"]
        F1["fetch_list.py<br/>HTML-скрейпинг (httpx + bs4)"]
        P1["prefilter.py"]
        E1["export_for_review.py"]
        L1["login.py (Playwright)"]
        R1["recon_card.py"]
        DB1[("data/b2bcenter.db<br/>SQLite")]
        Q1["search_queries.yaml<br/>keywords.yaml"]
        F1 --> DB1
        Q1 --> F1
        DB1 --> P1 --> DB1
        DB1 --> E1
        L1 --> R1
        R1 --> DB1
    end

    subgraph BZ["bidzaar-scout"]
        A2["auth.py (Playwright + JWT)"]
        F2["fetch_list.py<br/>JSON API (requests)"]
        P2["prefilter.py"]
        E2["export_for_review.py"]
        DB2[("data/bidzaar.db<br/>SQLite")]
        Q2["keywords.yaml"]
        A2 --> F2 --> DB2
        Q2 --> P2
        DB2 --> P2 --> DB2
        DB2 --> E2
    end

    E1 --> TXT["score100_tenders.txt / all_tenders.txt"]
    E2 --> TXT
    TXT --> Human["Человек → чат с Claude → шортлист"]
```

## Component Descriptions

### b2bcenter-scout / fetch_list.py
- **Purpose**: обход поиска B2B-Center и парсинг таблицы тендеров.
- **Responsibilities**: построение URL поиска, пагинация `?from=N`, антибот-паузы, защита от шумовых выдач, запись в SQLite.
- **Dependencies**: httpx, beautifulsoup4, lxml, PyYAML.
- **Type**: Application.

### b2bcenter-scout / prefilter.py, export_for_review.py, login.py, recon_card.py, reset_search.py
- **Purpose**: префильтр (score), выгрузка TXT, Playwright-логин, забор карточки, чистка search-данных.
- **Dependencies**: PyYAML; Playwright (login/recon).
- **Type**: Application.

### bidzaar-scout / auth.py
- **Purpose**: аутентификация Bidzaar — разовый ручной логин, далее headless-чтение свежего JWT из localStorage.
- **Responsibilities**: хранение состояния в `playwright_state.json`, кэш токена `token_cache.json`, выдача token + cookies для API-сессии.
- **Dependencies**: playwright.
- **Type**: Application (security-sensitive).

### bidzaar-scout / fetch_list.py, prefilter.py, export_for_review.py
- **Purpose**: синк списка через API, префильтр, выгрузка.
- **Dependencies**: requests, PyYAML.
- **Type**: Application.

## Data Flow

```mermaid
sequenceDiagram
    participant U as Человек
    participant S as scout (fetch_list)
    participant P as Платформа
    participant DB as SQLite
    participant C as Claude (чат)

    U->>S: запуск (bat / python)
    S->>P: запрос списка (HTML / API)
    P-->>S: тендеры
    S->>DB: upsert (дедуп по id)
    U->>S: prefilter + export
    S->>DB: чтение, простановка score
    S-->>U: score100_tenders.txt
    U->>C: TXT + контекст-файлы
    C-->>U: размеченный шортлист по эшелонам
```

## Integration Points
- **External APIs**: B2B-Center (HTML, неофициально — скрейпинг); Bidzaar (`/api/process/light/...`, официальный JSON).
- **Databases**: две локальные SQLite (`b2bcenter.db`, `bidzaar.db`).
- **Third-party Services**: Claude (claude.ai) — вне кода, ручной шаг; Playwright/Chromium для авторизации.

## Infrastructure Components
- **CDK Stacks**: отсутствуют.
- **Deployment Model**: локальный запуск на машине BD-сотрудника (Windows), `.bat`-кнопки; venv на машину.
- **Networking**: прямой исходящий HTTPS к площадкам; упоминается возможный корпоративный прокси (`HTTPS_PROXY`).
