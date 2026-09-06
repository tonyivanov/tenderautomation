import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.services.scoring_v3 import config
from core.services.scoring_v3.models import LLMClassificationItem
from core.services.scoring_v3.pipeline_v3 import PipelineRunResult, ScoringV3Pipeline


def _call_result(item: LLMClassificationItem, model: str = "fake"):
    return SimpleNamespace(
        items=[item],
        model_used=model,
        input_tokens=10,
        output_tokens=5,
        estimated_cost=0.01,
        latency_ms=1,
        attempts=1,
    )


def _core_item(confidence: float = 0.95) -> LLMClassificationItem:
    return LLMClassificationItem(
        id="t1",
        verdict="core",
        fit_score=92,
        confidence=confidence,
        procurement_type="services",
        primary_domain="devops",
    )


def test_pipeline_classifies_uncached_without_live_llm(monkeypatch) -> None:
    monkeypatch.setattr("core.services.scoring_v3.pipeline_v3.llm_cache.get", lambda *a, **k: None)
    put = Mock()
    monkeypatch.setattr("core.services.scoring_v3.pipeline_v3.llm_cache.put", put)
    subject = ScoringV3Pipeline()
    subject._waterfall_classify = AsyncMock(return_value=_call_result(_core_item()))

    result = asyncio.run(
        subject.run_async([{"id": "1", "title": "Внедрение Kubernetes"}], run_legacy=False)
    )
    assert result.cache_misses == 1
    assert result.primary_batches == 1 and result.judge_batches == 0
    assert result.results[0].queue == "P1"
    assert result.total_tokens == 15
    put.assert_called_once()


def test_low_confidence_runs_judge_and_aggregates(monkeypatch) -> None:
    monkeypatch.setattr("core.services.scoring_v3.pipeline_v3.llm_cache.get", lambda *a, **k: None)
    monkeypatch.setattr("core.services.scoring_v3.pipeline_v3.llm_cache.put", Mock())
    put_judge = Mock()
    monkeypatch.setattr("core.services.scoring_v3.pipeline_v3.llm_cache.put_judge", put_judge)
    subject = ScoringV3Pipeline()
    primary = _core_item(confidence=0.4)
    judge = LLMClassificationItem(
        id="t1", verdict="review", fit_score=60, confidence=0.9,
        procurement_type="services", primary_domain="devops"
    )
    subject._waterfall_classify = AsyncMock(
        side_effect=[_call_result(primary, "primary"), _call_result(judge, "judge")]
    )
    result = asyncio.run(subject.run_async([{"id": "1", "title": "Cloud"}]))
    assert result.judge_batches == 1
    assert result.results[0].classifier_disagreement
    assert result.results[0].queue == "P2"
    put_judge.assert_called_once()


def test_cache_hit_avoids_primary_call(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.services.scoring_v3.pipeline_v3.llm_cache.get", lambda *a, **k: _core_item()
    )
    subject = ScoringV3Pipeline()
    subject._waterfall_classify = AsyncMock()
    result = asyncio.run(subject.run_async([{"id": "1", "title": "Cached Kubernetes"}]))
    assert result.cache_hits == 1
    assert result.primary_batches == 0
    subject._waterfall_classify.assert_not_awaited()


def test_batch_failure_creates_review_fallback(monkeypatch) -> None:
    monkeypatch.setattr("core.services.scoring_v3.pipeline_v3.llm_cache.get", lambda *a, **k: None)
    subject = ScoringV3Pipeline()
    subject._waterfall_classify = AsyncMock(side_effect=RuntimeError("offline"))
    result = asyncio.run(subject.run_async([{"id": "1", "title": "Unknown"}]))
    assert result.errors
    assert result.results[0].final_verdict == "review"
    assert result.results[0].queue == "P2"


def test_judge_candidate_rules_skip_obvious_non_it() -> None:
    subject = ScoringV3Pipeline()
    tenders = [
        {"title": "non-it", "v1_category": ""},
        {"title": "legacy", "v1_category": "core"},
        {"title": "mixed", "v1_category": ""},
        {"title": "risk", "v1_category": ""},
    ]
    items = {
        "non-it": LLMClassificationItem(id="t1", verdict="reject", confidence=0.99, primary_domain="non_it"),
        "legacy": LLMClassificationItem(id="t2", verdict="reject", confidence=0.99, primary_domain="non_it"),
        "mixed": LLMClassificationItem(id="t3", verdict="core", confidence=0.99, procurement_type="mixed"),
        "risk": LLMClassificationItem(id="t4", verdict="core", confidence=0.99, risk_flags=["ambiguous_title"]),
    }
    selected = set(subject._find_judge_candidates(tenders, items))
    assert selected == {"legacy", "mixed", "risk"}


def test_waterfall_without_configured_backend_fails_safely(monkeypatch) -> None:
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    with pytest.raises(RuntimeError, match="All classification backends failed"):
        asyncio.run(ScoringV3Pipeline()._waterfall_classify(["title"]))


def test_classify_titles_builds_stable_raw_ids(monkeypatch) -> None:
    subject = ScoringV3Pipeline()
    fake = PipelineRunResult(results=[])
    run = Mock(return_value=fake)
    monkeypatch.setattr(subject, "run", run)
    assert subject.classify_titles(["one", "two"]) == []
    assert run.call_args.args[0][1]["id"] == "raw_1"
