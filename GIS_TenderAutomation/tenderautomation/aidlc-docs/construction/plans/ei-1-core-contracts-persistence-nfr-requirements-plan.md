# EI-1 NFR Requirements Plan — Core Contracts & Persistence

## План

- [x] Проанализировать EI-1 Functional Design и cross-unit dependencies.
- [x] Зафиксировать существующий tech stack и обязательные Security/PBT gates.
- [x] Получить и проверить ответы Q1-Q4 ниже.
- [x] Создать `nfr-requirements.md` с измеримыми performance, reliability,
  security, maintainability и compatibility requirements.
- [x] Создать `tech-stack-decisions.md` с выбранными технологиями и rationale.
- [x] Проверить применимые SECURITY-01–SECURITY-15.
- [x] Проверить PBT framework/reproducibility requirements.
- [x] Валидировать измеримость и отсутствие противоречий.

## Вопросы NFR

### Q1: Максимальный размер export batch
Какой service-level maximum должен защищать Core readiness orchestration?

A) Не более 50 уникальных тендеров на один export request (рекомендуется для
bounded пользовательского HTTP flow)

B) Не более 100 уникальных тендеров

C) Сохранить текущий максимум 1000 тендеров

X) Другое (укажите точное число после тега [Answer]: ниже)

[Answer]: A

### Q2: Concurrency и latency budget
Какой профиль принять для live inspection внутри одного export request?

A) До 4 одновременных инспекций, 30 секунд на один внешний вызов, 120 секунд на
весь batch; cached single export должен укладываться в 2 секунды (рекомендуется)

B) Только последовательные инспекции, без общего batch timeout

C) До 10 одновременных инспекций и общий timeout 60 секунд

X) Другое (укажите точные budgets после тега [Answer]: ниже)

[Answer]: A

### Q3: Повторные попытки в пользовательском export flow
Сколько раз Core должен повторять временно неуспешную инспекцию?

A) Не повторять внутри одного request; вернуть unverified/503, чтобы не удваивать
latency и нагрузку площадки (рекомендуется)

B) Одна повторная попытка с коротким exponential backoff

C) До трёх попыток

X) Другое (опишите policy после тега [Answer]: ниже)

[Answer]: A

### Q4: Транзакционная граница batch
Как сохранять результаты частично успешного batch?

A) Отдельная атомарная транзакция на каждый тендер; сбой одного не откатывает
успешные результаты других (рекомендуется)

B) Одна all-or-nothing транзакция на весь batch

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A
