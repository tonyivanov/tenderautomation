"""Scoring v3 Pipeline — LLM-based classification with two-pass architecture.

Flow:
1. Load tenders from JSONL/dict list.
2. Check SQLite cache for each title.
3. Batch uncached titles → primary model classification.
4. For low-confidence/disputed → judge model re-classification.
5. Aggregate first + judge → final verdict + queue.
6. Apply P3 stratified sampling.
7. Run legacy v2 as diagnostic (optional).
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import cache as llm_cache
from . import config, models
from .aggregator_v3 import aggregate_single, compute_stats, stratify_p3, AggregationStats
from .post_filter import apply_post_filter
from .title_prep import make_cache_key

logger = logging.getLogger(__name__)


class LLMCallResult(Protocol):
    items: list[models.LLMClassificationItem]
    model_used: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: int
    attempts: int


@dataclass
class PipelineRunResult:
    results: list[models.V3Result] = field(default_factory=list)
    stats: AggregationStats = field(default_factory=AggregationStats)
    cache_hits: int = 0
    cache_misses: int = 0
    primary_batches: int = 0
    judge_batches: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


class ScoringV3Pipeline:
    """Main v3 pipeline with caching, LLM classification, and aggregation."""

    def __init__(self, seed: int = 42) -> None:
        # Reserved for reproducible quality-control sampling, never for security.
        self._rng = random.Random(seed)  # nosec B311

    # ── Core pipeline ─────────────────────────────────────────────────────

    def run(
        self, tenders: list[dict[str, Any]], *, run_legacy: bool = True
    ) -> PipelineRunResult:
        """Run full v3 pipeline on tender list.

        Args:
            tenders: List of dicts with keys id, title, v1_tier, v1_score, v1_category.
            run_legacy: If True, run v2 pipeline as diagnostic (set legacy_* fields).

        Returns:
            PipelineRunResult with all V3Results and aggregated stats.
        """
        return asyncio.run(self.run_async(tenders, run_legacy=run_legacy))

    async def run_async(
        self, tenders: list[dict[str, Any]], *, run_legacy: bool = True
    ) -> PipelineRunResult:
        t0 = time.perf_counter()
        result = PipelineRunResult()

        # Stage 1: Check cache for all titles
        title_to_item: dict[str, models.LLMClassificationItem] = {}
        uncached: list[dict[str, Any]] = []

        for t in tenders:
            title = t.get("title", "")
            if not title:
                continue
            cached = llm_cache.get(title, tender_id=t.get("id") or None)
            if cached is not None:
                title_to_item[title] = cached
                result.cache_hits += 1
            else:
                uncached.append(t)
                result.cache_misses += 1

        # Stage 2: Batch classify uncached titles with primary model
        primary_model_name = ""
        if uncached:
            primary_model_name = await self._classify_uncached(uncached, title_to_item, result, use_judge=False)
            result.primary_batches = max(1, (len(uncached) + config.LLM_BATCH_SIZE - 1) // config.LLM_BATCH_SIZE)

        # Stage 3: Identify candidates needing judge review
        judge_candidates = self._find_judge_candidates(tenders, title_to_item)

        # Stage 4: Judge pass
        judge_model_name = ""
        if judge_candidates:
            judge_items: dict[str, models.LLMClassificationItem] = {}
            judge_model_name = await self._classify_uncached(
                [{"title": t} for t in judge_candidates],
                judge_items,
                result,
                use_judge=True,
            )
            result.judge_batches = max(1, (len(judge_candidates) + config.LLM_BATCH_SIZE - 1) // config.LLM_BATCH_SIZE)
        else:
            judge_items = {}

        # Stage 5: Aggregate each tender
        for t in tenders:
            title = t.get("title", "")
            if not title:
                continue

            fp = title_to_item.get(title)
            if fp is None:
                result.errors.append(f"Missing first_pass for: {title[:80]}")
                continue

            jp = judge_items.get(title)  # None if not sent to judge

            legacy_tier = t.get("v1_tier", "")
            legacy_score = t.get("v1_score", 0)
            legacy_category = t.get("v1_category", "")

            v3r = aggregate_single(
                tender_id=t.get("id", ""),
                title=title,
                first_pass=fp,
                judge_pass=jp,
                legacy_tier=legacy_tier,
                legacy_score=legacy_score,
                legacy_category=legacy_category,
                cache_hit=title in title_to_item and judge_items.get(title) is None,
            )
            v3r.primary_model = config.OPENROUTER_MODEL_PRIMARY
            v3r.primary_model_used = primary_model_name
            v3r.judge_model = config.OPENROUTER_MODEL_JUDGE
            v3r.judge_model_used = judge_model_name
            # v3.2.2: Apply deterministic post-filter
            v3r = apply_post_filter(v3r, title)
            result.results.append(v3r)

        # Stage 6: P3 stratification
        result.results = stratify_p3(result.results)

        # Stage 7: Compute stats
        result.stats = compute_stats(result.results)
        result.elapsed_seconds = round(time.perf_counter() - t0, 2)

        logger.info(
            "V3 pipeline complete: %d tenders, cache=%d/%d, batches=%d/%d, "
            "P1=%d P2=%d P3=%d reject=%d, cost=$%.4f, time=%.1fs",
            len(result.results),
            result.cache_hits, result.cache_misses,
            result.primary_batches, result.judge_batches,
            result.stats.queue_p1, result.stats.queue_p2,
            result.stats.queue_p3, result.stats.queue_reject,
            result.total_cost, result.elapsed_seconds,
        )
        return result

    async def _classify_uncached(
        self,
        items: list[dict[str, Any]],
        title_to_item: dict[str, models.LLMClassificationItem],
        run_result: PipelineRunResult,
        *,
        use_judge: bool = False,
    ) -> str:
        """Classify uncached titles in batches. Returns model name used."""
        titles = [item.get("title", "") for item in items]
        batch_size = config.LLM_BATCH_SIZE
        model_used = ""

        for i in range(0, len(titles), batch_size):
            batch_titles = titles[i:i + batch_size]
            batch_items = items[i:i + batch_size]
            try:
                llm_result = await self._waterfall_classify(batch_titles, use_judge=use_judge)

                for item in llm_result.items:
                    # Map LLM item id back to actual title
                    idx = int(item.id[1:]) - 1 if item.id.startswith("t") else -1  # t1→0, t2→1, ...
                    if 0 <= idx < len(batch_titles):
                        actual_title = batch_titles[idx]
                        title_to_item[actual_title] = item

                        if use_judge:
                            # Store judge result in cache (alongside primary)
                            llm_cache.put_judge(actual_title, item)
                        else:
                            # Store primary result in cache
                            llm_cache.put(
                                actual_title, item,
                                tender_id=batch_items[idx].get("id") or None,
                                model_used=llm_result.model_used,
                                input_tokens=llm_result.input_tokens,
                                output_tokens=llm_result.output_tokens,
                                estimated_cost=llm_result.estimated_cost,
                            )

                run_result.total_tokens += llm_result.input_tokens + llm_result.output_tokens
                run_result.total_cost += llm_result.estimated_cost
                model_used = llm_result.model_used

            except Exception as e:
                logger.error("Batch %d-%d failed: %s", i, i + len(batch_titles), e)
                run_result.errors.append(f"Batch {i}-{i + len(batch_titles)}: {e}")
                # Create fallback items
                for title in batch_titles:
                    title_to_item[title] = models.LLMClassificationItem(
                        id=make_cache_key(title)[:16],
                        verdict=models.Verdict.REVIEW,
                        fit_score=40,
                        confidence=0.3,
                        reason=f"API error: {str(e)[:200]}",
                    )

        return model_used

    def _find_judge_candidates(
        self,
        tenders: list[dict[str, Any]],
        title_to_item: dict[str, models.LLMClassificationItem],
    ) -> list[str]:
        """Determine which titles need judge review based on first pass."""
        candidates: set[str] = set()
        for t in tenders:
            title = t.get("title", "")
            fp = title_to_item.get(title)
            if fp is None:
                continue

            # Check conditions from V3Result.needs_judge
            legacy_cat = t.get("v1_category", "")

            # v3.2.1: Skip judge for obvious non-IT rejects (save API calls)
            is_obvious_non_it = (
                fp.verdict == "reject"
                and str(fp.primary_domain) in ("non_it", "facilities", "web_and_marketing",
                                                "application_software", "office_it", "supply")
                and legacy_cat not in ("core", "review")
                and not any(rf in fp.risk_flags for rf in ("insufficient_context", "ambiguous_title"))
            )
            if is_obvious_non_it:
                continue

            if fp.confidence < config.JUDGE_MIN_CONFIDENCE:
                candidates.add(title)
            elif fp.verdict == models.Verdict.REVIEW:
                candidates.add(title)
            elif fp.verdict == models.Verdict.REJECT and legacy_cat in ("core", "review", "lowish"):
                candidates.add(title)
            elif fp.verdict == models.Verdict.CORE and legacy_cat == "hard_stop":
                candidates.add(title)
            elif fp.procurement_type == "mixed":
                candidates.add(title)
            elif "ambiguous_title" in fp.risk_flags:
                candidates.add(title)
            elif "insufficient_context" in fp.risk_flags:
                candidates.add(title)

        return list(candidates)

    async def _waterfall_classify(
        self,
        batch_titles: list[str],
        *,
        use_judge: bool = False,
    ) -> LLMCallResult:
        """Waterfall classification: try free APIs first, fall back to DeepSeek.

        Primary: Groq Qwen3-32B (free) → DeepSeek V4 (paid) → OpenRouter gemma (free)
        Judge:   Groq Qwen3-32B (free) → DeepSeek V4 (paid) → OpenRouter gemma (free)

        Note: Groq key was 403, so currently defaults to DeepSeek primary.
        Gemini blocked in Russia.
        """
        last_error = None

        # Tier 1: Groq Qwen3-32B (free, 1K req/day)
        if config.GROQ_API_KEY:
            try:
                from .groq_client import classify_batch as groq_classify
                return await groq_classify(batch_titles, use_judge=use_judge, api_key=config.GROQ_API_KEY)
            except Exception as e:
                logger.warning("Groq waterfall failed: %s", e)
                last_error = e

        # Tier 2: DeepSeek V4 Flash (paid, $0.14/$0.28 per 1M tokens)
        if config.DEEPSEEK_API_KEY:
            try:
                from .deepseek_client import classify_batch as deepseek_classify
                return await deepseek_classify(batch_titles, use_judge=use_judge, api_key=config.DEEPSEEK_API_KEY)
            except Exception as e:
                logger.warning("DeepSeek waterfall failed: %s", e)
                last_error = e

        # Tier 3: OpenRouter gemma (free tier)
        if config.OPENROUTER_API_KEY:
            try:
                from .openrouter_client import classify_batch as openrouter_classify
                return await openrouter_classify(batch_titles, use_judge=use_judge)
            except Exception as e:
                logger.warning("OpenRouter waterfall failed: %s", e)
                last_error = e

        raise RuntimeError(f"All classification backends failed. Last error: {last_error}")

    # ── Utility: run on titles only ───────────────────────────────────────

    def classify_titles(self, titles: list[str]) -> list[models.V3Result]:
        """Quick classification of raw title strings (no legacy data)."""
        tenders = [{"id": f"raw_{i}", "title": t, "v1_tier": "", "v1_score": 0, "v1_category": ""}
                   for i, t in enumerate(titles)]
        return self.run(tenders, run_legacy=False).results
