# EI-1 Functional Design Plan — Core Contracts & Persistence

## План

- [x] Загрузить утверждённые requirements, Application Design и unit artifacts.
- [x] Определить функциональные границы EI-1 и contracts для EI-2/EI-3.
- [x] Получить и проверить ответы Q1-Q4 ниже.
- [x] Создать `business-logic-model.md` с readiness flow и state decisions.
- [x] Создать `business-rules.md` с eligibility, archive, merge и error rules.
- [x] Создать `domain-entities.md` с entities, values и relationships.
- [x] Зафиксировать Testable Properties по PBT-01.
- [x] Проверить Security fail-closed rules и ownership.
- [x] Валидировать артефакты и согласованность с FR/NFR/AC.

## Вопросы Functional Design

### Q1: Срок действия подтверждения активности
Когда сохранённое `procedure_state=active` можно использовать без нового live-вызова?

A) В течение 24 часов после успешной проверки; после TTL требуется повторная
инспекция перед экспортом (рекомендуется)

B) Всегда выполнять live-проверку перед каждым экспортом

C) Использовать сохранённое состояние без TTL до следующего планового сбора

X) Другое (укажите точный TTL или правило после тега [Answer]: ниже)

[Answer]: A

### Q2: Merge enrichment-полей
Как применять непустые значения, полученные при новой успешной инспекции?

A) Считать площадку актуальным источником и обновлять buyer, budget, deadline,
description и published_at; `null` из ответа никогда не стирает сохранённое
значение (рекомендуется)

B) Заполнять только ранее пустые поля и никогда не изменять существующие

C) Полностью заменять все поля, включая стирание значением `null`

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A

### Q3: Повторное открытие процедуры
Может ли более новая успешная проверка вернуть архивную процедуру в active?

A) Да; последнее подтверждённое состояние площадки является авторитетным, поэтому
closed/not_found может перейти обратно в active без изменения workflow status
(рекомендуется)

B) Нет; архивное состояние необратимо и требует ручного вмешательства

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A

### Q4: Classification eligibility для bulk и single export
Какие активные тендеры допускаются к экспорту по классификации?

A) Single: V3 P1/P2 либо legacy qualified; Bulk: тот же критерий. Legacy filtered
без V3 P1/P2 не экспортируется (рекомендуется)

B) Single: любой явно выбранный active tender; Bulk: только legacy qualified

C) И single, и bulk: только V3 P1/P2

X) Другое (опишите после тега [Answer]: ниже)

[Answer]: A
