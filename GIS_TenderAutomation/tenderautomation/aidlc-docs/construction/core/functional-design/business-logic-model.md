# Business Logic Model — Unit 1: Core Library

## 1. Content Hash (уpsert-детектор)

**Назначение**: определить, изменился ли тендер с момента последнего сбора.

**Алгоритм**:
```
input:  title, buyer, budget, deadline, description
step 1: нормализовать каждое поле:
        - str → strip() + lower()
        - None → пустая строка ""
        - Decimal → str с фиксированной точностью (2 знака)
        - datetime → ISO 8601 без timezone (UTC)
step 2: собрать словарь с сортированными ключами
step 3: json.dumps(dict, sort_keys=True, ensure_ascii=False)
step 4: SHA-256(utf-8 bytes) → hex digest
output: str (64 hex символа)
```

**Свойства**: детерминированный, независимый от порядка полей, коллизии исключены для этих полей.

---

## 2. Tier 1 Scoring (QualificationEngine)

**Назначение**: быстрая keyword-фильтрация без LLM.

**Алгоритм**:
```
input:  tender (title + description), rules: list[KeywordRule], config: QualificationConfig

score = 0
for rule in rules:
    text = f"{tender.title} {tender.description or ''}".lower()
    
    matched = match(rule.term, text, rule.match_type)
    # match_type:
    #   exact:    term == text (целое слово, word boundary)
    #   contains: term in text
    #   regex:    re.search(rule.term, text, re.IGNORECASE)
    
    if matched:
        if rule.weight < 0:   # blacklist
            return 0, []      # немедленный выход, score = 0
        else:                  # whitelist
            score += rule.weight
            matched_terms.append(rule.term)

return score, matched_terms
```

**Квалификация**:
```
if score >= config.threshold:
    tier = "qualified"
else:
    tier = "filtered"
```

**Свойства**:
- Blacklist имеет абсолютный приоритет: одно совпадение с blacklist → score=0
- score всегда ≥ 0
- Детерминирован: один и тот же tender + rules → один и тот же score

---

## 3. Upsert Logic (TenderRepository.save_batch)

**Назначение**: сохранить новые тендеры, обновить изменившиеся, пропустить неизменные.

**Алгоритм**:
```
for tender in batch:
    existing = SELECT * FROM tenders WHERE id = tender.id
    
    if existing is None:
        # Новый тендер
        INSERT tender WITH status='pending', collected_at=now()
        new_count += 1
    
    elif existing.content_hash == tender.content_hash:
        # Не изменился — пропускаем
        skip_count += 1
    
    else:
        # Изменился контент
        UPDATE tenders SET
            title = tender.title,
            buyer = tender.buyer,
            budget = tender.budget,
            deadline = tender.deadline,
            description = tender.description,
            raw_data = tender.raw_data,
            content_hash = tender.content_hash,
            updated_at = now()
        WHERE id = tender.id
        # ВАЖНО: status, prefilter_score, qualification_tier НЕ сбрасываются
        updated_count += 1

return CollectionResult(new=new_count, updated=updated_count, skipped=skip_count)
```

**Правило**: обновление контента не сбрасывает квалификацию. Re-квалификация только явная операция.

---

## 4. Retry with Exponential Backoff (CollectionService)

**Назначение**: устойчивость к временным сетевым сбоям.

**Алгоритм**:
```
MAX_ATTEMPTS = 3
BASE_DELAY_SEC = 1
BACKOFF_FACTOR = 2

RETRYABLE_ERRORS = [NetworkTimeout, ConnectionError, HTTP_5xx]
NON_RETRYABLE_ERRORS = [HTTP_401, HTTP_403, AuthError]

for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        result = adapter.fetch_new(session, since, descriptor)
        log_collection_run(platform, status='success', attempt=attempt)
        return result
    
    except NON_RETRYABLE_ERRORS as e:
        log_collection_run(platform, status='auth_error', error=str(e))
        raise CollectionAuthError(platform, e)   # не retry
    
    except RETRYABLE_ERRORS as e:
        if attempt == MAX_ATTEMPTS:
            log_collection_run(platform, status='failed', error=str(e))
            return CollectionError(platform, e)   # не прерываем pipeline
        
        delay = BASE_DELAY_SEC * (BACKOFF_FACTOR ** (attempt - 1))
        # delays: 1s, 2s, 4s
        sleep(delay)
```

