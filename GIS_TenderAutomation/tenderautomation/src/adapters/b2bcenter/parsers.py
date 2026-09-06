from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from bs4 import BeautifulSoup
from bs4.element import Tag
from core.models import (
    DeadlineExtractionOutcome,
    DeadlineSource,
)
from core.services.deadlines import (
    normalize_deadline,
    resolve_labeled_deadline_lines,
)

PLATFORM_TIMEZONE = "Europe/Moscow"

_PRICE_CLEANUP = re.compile(r"[^\d,.]")
_LOT_ID_RE = re.compile(r"/market/(\d+)/")


class B2BCenterRawRow(NamedTuple):
    lot_id: str
    title: str
    buyer: str | None
    budget_raw: str | None
    deadline_raw: str | None
    url: str
    search_query: str | None


def parse_price(text: str | None) -> Decimal | None:
    if not text:
        return None
    clean = text.strip().lower()
    if clean in ("", "не указана", "договорная", "по договору", "0"):
        return None
    digits = _PRICE_CLEANUP.sub("", clean).replace(",", ".")
    # Strip trailing dots (e.g. from "500 руб." → "500.")
    digits = digits.rstrip(".")
    if not digits:
        return None
    try:
        value = Decimal(digits)
        return value if value > 0 else None
    except InvalidOperation:
        return None


def parse_deadline(text: str | None) -> datetime | None:
    normalized = normalize_deadline(
        text,
        source=DeadlineSource.LISTING,
        timezone_name=PLATFORM_TIMEZONE,
    )
    return normalized.value if normalized else None


def parse_detail_deadline(html: str) -> DeadlineExtractionOutcome:
    """Extract only explicitly labelled deadline values from a detail page."""
    soup = BeautifulSoup(html, "html.parser")
    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    return resolve_labeled_deadline_lines(
        lines, timezone_name=PLATFORM_TIMEZONE
    )


def parse_total_count(soup: BeautifulSoup) -> int:
    # B2B-Center shows total in a heading like "Найдено: 123 лота"
    for tag in soup.find_all(string=re.compile(r"найдено|результат", re.I)):
        numbers = re.findall(r"\d[\d\s]*", str(tag))
        if numbers:
            try:
                return int(numbers[0].replace(" ", ""))
            except ValueError:
                continue
    # Fallback: count rows
    rows = _find_lot_rows(soup)
    return len(rows)


def parse_rows(html: str, search_query: str | None = None) -> list[B2BCenterRawRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows = _find_lot_rows(soup)
    result = []
    for tr in rows:
        lot_id = _extract_lot_id(tr)
        if not lot_id:
            continue
        # Structure: td[0]=category+title, td[1]=buyer, td[2]=published, td[3]=deadline, td[4]=buttons
        title_raw = _cell_text(tr, 0)
        # Extract title after "Запрос предложений № XXXXXXXX" / "Конкурс № XXXXXXXX" etc.
        # Pattern: "КАТЕГОРИЯ Тип процедуры № НОМЕР РЕКОМЕНДОВАНО Название тендера"
        title_match = re.search(
            r'(?:Запрос предложений|Конкурс|Процедура закупки|Аукцион|Тендер)\s*№\s*\d+\s*(?:РЕКОМЕНДОВАНО\s*)?(.*)',
            title_raw, re.DOTALL
        )
        title = title_match.group(1).strip() if title_match else title_raw

        result.append(B2BCenterRawRow(
            lot_id=lot_id,
            title=title,
            buyer=_cell_text(tr, 1) or None,
            budget_raw=None,  # budget not in listing, only in detail page
            deadline_raw=_extract_deadline(tr),
            url=f"https://www.b2b-center.ru/market/view.html?id={lot_id}",
            search_query=search_query,
        ))
    return result


# Matches both URL formats:
# /market/view.html?id=4477492
# /app/market/{slug}/tender-4469836/
_LOT_HREF_RE = re.compile(r"(?:/market/view\.html\?id=|/tender-)(\d+)")


def _find_lot_rows(soup: BeautifulSoup) -> list[Tag]:
    return [
        tr for tr in soup.find_all("tr")
        if isinstance(tr, Tag) and tr.find("a", href=_LOT_HREF_RE)
    ]


def _extract_lot_id(tr: Tag) -> str | None:
    a = tr.find("a", href=_LOT_HREF_RE)
    if not isinstance(a, Tag):
        return None
    href = a.get("href", "")
    if not isinstance(href, str):
        return None
    m = _LOT_HREF_RE.search(href)
    return m.group(1) if m else None


def _cell_text(tr: Tag, index: int) -> str:
    cells = tr.find_all("td")
    if not cells:
        return ""
    try:
        return str(cells[index].get_text(separator=" ", strip=True))
    except IndexError:
        return ""


def _extract_deadline(tr: Tag) -> str | None:
    # td[3] is deadline (dd.mm.yyyy HH:MM)
    cells = tr.find_all("td")
    if len(cells) >= 4:
        text = str(cells[3].get_text(strip=True))
        if re.match(r"\d{2}\.\d{2}\.\d{4}", text):
            return text
    return None
