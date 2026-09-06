"""Text normalization for Scoring v2 — v2.4 (abbreviations, extended prefixes)."""
from __future__ import annotations

import re


def normalize(text: str) -> str:
    """Normalize text for matching — aggressive, handles ИТ/IT, hyphens, ё/е, special chars."""
    t = text.lower()
    t = t.replace("ё", "е")
    # Normalize ИТ/IT variants — convert all to "it"
    t = re.sub(r"\bит\b", "it", t)
    t = re.sub(r"\bит-", "it ", t)
    t = re.sub(r"\bит\s", "it ", t)
    t = re.sub(r"\bit\b", "it", t)
    t = re.sub(r"\bit-", "it ", t)
    t = re.sub(r"\bit\s", "it ", t)
    # Normalize separators — dashes, slashes, colons, semicolons → space
    t = re.sub(r"[-\u2013\u2014\u2012/\\_|:;]", " ", t)
    t = t.replace("\u00a0", " ")  # non-breaking space
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ── Abbreviation expansion (ТЗ §5.2) ─────────────────────────────────────
ABBREVIATIONS: dict[str, str] = {
    "it инфр": "it инфраструктура",
    "ит инфр": "it инфраструктура",
    "ит инфраструктура": "it инфраструктура",
    "цод": "центр обработки данных",
    "схд": "система хранения данных",
    "бд": "база данных",
    "субд": "система управления базами данных",
    "лвс": "локальная вычислительная сеть",
    "ввр": "виртуальные вычислительные ресурсы",
    "рк": "резервное копирование",
    "тп": "техническая поддержка",
    "иб": "информационная безопасность",
    "кии": "критическая информационная инфраструктура",
}


def expand_abbreviations(text: str) -> str:
    """Expand known Russian abbreviations to full forms for better matching."""
    t = text
    for abbr, full in sorted(ABBREVIATIONS.items(), key=lambda item: -len(item[0])):
        t = re.sub(
            rf"(?<!\w){re.escape(abbr)}(?!\w)",
            full,
            t,
        )
    return t


# ── Prefix removal (ТЗ §6) ───────────────────────────────────────────────
PREFIX_PATTERNS: list[str] = [
    r"\brfi\b",
    r"\brfp\b",
    r"\brfq\b",
    r"\bпко\b",
    r"запрос\s+(цен|предложений|информации|коммерческого предложения|цены)",
    r"мониторинг\s+цен",
    r"маркетинговое\s+исследование",
    r"предварительная\s+квалификация",
    r"тендер\s*[№#]?\s*\d*",
    r"конкурс\s*[№#]?\s*\d*",
    r"закупочная\s+процедура\s*[№#]?\s*\d*",
    r"выбор\s+(подрядчика|партн[её]ра|поставщика|исполнителя)",
    r"поиск\s+(подрядчика|партн[её]ра|поставщика|исполнителя)",
    r"закупка\s+услуг\s+по\s+",
    r"закупка\s+услуги\s+по\s+",
    r"на\s+оказание\s+услуг\s+по\s+",
    r"оказание\s+услуг\s+по\s+",
    r"выполнение\s+работ\s+по\s+",
    r"предоставление\s+услуг\s+по\s+",
    r"тендер\s+(на\s+)?(право\s+)?(заключения\s+договора\s+)?",
    r"право\s+заключения\s+договора\s+",
    r"определение\s+поставщика\s+(на\s+)?",
]


def strip_prefixes(text: str) -> str:
    """Remove boilerplate prefixes from tender title for semantic classification."""
    t = text
    for pattern in PREFIX_PATTERNS:
        t = re.sub(r"^" + pattern + r"[:,\s–—-]*", "", t, flags=re.IGNORECASE)
    return t.strip()
