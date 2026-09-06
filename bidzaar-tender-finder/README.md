# Bidzaar tender finder (MVP: parse new)

## Что делает
Собирает **все тендеры Bidzaar, опубликованные после последнего запуска** (по полю «Опубликован DD.MM.YYYY, HH:MM») и сохраняет результаты в `out/run-.../tenders.json`.

## Установка

```bash
npm install
```

Установите браузер для Playwright (Chromium):

```bash
npx playwright install chromium
```

## Первый запуск: сохранить сессию (ручной логин)

```bash
npm run login
```

Откроется браузер. Войдите в Bidzaar вручную. Скрипт сохранит `storageState.json`.

## Парсинг новых тендеров

```bash
npm run parse-new -- --maxPages 10 --maxNew 200 --headful
```

Для headless режима уберите `--headful`.

Опционально скачать документы:

```bash
npm run parse-new -- --downloadDocs
```

## Файлы состояния и результата
- `state.json`: хранит `lastRunAt` (ISO) для определения «новых»\n- `storageState.json`: сохранённая сессия Playwright\n- `out/run-.../tenders.json`: найденные новые тендеры\n- `out/run-.../run.json`: метаданные запуска и ошибки\n- `out/run-.../artifacts/`: скриншоты/HTML при ошибках\n+
