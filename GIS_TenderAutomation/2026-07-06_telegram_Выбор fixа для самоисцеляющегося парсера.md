# Выбор fix'а для самоисцеляющегося парсера

- **Сессия:** `20260706_080922_1495a8f4`
- **Источник:** telegram
- **Период:** 2026-07-06 08:09 → 2026-08-15 08:25
- **Сообщений:** 276
- **Токены:** in=564,615 out=56,859 (≈621K)

## Цель

[Replying to: "Cronjob Response: HH.ru Scraping Loop — самоисцеляющийся парсер
(job_id: 1bd418be2920)
HH.ru Pipeline — Cron Report
Результаты по конфигам
Сводка по БД
• SDR: 781 вакансий, 43 matched, 43 approved
• Tender: 1057 вакансий, 201 matched, 201 approved
• GTM: 1439 вакансий, 54 matched, 54 approved
• Ghostwriter: 415 вакансий, 4 matched, 4 approved
Проблемы
1. Все скрапинги кроме SDR не завершились — таймаут 600s. Early-stop не сработал (много новых карточек на первом же запросе — 100 карточек × ~6s ="]

[Anatoliy Ivanov] Так, что делать будем? Во первых анти капча сработала ли? Во вторых как мы можем пораньше ловить тайм-аут и прекращать парсинг?

## Файлы (созданы/изменены)

- `C:\Users\A\Desktop\longread-1-ai-automation-agency.md`
- `C:\Users\A\Desktop\longread-2-geo-aeo-agency.md`
- `C:\Users\A\Desktop\longread-3-vibe-coding-solo-saas.md`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\_check_key.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\_cleanup.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\_v.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\_verify_syntax.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\_vs.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\ai_review.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\captcha_solver.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\run_all_configs.py`
- `C:\Users\A\Documents\Claude\Projects\HH_parsing_Hermes\search_pw.py`

## Итог / результат

Готово. Три лонгрида лежат на рабочем столе:

| # | Файл | Тема | Размер |
|---|------|------|--------|
| 1 | `longread-1-ai-automation-agency.md` | AI Automation Agency — как строить на $10-50K/мес | 9.6K |
| 2 | `longread-2-geo-aeo-agency.md` | GEO/AEO — ранжирование в ChatGPT/Perplexity | 10.2K |
| 3 | `longread-3-vibe-coding-solo-saas.md` | Vibe Coding + One-Person Company | 11.2K |

**Прямые ссылки на источники (внутри файлов тоже есть):**

- Dan Martell, «25 Legit Ways to Make Money in 2026 Using AI» — https://www.danmartell.com/25-legit-ways-to-make-money-in-2026-using-ai-beginner-to-advanced
- Naoma AI, «Как заработать на ИИ в 2026» (рус.) — https://naoma.ai/ru/articles/how-to-make-money-with-ai-2026
- Powered by Search, «AEO: How to Rank on ChatGPT and Perplexity in 2026» — https://www.poweredbysearch.com/blog/aeo-llm-seo-best-practices
- Taskade, «Why One-Person Companies Are the Future of Work (2026)» — https://www.taskade.com/blog/one-person-companies
- Sabrina Ramonov, «12 Ways to Make Money in 2026 (with AI)» — https://www.youtube.com/watch?v=qI68bYCN_9o
- Shopify, «20 бизнес-идей на основе ИИ» — https://www.shopify.com/by/blog/ai-business-ideas
- Medium, «Vibe Coding Your Way to a SaaS» — https://ai.plainenglish.io/vibe-coding-your-way-to-a-saas-how-solo-founders-are-shipping-faster-than-ever-0642d49b3466

Сказать, какой лонгрид расписать под конкретный план действий под твой профиль?

Свежее за последние дни. Главное:

---

## 1. Stripe: 63% новых компаний — соло-основатели

Stripe Atlas (инкорпорация C-corp в США): **в Q2 2026 две трети всех новых компаний основаны одним человеком.** Это не «запасной вариант» — это новый стандарт.

AI-native соло-стартапы генерируют **в 2.3× больше выручки к 24-му месяцу**, чем не-AI соло-стартапы.

Источник: https://solofounders.com/blog/solo-founders-are-63-of-new-startups-in-2026-stripe

---

## 2. Новая экономика AI-продуктов: per-seat pricing умер

Ключевой инсайт из статьи «7 AI Business Models» (опубликовано **вчера**, 7 июля):

Традиционный SaaS: 80-90% маржинальность (добавить пользователя почти ничего не стоит).
AI-продукт: **50-60% маржинальности** — каждый запрос жжёт compute. Один agent loop с retries может спалить 50 000 токенов.

**Главная ошибка соло-основателей:** копировать SaaS-ценообразование 2019 года. $9/мес «unlimited» план с AI — быстрый путь к банкротству.

**Что работает:** гибридная модель — base subscription ($29-49/мес) + consumption overage. **70% новых AI-компаний используют 
