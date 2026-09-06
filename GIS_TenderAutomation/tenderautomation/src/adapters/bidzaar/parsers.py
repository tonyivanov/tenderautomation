from __future__ import annotations

from bs4 import BeautifulSoup

from core.models import DeadlineExtractionOutcome
from core.services.deadlines import resolve_labeled_deadline_lines


def parse_detail_deadline(html: str) -> DeadlineExtractionOutcome:
    soup = BeautifulSoup(html, "html.parser")
    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    return resolve_labeled_deadline_lines(lines, timezone_name="Europe/Moscow")
