# Technology Stack

## Programming Languages
- **Python** — 3.10+ — вся логика обоих конвейеров.
- **Windows Batch (.bat)** — обёртки-кнопки для не-разработчика (описаны в README; в архиве не распакованы).
- **YAML** — конфигурация ключевых слов и запросов.
- **SQL (SQLite dialect)** — хранение и запросы.

## Frameworks / Libraries
| Библиотека | Где | Назначение |
|---|---|---|
| httpx (≥0.27) | b2bcenter-scout | HTTP-клиент (HTML) |
| requests (≥2.31) | bidzaar-scout | HTTP-клиент (JSON API) |
| beautifulsoup4 (≥4.12) + lxml (≥5.0) | b2bcenter-scout | парсинг HTML |
| PyYAML (≥6.0) | оба | чтение словарей |
| playwright (≥1.40/1.45) | оба | аутентификация, recon |

## Data Stores
- **SQLite** — `b2bcenter.db`, `bidzaar.db` (локальные файлы, без сервера).

## Infrastructure
- Нет облачной инфраструктуры. Запуск на рабочей машине (преимущественно Windows 10/11), кроссплатформенность — на уровне Python-скриптов.
- Возможный корпоративный прокси (`HTTPS_PROXY`) для pip/Playwright/площадок.

## Build Tools
- **pip + venv** — установка зависимостей из `requirements.txt`.
- **playwright install chromium** — разовая загрузка браузера (~150–300 МБ).

## Testing Tools
- Отсутствуют (нет фреймворка тестирования, нет CI).

## External (вне кода)
- **Claude / claude.ai** — ручной семантический разбор (День 1). Anthropic API — запланирован для Дня 2, не подключён.
