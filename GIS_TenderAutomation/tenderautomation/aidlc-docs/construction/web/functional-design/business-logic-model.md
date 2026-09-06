# Business Logic Model — Unit 3: Web Application

## 1. Аутентификация (Login)

```
POST /login (username, password)

1. Lookup User by username → not found → 401 (generic message)
2. bcrypt.checkpw(password, user.password_hash) → False → log LoginAttempt → 401
3. Check rate limit: COUNT(login_attempts WHERE ip=X AND attempt_at > now()-15min) >= 5 → 429
4. user.is_active == False → 401
5. Create UserSession(session_id=uuid4(), user_id=user.id,
                      expires_at=now()+SESSION_TTL, ip=request.client.host)
6. INSERT session into DB
7. Set cookie: session_id=<uuid>, HttpOnly, Secure, SameSite=Lax, Max-Age=SESSION_TTL_SECS
8. Redirect to /tenders
```

## 2. Валидация сессии (per-request dependency)

```
get_current_user(request) → User:
    session_id = request.cookies.get("session_id") → None → redirect /login
    session = DB.get(UserSession, session_id) → None → clear cookie → redirect /login
    session.expires_at < now() → DELETE session → redirect /login
    return session.user  # loaded via join
```

## 3. Logout

```
POST /logout:
    session_id = cookie
    DELETE UserSession WHERE session_id=?
    response.delete_cookie("session_id")
    redirect /login
```

## 4. Список тендеров (US-04) с пагинацией

```
GET /tenders?page=N&platform=X&status=Y&search=Z

1. page_size = 20; offset = (page-1) * page_size
2. tenders = TenderRepository.get_qualified(platform, search, limit=page_size+1, offset=offset)
3. has_next = len(tenders) > page_size; tenders = tenders[:page_size]
4. For each tender: is_new = NOT EXISTS TenderView(tender.id, current_user.id)
5. Render tenders/list.html(tenders, is_new_map, page, has_next, filters)
```

## 5. Карточка тендера + mark viewed (US-04)

```
GET /tenders/{id}:
    tender = TenderRepository.get_by_id(id) → 404 if None
    # Mark as viewed (upsert — idempotent)
    INSERT INTO tender_views(tender_id, user_id, viewed_at)
    VALUES(id, current_user.id, now())
    ON CONFLICT (tender_id, user_id) DO NOTHING
    # Latest AI analysis
    ai_analysis = TenderRepository.get_latest_analysis(id)
    Render tenders/detail.html(tender, ai_analysis, current_user)
```

## 6. Экспорт JSONL + AGENTS.md (US-03, Q3:A)

```
GET /export/zip?ids=1,2,3 (или без ids → все qualified)

ExportService.build_export_bundle(tender_ids: list[str] | None):
    # JSONL content
    if tender_ids:
        tenders = [TenderRepository.get_by_id(id) for id in tender_ids]
    else:
        tenders = TenderRepository.get_qualified(limit=1000)
    jsonl = "\n".join(t.to_jsonl_dict() for t in tenders)

    # AGENTS.md: static base + dynamic semantic_profile (Q6:C)
    base_md = Path("AGENTS.md").read_text(encoding="utf-8")
    config = yaml.safe_load(Path("filters/config.yaml").read_text())
    profile_block = _render_profile_block(config["semantic_profile"])
    agents_md = base_md.replace("{{SEMANTIC_PROFILE}}", profile_block)

    # ZIP in memory
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"tenders_{date}.jsonl", jsonl)
        zf.writestr("AGENTS.md", agents_md)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=tender_export_{date}.zip"})
```

## 7. Загрузка AI-анализа (US-05)

```
POST /tenders/{id}/analysis
    Body: {ai_tier: "⭐"|"🟡"|"🟠"|"🔴", ai_rationale: str, ai_tool: str|None}

    Validate: ai_tier in VALID_TIERS; ai_rationale len 1-2000
    TenderRepository.save_analysis(id, AnalysisResult(...), user_id=current_user.id)
    ActionLogRepository.append(TenderAction(tender_id=id, action_type="ai_analysis", ...))
    Redirect /tenders/{id} (PRG pattern)
```

## 8. Принятие решения (US-06)

```
POST /tenders/{id}/action
    Body: {action: "taken"|"rejected"|"deferred", notes: str|None}

    Validate: action in VALID_ACTIONS; notes max 500 chars
    action_obj = TenderAction(tender_id=id, action_type=action, user_id=current_user.id, notes=notes)
    TenderRepository.save_action(action_obj)   → обновляет tender.status в PostgreSQL
    ActionLogRepository.append(action_obj)      → дописывает в JSONL
    Redirect /tenders (PRG pattern, не /tenders/{id})
```

## 9. История тендеров (US-07)

```
GET /history?platform=X&status=Y&user=Z&from=DATE&to=DATE&search=Q&page=N

    filters = HistoryFilters(platform, status, user_id, date_from, date_to, search,
                              limit=20, offset=(page-1)*20)
    tenders_with_actions = TenderRepository.get_history(filters)
    Render history/list.html(items, filters, page, has_next)
```

## 10. CLI: add-user

```
python -m web.cli add-user --username EMAIL --password PASS [--role analyst]

1. Validate username is unique
2. password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
3. INSERT INTO users(id=uuid4(), username, password_hash, role, is_active=True, created_at=now())
4. Print "User created: {username} ({role})"
```
