# Code Summary — Unit 2: Platform Adapters

## Созданные файлы

### B2B-Center (`src/adapters/b2bcenter/`)
| Файл | Содержание |
|---|---|
| `parsers.py` | `parse_price()`, `parse_deadline()`, `parse_rows()`, `parse_total_count()` |
| `scraper.py` | `B2BCenterScraper` — async endpoint feed + Playwright query search, пагинация, антибот, дедупликация |
| `adapter.py` | `B2BCenterAdapter(PlatformAdapter)` — точка входа, no-op auth, map_to_tender |
| `descriptor.yaml` | Параметры платформы (rate limits, page_size, max_results_per_query) |
| `queries.yaml` | 70+ поисковых запросов (перенесены из существующего search_queries.yaml) |

### Bidzaar (`src/adapters/bidzaar/`)
| Файл | Содержание |
|---|---|
| `auth.py` | `BidzaarAuth` — no-op для публичного collection endpoint |
| `api_client.py` | `BidzaarApiClient` — async public integrator pagination, `since` и expiry filtering |
| `adapter.py` | `BidzaarAdapter(PlatformAdapter)` — публичный collection flow, map_to_tender |
| `descriptor.yaml` | Integrator ID, public response mapping, page_size |

### Прочее
| Файл | Содержание |
|---|---|
| `src/adapters/__init__.py` | Реэкспорт B2BCenterAdapter, BidzaarAdapter |
| `src/core/cli.py` | Обновлён: адаптеры зарегистрированы в registry |
| `requirements.txt` | Добавлены: httpx==0.27.2, playwright==1.48.0, beautifulsoup4==4.12.3 |

### Тесты (`tests/unit/adapters/`)
| Файл | Покрытие |
|---|---|
| `b2bcenter/test_parsers.py` | PBT: parse_price (никогда не поднимает, ≥0, never_raises); parse_deadline (формат, timezone, never_raises) |
| `b2bcenter/test_adapter.py` | ID format, required fields, determinism (PBT) |
| `bidzaar/test_adapter.py` | ID format, URL format, budget parsing, determinism (PBT), prefix invariant |

## Ключевые паттерны

- **Separate Bidzaar access paths**: public collection без credentials; manual Playwright session только для private-file deep analysis
- **Dual B2B collection**: endpoint recommendations feed + Playwright query search, configurable через `fetch_modes`
- **Noise guard**: B2B-Center queries с >1000 результатами пропускаются
- **Antibot**: случайные паузы 1.5–4s (15% chance 8–15s) из descriptor.yaml
- **httpx unified**: один клиент для B2B-Center scraping и Bidzaar API
- **State files gitignored**: `data/bidzaar_state.json` в `.gitignore`

## Запуск после установки

```bash
# Установка зависимостей
pip install -r requirements.txt
playwright install chromium

# Collection не требует Bidzaar login.
python -m core.cli run-pipeline

# Опционально: private-file deep analysis
PYTHONPATH=src python scripts/bidzaar_login.py
```
