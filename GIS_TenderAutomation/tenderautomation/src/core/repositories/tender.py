from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator
from uuid import uuid4

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from core.db import SessionLocal
from core.models import (
    AnalysisResult,
    CollectionResult,
    HistoryFilters,
    InspectionApplyResult,
    InspectionApplyStatus,
    TenderAction,
    InspectionErrorCategory,
    InspectionSource,
    ProcedureState,
    TenderModel,
    TenderInspectionResult,
    TenderStatus,
    compute_content_hash,
)
from core.orm import CollectionRunORM, TenderActionORM, TenderORM
from core.logging import get_logger

log = get_logger(__name__)

_BIDZAAR_CANONICAL_PREFIX = "https://bidzaar.com/app/process/light/"
_RECONCILIATION_ADVISORY_LOCK_ID = 926_393_572_214


class ExportPersistenceError(RuntimeError):
    """Safe repository boundary error without database details."""


class TenderRepository:
    @staticmethod
    def _reconciliation_predicate() -> ColumnElement[bool]:
        canonical_url = literal(_BIDZAAR_CANONICAL_PREFIX).concat(
            TenderORM.external_id
        )
        return or_(
            TenderORM.deadline.is_(None),
            and_(
                TenderORM.platform == "bidzaar",
                TenderORM.url != canonical_url,
            ),
        )

    @staticmethod
    def _validate_batch_size(limit: int) -> None:
        if isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")

    def get_reconciliation_candidates(self, limit: int = 50) -> list[TenderModel]:
        self._validate_batch_size(limit)
        with SessionLocal() as session:
            rows = session.execute(
                select(TenderORM)
                .where(self._reconciliation_predicate())
                .order_by(TenderORM.updated_at.desc(), TenderORM.id.asc())
                .limit(limit)
            ).scalars().all()
            return [self.orm_to_model(row) for row in rows]

    @staticmethod
    def _validate_export_limit(limit: int) -> None:
        if isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("export limit must be between 1 and 50")

    def get_export_candidates(
        self,
        tender_ids: tuple[str, ...] | None = None,
        *,
        limit: int = 50,
        additional_ids: tuple[str, ...] = (),
        additional_titles: tuple[str, ...] = (),
    ) -> list[TenderModel]:
        self._validate_export_limit(limit)
        if tender_ids is not None:
            if not tender_ids or len(tender_ids) > 50:
                raise ValueError("tender_ids must contain between 1 and 50 IDs")
            with SessionLocal() as session:
                rows = session.execute(
                    select(TenderORM).where(TenderORM.id.in_(tender_ids))
                ).scalars().all()
            by_id = {row.id: self.orm_to_model(row) for row in rows}
            return [by_id[tender_id] for tender_id in tender_ids if tender_id in by_id]

        predicates: list[ColumnElement[bool]] = [
            TenderORM.qualification_tier == "qualified"
        ]
        if additional_ids:
            predicates.append(TenderORM.id.in_(additional_ids))
        if additional_titles:
            predicates.append(TenderORM.title.in_(additional_titles))
        with SessionLocal() as session:
            rows = session.execute(
                select(TenderORM)
                .where(or_(*predicates))
                .order_by(TenderORM.collected_at.desc(), TenderORM.id.asc())
                .limit(limit)
            ).scalars().all()
            return [self.orm_to_model(row) for row in rows]

    def apply_inspection(
        self, inspection: TenderInspectionResult
    ) -> InspectionApplyResult:
        try:
            with SessionLocal() as session:
                row = session.get(TenderORM, inspection.tender_id, with_for_update=True)
                if row is None:
                    return InspectionApplyResult(
                        tender_id=inspection.tender_id,
                        status=InspectionApplyStatus.MISSING,
                    )

                latest = row.procedure_last_attempt_at
                if latest is not None and inspection.attempted_at < latest:
                    return InspectionApplyResult(
                        tender_id=inspection.tender_id,
                        status=InspectionApplyStatus.STALE,
                    )
                if latest is not None and inspection.attempted_at == latest:
                    status = (
                        InspectionApplyStatus.IDEMPOTENT
                        if self._inspection_matches(row, inspection)
                        else InspectionApplyStatus.CONFLICT
                    )
                    return InspectionApplyResult(tender_id=inspection.tender_id, status=status)

                if not inspection.verified:
                    row.procedure_last_attempt_at = inspection.attempted_at
                    row.procedure_source = inspection.source.value
                    row.procedure_error_category = (
                        inspection.error_category.value
                        if inspection.error_category is not None
                        else InspectionErrorCategory.UNKNOWN.value
                    )
                    session.commit()
                    return InspectionApplyResult(
                        tender_id=inspection.tender_id,
                        status=InspectionApplyStatus.APPLIED,
                    )

                business_changed = False
                for name in ("buyer", "budget", "deadline", "description", "published_at"):
                    value = getattr(inspection, name)
                    if value is not None and getattr(row, name) != value:
                        setattr(row, name, value)
                        business_changed = True
                if inspection.raw_data_updates:
                    merged_raw = {**(row.raw_data or {}), **inspection.raw_data_updates}
                    if merged_raw != (row.raw_data or {}):
                        row.raw_data = merged_raw
                        business_changed = True

                row.procedure_state = inspection.state.value
                row.procedure_checked_at = inspection.attempted_at
                row.procedure_last_attempt_at = inspection.attempted_at
                row.procedure_source = inspection.source.value
                row.procedure_error_category = None
                if business_changed:
                    row.content_hash = compute_content_hash(
                        row.title,
                        row.buyer,
                        Decimal(str(row.budget)) if row.budget is not None else None,
                        row.deadline,
                        row.description,
                    )
                    row.updated_at = inspection.attempted_at
                session.commit()
                return InspectionApplyResult(
                    tender_id=inspection.tender_id,
                    status=InspectionApplyStatus.APPLIED,
                    business_changed=business_changed,
                )
        except SQLAlchemyError as exc:
            log.warning(
                "export_inspection_persistence_failed",
                extra={"context": {"tender_id": inspection.tender_id}},
            )
            raise ExportPersistenceError("inspection persistence failed") from exc

    @staticmethod
    def _inspection_matches(row: TenderORM, inspection: TenderInspectionResult) -> bool:
        if inspection.verified:
            if row.procedure_checked_at != inspection.attempted_at:
                return False
            if row.procedure_state != inspection.state.value:
                return False
            for name in ("buyer", "budget", "deadline", "description", "published_at"):
                value = getattr(inspection, name)
                if value is not None and getattr(row, name) != value:
                    return False
            return True
        expected_error = (
            inspection.error_category.value
            if inspection.error_category is not None
            else InspectionErrorCategory.UNKNOWN.value
        )
        return row.procedure_error_category == expected_error

    def count_reconciliation_candidates(self) -> int:
        with SessionLocal() as session:
            count = session.execute(
                select(func.count()).select_from(TenderORM).where(
                    self._reconciliation_predicate()
                )
            ).scalar_one()
            return int(count)

    def apply_reconciliation_update(
        self,
        tender_id: str,
        *,
        deadline: datetime | None = None,
        url: str | None = None,
        raw_data_updates: dict[str, object] | None = None,
    ) -> tuple[bool, bool]:
        """Conditionally correct one row and return deadline/url update flags."""
        if deadline is not None and (
            deadline.tzinfo is None or deadline.utcoffset() is None
        ):
            raise ValueError("deadline must be timezone-aware")

        with SessionLocal() as session:
            row = session.get(TenderORM, tender_id)
            if row is None:
                return False, False

            deadline_updated = False
            url_updated = False
            if row.deadline is None and deadline is not None:
                row.deadline = deadline.astimezone(timezone.utc)
                deadline_updated = True
            if url is not None and row.url != url:
                row.url = url
                url_updated = True

            if deadline_updated or url_updated:
                if raw_data_updates:
                    raw_data = dict(row.raw_data or {})
                    raw_data.update(raw_data_updates)
                    row.raw_data = raw_data
                row.content_hash = compute_content_hash(
                    row.title,
                    row.buyer,
                    Decimal(str(row.budget)) if row.budget is not None else None,
                    row.deadline,
                    row.description,
                )
                row.updated_at = datetime.now(timezone.utc)
                session.commit()
            return deadline_updated, url_updated

    @contextmanager
    def reconciliation_lock(self) -> Iterator[bool]:
        """Hold a PostgreSQL advisory lock across a bounded reconciliation run."""
        session = SessionLocal()
        acquired = False
        try:
            acquired = bool(
                session.execute(
                    select(func.pg_try_advisory_lock(_RECONCILIATION_ADVISORY_LOCK_ID))
                ).scalar_one()
            )
            yield acquired
        finally:
            if acquired:
                session.execute(
                    select(func.pg_advisory_unlock(_RECONCILIATION_ADVISORY_LOCK_ID))
                )
            session.close()

    def save_batch(self, tenders: list[TenderModel]) -> CollectionResult:
        if not tenders:
            return CollectionResult(platform="unknown")

        platform = tenders[0].platform
        result = CollectionResult(platform=platform)

        for tender in tenders:
            try:
                with SessionLocal() as session:
                    stmt = (
                        insert(TenderORM)
                        .values(
                            id=tender.id,
                            platform=tender.platform,
                            external_id=tender.external_id,
                            title=tender.title,
                            buyer=tender.buyer,
                            budget=float(tender.budget) if tender.budget else None,
                            deadline=tender.deadline,
                            description=tender.description,
                            url=tender.url,
                            raw_data=tender.raw_data,
                            content_hash=tender.content_hash,
                            prefilter_score=tender.prefilter_score,
                            qualification_tier=tender.qualification_tier,
                            matched_keywords=tender.matched_keywords,
                            status=tender.status.value,
                            published_at=tender.published_at,
                            collected_at=tender.collected_at,
                            updated_at=tender.updated_at,
                            procedure_state=tender.procedure_state.value,
                            procedure_checked_at=tender.procedure_checked_at,
                            procedure_last_attempt_at=tender.procedure_last_attempt_at,
                            procedure_source=(
                                tender.procedure_source.value
                                if tender.procedure_source is not None
                                else None
                            ),
                            procedure_error_category=(
                                tender.procedure_error_category.value
                                if tender.procedure_error_category is not None
                                else None
                            ),
                        )
                        .on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "title": insert(TenderORM).excluded.title,
                                "buyer": insert(TenderORM).excluded.buyer,
                                "budget": insert(TenderORM).excluded.budget,
                                "deadline": insert(TenderORM).excluded.deadline,
                                "description": insert(TenderORM).excluded.description,
                                "raw_data": insert(TenderORM).excluded.raw_data,
                                "content_hash": insert(TenderORM).excluded.content_hash,
                                "updated_at": insert(TenderORM).excluded.updated_at,
                            },
                            where=(TenderORM.content_hash != insert(TenderORM).excluded.content_hash),
                        )
                    )
                    session.execute(stmt)
                    session.commit()
                    result.new_count += 1
            except Exception as e:
                result.failed_count += 1
                log.warning(
                    "tender_save_failed",
                    extra={"context": {"tender_id": tender.id, "error": str(e)}},
                )

        return result

    def get_by_status(self, status: str) -> list[TenderModel]:
        with SessionLocal() as session:
            rows = session.execute(
                select(TenderORM).where(TenderORM.status == status)
            ).scalars().all()
            return [self.orm_to_model(r) for r in rows]

    def update_qualification(
        self,
        tender_id: str,
        score: int,
        tier: str,
        matched_keywords: list[str],
    ) -> None:
        with SessionLocal() as session:
            row = session.get(TenderORM, tender_id)
            if row:
                row.prefilter_score = score
                row.qualification_tier = tier
                row.matched_keywords = matched_keywords
                row.status = tier  # "qualified" or "filtered"
                session.commit()

    def get_qualified(
        self,
        platform: str | None = None,
        since: datetime | None = None,
        limit: int = 200,
        hide_expired: bool = False,
    ) -> list[TenderModel]:
        with SessionLocal() as session:
            q = select(TenderORM).where(TenderORM.qualification_tier == "qualified")
            if platform:
                q = q.where(TenderORM.platform == platform)
            if since:
                q = q.where(TenderORM.collected_at >= since)
            if hide_expired:
                from datetime import datetime as dt, timezone
                now = dt.now(timezone.utc)
                q = q.where(
                    (TenderORM.deadline >= now) | (TenderORM.deadline == None)  # noqa: E711
                )
            q = q.order_by(TenderORM.collected_at.desc()).limit(limit)
            return [self.orm_to_model(r) for r in session.execute(q).scalars().all()]

    def get_by_id(self, tender_id: str) -> TenderModel | None:
        with SessionLocal() as session:
            row = session.get(TenderORM, tender_id)
            return self.orm_to_model(row) if row else None

    def get_all(self) -> list[TenderModel]:
        with SessionLocal() as session:
            rows = session.execute(select(TenderORM)).scalars().all()
            return [self.orm_to_model(r) for r in rows]

    def set_status(self, tender_id: str, status: str) -> None:
        with SessionLocal() as session:
            row = session.get(TenderORM, tender_id)
            if row:
                row.status = status
                session.commit()

    def save_action(self, action: TenderAction) -> None:
        with SessionLocal() as session:
            orm = TenderActionORM(
                id=action.id,
                tender_id=action.tender_id,
                action_type=action.action_type,
                user_id=action.user_id,
                notes=action.notes,
                ai_tier=action.ai_tier,
                ai_rationale=action.ai_rationale,
                ai_tool=action.ai_tool,
                created_at=action.created_at,
            )
            session.add(orm)
            # Update tender status for decision actions
            if action.action_type in ("taken", "rejected", "deferred"):
                row = session.get(TenderORM, action.tender_id)
                if row:
                    row.status = action.action_type
            session.commit()

    def save_analysis(self, tender_id: str, analysis: AnalysisResult, user_id: str) -> None:
        action = TenderAction(
            tender_id=tender_id,
            action_type="ai_analysis",
            user_id=user_id,
            ai_tier=analysis.ai_tier,
            ai_rationale=analysis.ai_rationale,
            ai_tool=analysis.ai_tool,
        )
        self.save_action(action)

    def get_history(self, filters: HistoryFilters) -> list[TenderModel]:
        with SessionLocal() as session:
            q = select(TenderORM).where(
                TenderORM.status.in_(["taken", "rejected", "deferred", "in_review"])
            )
            if filters.platform:
                q = q.where(TenderORM.platform == filters.platform)
            if filters.status:
                q = q.where(TenderORM.status == filters.status)
            if filters.search:
                q = q.where(
                    TenderORM.title.ilike(f"%{filters.search}%")
                    | TenderORM.buyer.ilike(f"%{filters.search}%")
                )
            q = q.order_by(TenderORM.updated_at.desc()).offset(filters.offset).limit(filters.limit)
            return [self.orm_to_model(r) for r in session.execute(q).scalars().all()]

    def log_collection_run(
        self,
        platform: str,
        status: str,
        new_count: int = 0,
        updated_count: int = 0,
        error: str | None = None,
        attempt: int = 1,
    ) -> None:
        with SessionLocal() as session:
            run = CollectionRunORM(
                id=uuid4(),
                platform=platform,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status=status,
                new_tenders_count=new_count,
                updated_tenders_count=updated_count,
                error_message=error,
                attempt_number=attempt,
            )
            session.add(run)
            session.commit()

    def get_last_success_at(self, platform: str) -> datetime | None:
        from sqlalchemy import and_, func
        with SessionLocal() as session:
            result = session.execute(
                select(func.max(CollectionRunORM.completed_at)).where(
                    and_(
                        CollectionRunORM.platform == platform,
                        CollectionRunORM.status == "success",
                    )
                )
            ).scalar()
            return result

    @staticmethod
    def orm_to_model(row: TenderORM) -> TenderModel:
        from decimal import Decimal
        return TenderModel(
            id=row.id,
            platform=row.platform,
            external_id=row.external_id,
            title=row.title,
            buyer=row.buyer,
            budget=Decimal(str(row.budget)) if row.budget is not None else None,
            deadline=row.deadline,
            description=row.description,
            url=row.url,
            raw_data=row.raw_data or {},
            content_hash=row.content_hash,
            prefilter_score=row.prefilter_score,
            qualification_tier=row.qualification_tier,
            matched_keywords=row.matched_keywords or [],
            status=TenderStatus(row.status),
            published_at=row.published_at,
            collected_at=row.collected_at,
            updated_at=row.updated_at,
            procedure_state=ProcedureState(
                getattr(row, "procedure_state", None) or "unknown"
            ),
            procedure_checked_at=getattr(row, "procedure_checked_at", None),
            procedure_last_attempt_at=getattr(
                row, "procedure_last_attempt_at", None
            ),
            procedure_source=(
                InspectionSource(source)
                if (source := getattr(row, "procedure_source", None))
                else None
            ),
            procedure_error_category=(
                InspectionErrorCategory(category)
                if (category := getattr(row, "procedure_error_category", None))
                else None
            ),
        )
