# EI-1 Business Rules

## Classification eligibility

### BR-01

Active tender допускается и в single, и в bulk export, если выполняется хотя бы
одно условие:

- финальная V3 queue равна `P1` или `P2`;
- legacy `qualification_tier` равен `qualified`.

Legacy `filtered` без V3 P1/P2 получает outcome `ineligible`. Пользовательский
workflow status (`taken`, `deferred`, `rejected`) не меняет classification
eligibility.

### BR-02

Classification eligibility проверяется до внешнего вызова. Ineligible tender не
должен расходовать credentials, network budget или rate limit площадки.

## Inspection rules

### BR-03

Live inspection обязательна, когда отсутствует одно из обязательных enrichment
полей, отсутствует успешная проверка, TTL успешной проверки достиг 24 часов либо
состояние неизвестно.

### BR-04

Fresh cached active state можно использовать без live call только при полном
наборе enrichment-полей и возрасте `procedure_checked_at < 24h`.

### BR-05

Просроченный сохранённый deadline немедленно даёт archive outcome. Более новая
последующая verified inspection может вернуть процедуру в active, если площадка
предоставила новый будущий deadline или active state.

## State rules

### BR-06

Archive predicate истинна, когда deadline просрочен либо procedure state входит
в `closed`, `completed`, `cancelled`, `not_found`.

### BR-07

`unknown` никогда не является ready или archive само по себе. Такой результат
является `unverified`.

### BR-08

Latest verified state является авторитетным и может выполнять переходы между
любыми normalized states, включая inactive → active. Каждый переход сохраняет
provenance и successful-check timestamp.

### BR-09

External failure не является verified state transition. Он обновляет только
`procedure_last_attempt_at` и safe `procedure_error_category`, сохраняя последнее
подтверждённое state/checked_at.

## Merge rules

### BR-10

Verified non-null source values перезаписывают buyer, budget, deadline,
description и published_at. Source `null` сохраняет прежнее значение.

### BR-11

Merge не изменяет id, platform, external_id, legacy qualification fields,
matched keywords или пользовательский workflow status.

### BR-12

После фактического изменения enrichment fields пересчитываются content hash и
updated_at. Идентичный повторный result не создаёт нового business change.

## Completeness rules

### BR-13

После successful active inspection отсутствующие buyer, deadline, description и
published_at перечисляются в `completeness_warnings`. Наличие warnings не
блокирует export, если active state подтверждён.

### BR-14

Budget не является обязательным completeness field: многие площадки законно не
публикуют НМЦК. Его отсутствие не создаёт warning и не блокирует export.

## Partition and ordering

### BR-15

После deduplication каждый requested ID должен попасть ровно в одну группу:
ready, archived, unverified, ineligible либо missing.

### BR-16

Порядок ready records детерминирован: сохраняется порядок explicit IDs; bulk
использует repository order с ID как стабильным tie-breaker.

## Security rules

### BR-17 — SECURITY-03/15

Core logs включают tender ID, platform и outcome/error category, но не credentials,
cookies, response bodies или description text. Contract/DB failures fail closed.

### BR-18 — SECURITY-05/11

Core принимает уже валидированный и ограниченный request, но дополнительно
отклоняет пустой/превышающий service maximum batch. Это defense in depth против
обхода Web validation.

### BR-19 — SECURITY-13

Repository применяет только typed inspection result с allowlisted fields;
произвольный raw payload не может обновлять ORM columns за пределами raw_data
provenance namespace.

## Testable Properties — PBT-01

### TP-01: Archive invariant — PBT-03

Для любого workflow status вычисление archive predicate не изменяет status.

### TP-02: Inactive invariant — PBT-03

Любой normalized inactive state всегда архивный; `unknown` никогда не ready.

### TP-03: TTL boundary — PBT-03

Возраст проверки `<24h` свежий; возраст `>=24h` stale для любых timezone-aware
timestamps.

### TP-04: Merge null preservation — PBT-03

Source `null` сохраняет старое поле, source non-null становится новым значением.

### TP-05: Merge idempotency — PBT-04

Применение одного verified result дважды эквивалентно однократному применению по
всем observable business fields.

### TP-06: Failure safety — PBT-03

External failure никогда не создаёт inactive state и не меняет last verified
state/checked_at.

### TP-07: Eligibility oracle — PBT-05

Production eligibility равна простому oracle:
`v3_queue in {P1,P2} or legacy_tier == qualified`.

### TP-08: Partition conservation — PBT-03

Множество уникальных requested IDs равно дизъюнктному объединению пяти outcome
groups.

### TP-09: Reopening transition — PBT-06 candidate

Для последовательности verified states observable state всегда равно последнему
verified state; вставка failure-команд не меняет его.

### Generator requirements — PBT-07/08/09/10

- Reusable strategies создают timezone-aware timestamps около TTL/deadline границ.
- Domain strategies генерируют TenderModel, procedure states и partial inspection
  results с реалистичными constraints.
- Hypothesis shrinking остаётся включённым; CI seed воспроизводим.
- Для каждого критического сценария существует example-based regression test
  наряду с property test.
