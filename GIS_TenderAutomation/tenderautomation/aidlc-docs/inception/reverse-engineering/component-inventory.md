# Component Inventory

## Application Packages
- `b2bcenter-scout` (`Разбор тендеров/B2bCenter_parsing/`) — мониторинг B2B-Center (HTML-скрейпинг). 6 Python-модулей, ~1288 LOC.
- `bidzaar-scout` (`Разбор тендеров/Bidzaar_parsing/`) — мониторинг Bidzaar (JSON API). 4 Python-модуля, ~685 LOC.

## Infrastructure Packages
- Отсутствуют (нет CDK/Terraform/CloudFormation). Развёртывание — локальный venv + Windows `.bat`.

## Shared Packages
- Отсутствуют. Код между конвейерами **не переиспользуется** (дублирование паттерна — кандидат на выделение общего ядра).

## Test Packages
- Отсутствуют. Автоматических тестов в проекте нет.

## Data / Reference (не код)
- `Разбор тендеров/Данные для анализа/` — 7 кейсов реальных тендеров (30 файлов: 21 docx, 5 xlsx, 3 pdf, 1 doc). Эталонные ТЗ/КП для калибровки отбора и будущего LLM-анализа.
- `data/*.txt` — выгрузки тендеров (артефакты прогонов).
- Файлы сессий/токенов (`auth_state.json`, `cookies*.json`, `playwright_state.json`, `token_cache.json`) — **секреты** (см. code-quality-assessment.md).

## Total Count
- **Total Packages (код)**: 2
- **Application**: 2
- **Infrastructure**: 0
- **Shared**: 0
- **Test**: 0
- **Python-модулей**: 10 (~1973 LOC)
- **Конфигов**: 3 YAML (2× keywords, 1× search_queries)
