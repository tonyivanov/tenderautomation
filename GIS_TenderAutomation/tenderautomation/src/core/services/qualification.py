from __future__ import annotations

from dataclasses import dataclass

from core.logging import get_logger
from core.repositories import QualifiedLogRepository, TenderRepository
from core.services.qualification_engine import QualificationEngine

log = get_logger(__name__)


@dataclass
class QualificationResult:
    total: int
    qualified_count: int
    in_review_count: int
    filtered_count: int


class QualificationService:
    def __init__(
        self,
        engine: QualificationEngine,
        tender_repo: TenderRepository,
        qualified_log: QualifiedLogRepository,
    ) -> None:
        self._engine = engine
        self._tender_repo = tender_repo
        self._qualified_log = qualified_log

    def qualify_pending(self) -> QualificationResult:
        pending = self._tender_repo.get_by_status("pending")
        if not pending:
            return QualificationResult(total=0, qualified_count=0, in_review_count=0, filtered_count=0)

        qualified_tenders = []
        in_review_tenders = []
        for tender in pending:
            r = self._engine.qualify(tender)
            matched_keywords = [m.phrase for m in r.positive_matches]
            self._tender_repo.update_qualification(tender.id, r.score, r.tier, matched_keywords)

            if r.category == "core":
                tender.prefilter_score = r.score
                tender.matched_keywords = matched_keywords
                tender.qualification_tier = "qualified"
                qualified_tenders.append(tender)
            elif r.category == "review":
                tender.prefilter_score = r.score
                tender.matched_keywords = matched_keywords
                tender.qualification_tier = "in_review"
                in_review_tenders.append(tender)

        if qualified_tenders:
            self._qualified_log.append_batch(qualified_tenders)

        log.info(
            "qualification_complete",
            extra={"context": {
                "total": len(pending),
                "qualified": len(qualified_tenders),
                "in_review": len(in_review_tenders),
                "filtered": len(pending) - len(qualified_tenders) - len(in_review_tenders),
            }},
        )
        return QualificationResult(
            total=len(pending),
            qualified_count=len(qualified_tenders),
            in_review_count=len(in_review_tenders),
            filtered_count=len(pending) - len(qualified_tenders) - len(in_review_tenders),
        )