---

## 5. Pipeline Orchestration (PipelineOrchestrator)

**Назначение**: полный цикл cron-запуска.

**Алгоритм**:
```
async def run() -> PipelineResult:
    pipeline_start = now()
    
    # Шаг 1: Сбор со всех площадок
    collection_results = await CollectionService.run_all()
    # Ошибка одной площадки не останавливает другие
    
    # Шаг 2: Квалификация всех pending тендеров
    qualification_result = QualificationService.qualify_pending()
    
    # Шаг 3: Публикация события (если есть новые кандидаты)
    if qualification_result.qualified_count > 0:
        EventBus.publish(
            'tenders_qualified',
            count=qualification_result.qualified_count,
            platform_summary=collection_results.by_platform()
        )
    
    # Шаг 4: Логирование итога
    return PipelineResult(
        duration=now() - pipeline_start,
        collection=collection_results,
        qualification=qualification_result,
    )
```

---

## 6. Qualification Service (QualificationService.qualify_pending)

**Назначение**: квалифицировать все тендеры в статусе `pending`.

**Алгоритм**:
```
def qualify_pending() -> QualificationResult:
    config = QualificationEngine.load_rules(rules_path)
    pending = TenderRepository.get_by_status('pending')
    
    qualified_list = []
    for tender in pending:
        score, matched_keywords = QualificationEngine.score_tier1(tender, config.rules)
        tier = "qualified" if score >= config.threshold else "filtered"
        
        TenderRepository.update_qualification(
            tender_id=tender.id,
            score=score,
            tier=tier,
            matched_keywords=matched_keywords,
            new_status=tier  # pending → qualified / filtered
        )
        
        if tier == "qualified":
            qualified_list.append(tender)
    
    # Запись квалифицированных в JSONL-лог
    if qualified_list:
        QualifiedLogRepository.append_batch(qualified_list)
    
    return QualificationResult(
        total=len(pending),
        qualified_count=len(qualified_list),
        filtered_count=len(pending) - len(qualified_list)
    )
```

---

## 7. JSONL Export Format

**Назначение**: машиночитаемый вывод для AI-агента.

**Схема одной строки** (стандартный уровень, Q8:B):
```json
{
  "id": "bidzaar_12345",
  "platform": "bidzaar",
  "title": "Разработка ПО для мониторинга инфраструктуры",
  "buyer": "ООО Ромашка",
  "budget": "1500000.00",
  "deadline": "2026-07-15T23:59:00Z",
  "url": "https://bidzaar.com/tenders/12345",
  "description": "Заказчику требуется...",
  "prefilter_score": 150,
  "qualification_tier": "qualified",
  "matched_keywords": ["мониторинг", "инфраструктура", "devops"],
  "published_at": "2026-06-01T10:00:00Z",
  "exported_at": "2026-06-03T08:00:00Z"
}
```

**Правила формата**:
- Одна строка = один тендер (validiный JSON)
- `budget`: строка с двумя знаками после запятой (избегаем float-проблем)
- datetime: ISO 8601 UTC
- `matched_keywords`: список строк, может быть пустым `[]`
- Файл append-only, кодировка UTF-8

---

## Потоки данных (сводка)

```
[Platform API / HTML]
       │
       ▼ adapter.fetch_new()
  list[RawTender]
       │
       ▼ adapter.map_to_tender()
  list[Tender] (status=pending)
       │
       ▼ TenderRepository.save_batch() ──► PostgreSQL
       │
       ▼ QualificationEngine.score_tier1()
  list[ScoredTender] (score, tier, matched_keywords)
       │
       ▼ TenderRepository.update_qualification() ──► PostgreSQL
       │
       ▼ QualifiedLogRepository.append_batch() ──► tenders.jsonl
       │
       ▼ EventBus.publish('tenders_qualified')
  [NotificationHandler] ──► Telegram
```
