import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.services.collection import CollectionSummary
from core.services.pipeline import PipelineOrchestrator
from core.services.qualification import QualificationResult
from web.app import create_app, templates
from web.routers.admin_router import _short_commit_id
from web.routers.v3_router import _match_tender


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1234567890abcdef", "12345678"),
        (" ABCDEF1234567890 ", "abcdef12"),
        ("1234567", "unknown"),
        ("not-a-commit", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_short_commit_id_is_bounded_and_validated(
    value: str | None, expected: str
) -> None:
    assert _short_commit_id(value) == expected


def test_commit_id_is_rendered_only_with_admin_context() -> None:
    template = templates.env.get_template("base.html")
    current_user = SimpleNamespace(username="admin")

    admin_html = template.render(current_user=current_user, commit_id="12345678")
    ordinary_html = template.render(current_user=current_user)

    assert 'data-testid="admin-commit-id"' in admin_html
    assert "commit 12345678" in admin_html
    assert 'data-testid="admin-commit-id"' not in ordinary_html


def test_pipeline_has_sync_and_async_entry_points() -> None:
    collection = Mock(run_all=AsyncMock(return_value=CollectionSummary()))
    qualification = Mock(qualify_pending=Mock(return_value=QualificationResult(0, 0, 0, 0)))
    subject = PipelineOrchestrator(collection, qualification, Mock())
    assert asyncio.run(subject.run_async()).collection.total_new == 0
    assert subject.run().collection.total_new == 0


def test_action_route_is_post_only() -> None:
    operations = create_app().openapi()["paths"]["/tenders/{tender_id}/action"]
    assert "post" in operations
    assert "get" not in operations


def test_cache_join_uses_tender_id_not_colliding_prefix() -> None:
    prefix = "x" * 60
    one = SimpleNamespace(id="one", title=prefix + "1")
    two = SimpleNamespace(id="two", title=prefix + "2")
    assert _match_tender({"tender_id": "two", "normalized_title": prefix}, {"one": one, "two": two}, {}) is two


def test_ci_secret_scan_is_limited_to_new_commit_history() -> None:
    pipeline = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

    assert "CI_MERGE_REQUEST_DIFF_BASE_SHA" in pipeline
    assert 'git merge-base "$CI_COMMIT_SHA" FETCH_HEAD' in pipeline
    assert '--log-opts="$gitleaks_log_opts"' in pipeline


def test_production_image_embeds_source_commit_sha() -> None:
    pipeline = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert '--build-arg APP_COMMIT_SHA="$CI_COMMIT_SHA"' in pipeline
    assert "ARG APP_COMMIT_SHA=unknown" in dockerfile
    assert "ENV APP_COMMIT_SHA=${APP_COMMIT_SHA}" in dockerfile


def test_project_enforces_sixty_percent_source_coverage() -> None:
    pipeline = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "--cov=src" in pipeline
    assert "--cov-fail-under=60" in pipeline
    assert "[tool.coverage.report]" in project
    assert "fail_under = 60" in project
    assert "--cov-fail-under=60" in readme
