"""Entry point: python -m core.cli run-pipeline"""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from typing import Any

import click

from core.bootstrap import build_pipeline, build_reconciliation_service
from core.events import EventBus
from core.logging import get_logger
from core.models import ReconciliationCommand, ReconciliationSource
from core.repositories import TenderRepository
from core.services import PipelineOrchestrator

log = get_logger("core.cli")


def _build_orchestrator(event_bus: EventBus) -> PipelineOrchestrator:
    return build_pipeline(event_bus, register_notifications=True)


@click.group()
def main() -> None:
    pass


@main.command("run-pipeline")
def run_pipeline() -> None:
    """Run the full collection + qualification + V3 LLM classification pipeline."""
    event_bus = EventBus()
    orchestrator = _build_orchestrator(event_bus)
    try:
        result = orchestrator.run()
        log.info(
            "pipeline_done",
            extra={"context": {
                "duration_sec": result.duration_sec,
                "qualified": result.qualification.qualified_count,
            }},
        )

        # ── V3 LLM classification (on new + uncached tenders) ──────────
        try:
            _run_v3_classification()
        except Exception as e:
            log.error("v3_classification_failed", extra={"context": {"error": str(e)}})
            # Non-fatal: pipeline continues even if V3 fails

        sys.exit(0)
    except Exception as e:
        log.error("pipeline_fatal", extra={"context": {"error": str(e)}})
        sys.exit(1)


@main.command("reconcile-deadlines")
@click.option(
    "--batch-size",
    type=click.IntRange(1, 200),
    default=50,
    show_default=True,
    help="Maximum number of candidate tenders to process.",
)
def reconcile_deadlines(batch_size: int) -> None:
    """Repair missing deadlines and legacy Bidzaar URLs."""
    command = ReconciliationCommand(
        batch_size=batch_size,
        requested_by="cli",
        source=ReconciliationSource.CLI,
    )
    try:
        result = asyncio.run(build_reconciliation_service().run(command))
    except Exception as exc:
        log.error(
            "deadline_reconciliation_cli_failed",
            extra={"context": {"error_type": type(exc).__name__}},
        )
        raise click.ClickException("deadline reconciliation failed") from exc
    click.echo(json.dumps(asdict(result), sort_keys=True))


def _run_v3_classification() -> None:
    """Run V3 LLM classification on tenders not yet in the cache."""
    from core.services.scoring_v3 import ScoringV3Pipeline
    from core.services.scoring_v3 import cache as v3_cache

    repo = TenderRepository()
    tenders = repo.get_all()

    if not tenders:
        log.info("v3_no_tenders")
        return

    # Filter: only tenders not yet in V3 cache
    uncached = []
    cache_hits = 0
    for t in tenders:
        if v3_cache.get(t.title, tender_id=t.id) is None:
            qr = _get_v1_result(t.id, repo)
            uncached.append({
                "id": t.id,
                "title": t.title,
                "v1_tier": qr.get("tier", ""),
                "v1_score": qr.get("score", 0),
                "v1_category": qr.get("category", ""),
            })
        else:
            cache_hits += 1

    if not uncached:
        log.info("v3_all_cached", extra={"context": {"total": len(tenders), "cached": cache_hits}})
        return

    log.info("v3_classification_start", extra={"context": {"uncached": len(uncached), "cached": cache_hits}})
    pipeline = ScoringV3Pipeline(seed=42)
    result = pipeline.run(uncached, run_legacy=False)
    log.info(
        "v3_classification_done",
        extra={"context": {
            "uncached": len(uncached),
            "p1": result.stats.queue_p1,
            "p2": result.stats.queue_p2,
            "reject": result.stats.queue_reject,
            "cost": f"${result.total_cost:.4f}",
            "tokens": result.total_tokens,
            "time": f"{result.elapsed_seconds:.1f}s",
        }},
    )


def _get_v1_result(tender_id: str, repo: TenderRepository) -> dict[str, Any]:
    """Reconstruct V1 qualification result for a tender."""
    tender = repo.get_by_id(tender_id)
    if not tender:
        return {}
    return {
        "tier": tender.qualification_tier or "",
        "score": tender.prefilter_score,
        "category": "",  # not stored separately in DB
    }


if __name__ == "__main__":
    main()
