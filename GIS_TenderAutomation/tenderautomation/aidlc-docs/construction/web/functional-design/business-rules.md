# Business Rules — Unit 3: Web Application

## Доступ и аутентификация

**BR-W01**: Все эндпоинты кроме `GET /login`, `POST /login`, `GET /static/*` требуют валидной сессии. Нет сессии → redirect `/login`. (SECURITY-08 deny by default)

**BR-W02**: Сессия истекает через `SESSION_TTL_HOURS` (по умолчанию 8). Значение из `Settings`. Истёкшая сессия удаляется при первом обращении с ней.

**BR-W03**: Пароли хранятся только как bcrypt-хэш с cost=12. Plaintext пароль никогда не сохраняется и не логируется. (SECURITY-12)

**BR-W04**: Cookie сессии устанавливается с флагами: `HttpOnly=True`, `Secure=True`, `SameSite=Lax`. (SECURITY-12 session management)

**BR-W05**: Brute-force protection: если за последние 15 минут с одного IP поступило ≥ 5 неудачных попыток входа → 429 Too Many Requests. Логируется в `login_attempts`. (SECURITY-12)

**BR-W06**: Сообщение об ошибке входа всегда обобщённое: «Неверное имя пользователя или пароль» — без уточнения что именно неверно. (SECURITY-09)

**BR-W07**: Деактивированный пользователь (`is_active=False`) не может войти. Существующие сессии деактивированного пользователя инвалидируются при следующем обращении.

## Тендеры и просмотр

**BR-W08**: Тендер считается «новым» для пользователя если в таблице `tender_views` нет записи для пары `(tender_id, user_id)`. Запись создаётся при открытии карточки — `ON CONFLICT DO NOTHING`.

**BR-W09**: Список тендеров: страница = 20 записей. Максимальный offset = 10 000 (защита от перебора).

**BR-W10**: Список показывает только тендеры с `qualification_tier = "qualified"`.

## Экспорт (US-03)

**BR-W11**: Экспорт — ZIP-архив с двумя файлами: `tenders_YYYY-MM-DD.jsonl` + `AGENTS.md`. Один эндпоинт `GET /export/zip`. (Q3:A)

**BR-W12**: AGENTS.md = базовый статический файл + блок `semantic_profile` из `filters/config.yaml`, вставляемый в placeholder `{{SEMANTIC_PROFILE}}`. (Q6:C)

**BR-W13**: Экспорт без параметров → все qualified тендеры (limit 1000). С параметром `?ids=id1,id2` → только указанные.

## AI-анализ (US-05)

**BR-W14**: Допустимые значения `ai_tier`: `⭐`, `🟡`, `🟠`, `🔴`. Любое другое значение → 422.

**BR-W15**: `ai_rationale` — обязательное поле, длина 1–2000 символов.

**BR-W16**: `ai_tool` — необязательное поле, максимум 100 символов.

**BR-W17**: Загрузка анализа — всегда новая запись в `tender_actions` (action_type="ai_analysis"). Предыдущий анализ не удаляется — хранится история. В карточке отображается последний.

## Решения специалиста (US-06)

**BR-W18**: Допустимые значения `action`: `taken`, `rejected`, `deferred`.

**BR-W19**: `notes` — необязательное поле, максимум 500 символов.

**BR-W20**: Решение не отменяется напрямую — создаётся новая запись. История всех решений сохраняется в `tender_actions` и `actions.jsonl`.

**BR-W21**: После решения `taken`/`rejected`/`deferred` тендер получает соответствующий статус в `tenders.status`. Статус может измениться если принято новое решение (например отложенный → взят).

## История (US-07)

**BR-W22**: Поиск по названию и заказчику — case-insensitive, ILIKE в PostgreSQL.

**BR-W23**: Максимальный размер страницы истории — 50 записей.

## HTTP Security Headers (SECURITY-04)

**BR-W24**: На всех HTML-ответах устанавливаются заголовки:
```
Content-Security-Policy: default-src 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```
Реализуется через FastAPI middleware (один раз).

## Прочее

**BR-W25**: Все формы используют PRG (Post-Redirect-Get) — после POST-запроса всегда redirect, не прямой рендер. Исключение: форма входа при ошибке.

**BR-W26**: Страница входа не кэшируется: `Cache-Control: no-store`.

---

## PBT-01: Compliance Summary

| Компонент | Свойство | Категория | Статус |
|---|---|---|---|
| Auth: bcrypt | `verify(hash(pw), pw) == True` для любого pw | Round-trip | Идентифицировано |
| ExportService | JSONL export → json.loads → те же поля | Round-trip | Идентифицировано |
| SessionService | Session ID всегда UUID4 (уникален) | Invariant | Идентифицировано |
| TenderView | `is_new(tender, user)` = True iff нет записи в tender_views | Invariant | Идентифицировано |
| ActionType | action_type всегда из фиксированного множества | Invariant | Идентифицировано |
