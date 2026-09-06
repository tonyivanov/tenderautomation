# NFR Requirements — Unit 3: Web Application

## Производительность

| Требование | Метрика |
|---|---|
| Время отклика списка тендеров | < 2с (NFR-03) |
| Время отклика карточки тендера | < 2с |
| Валидация сессии | Один SQL-запрос per request (JOIN users ON sessions) |
| ZIP-экспорт | Генерируется в памяти (BytesIO), нет temp-файлов на диске |
| Пагинация | max 20 записей/страница, max offset 10 000 |

## Безопасность (Security Baseline — все правила блокирующие)

| Правило | Применение к Unit 3 |
|---|---|
| SECURITY-01 (TLS) | TLS терминируется на Nginx. Приложение слушает localhost:8000 (нет прямого TLS в FastAPI). |
| SECURITY-03 (Logging) | session_id, password_hash, ip_address — не логируются. Формат JSON (core.logging). |
| SECURITY-04 (HTTP Headers) | Middleware добавляет CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy на все HTML-ответы. |
| SECURITY-05 (Input Validation) | Pydantic-модели на всех POST body. FastAPI query-параметры типизированы. max_length на all string inputs. |
| SECURITY-08 (Auth & IDOR) | Все роутеры — FastAPI dependency `get_current_user`. Нет публичных эндпоинтов кроме /login. Тендеры не проверяются на ownership (все authenticated users видят все — internal tool). |
| SECURITY-09 (Error handling) | Кастомный 500-handler возвращает generic HTML-страницу без stack trace. В логах — полная ошибка. |
| SECURITY-10 (Supply chain) | bcrypt, slowapi, bootstrap CDN с integrity hashes (SRI — SECURITY-13). Pinned versions. |
| SECURITY-11 (Secure Design) | Auth logic изолирован в `src/web/auth.py`. Rate limiting изолирован через slowapi. |
| SECURITY-12 (Auth & Credentials) | bcrypt cost=12 (adaptive). Cookie: Secure+HttpOnly+SameSite=Lax. Session TTL 8h. Brute-force: slowapi 5/15min per IP. Session invalidated on logout. |
| SECURITY-13 (Integrity) | Bootstrap 5 с SRI-хэшем в base.html. json.loads (не eval). Нет pickle. |
| SECURITY-14 (Alerting) | Login failures логируются (level=WARNING) с ip и username. Мониторинг — через journald/log-файлы. |
| SECURITY-15 (Fail-safe) | Global FastAPI exception_handler: 500 → generic response. DB-соединения через context manager (возврат в пул). |

**SECURITY N/A**: SECURITY-02 (нет LB в приложении — это Nginx), SECURITY-06 (нет IAM), SECURITY-07 (сетевая конфигурация — Infrastructure Design).

## Надёжность

- **Session cleanup**: истёкшие сессии удаляются lazy (при обращении). Опционально — cron `DELETE FROM user_sessions WHERE expires_at < now()` раз в сутки.
- **DB connection pool**: унаследован из Unit 1 (`core.db.SessionLocal`, pool_size=5).
- **Brute-force via slowapi**: in-memory store (single-process Gunicorn worker). При multi-worker — shared Redis storage (будущее расширение).
- **Static files**: отдаются Nginx (не FastAPI) — снижает нагрузку на Python-процесс.

## Тестирование (PBT + Unit)

PBT-09: Hypothesis — уже выбран.

PBT-01 свойства:
| Компонент | Свойство | Категория |
|---|---|---|
| `bcrypt.hashpw` | verify(hash(pw), pw) == True для любого пароля | Round-trip |
| `ExportService` | JSONL export → json.loads → те же поля id, title, platform | Round-trip |
| Session ID | UUID4 — всегда уникален (collision probability < 1e-18) | Invariant |
| `is_new` | Iff нет TenderView(tender_id, user_id) | Invariant |
