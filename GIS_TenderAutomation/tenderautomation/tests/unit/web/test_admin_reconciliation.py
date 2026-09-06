import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import Request

from core.models import ReconciliationResult
from web.app import create_app, templates
from web.routers import admin_router


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/admin", "headers": []})


def test_reconciliation_route_is_post_only() -> None:
    operations = create_app().openapi()["paths"]["/admin/reconcile-deadlines"]
    assert "post" in operations
    assert "get" not in operations


def test_non_admin_cannot_start_reconciliation(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_router, "require_user", lambda request: SimpleNamespace(role="manager")
    )
    builder = AsyncMock()
    monkeypatch.setattr(admin_router, "build_reconciliation_service", builder)
    response = asyncio.run(admin_router.reconcile_deadlines(_request(), "50"))
    assert response.status_code == 302
    assert response.headers["location"] == "/tenders"
    builder.assert_not_awaited()


def test_invalid_batch_is_rejected_before_service(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_router,
        "require_user",
        lambda request: SimpleNamespace(role="admin", id="admin-1"),
    )
    builder = AsyncMock()
    monkeypatch.setattr(admin_router, "build_reconciliation_service", builder)
    response = asyncio.run(admin_router.reconcile_deadlines(_request(), "201"))
    assert response.status_code == 303
    assert response.headers["location"].endswith("reconcile=invalid")
    builder.assert_not_awaited()


def test_success_uses_prg_and_safe_aggregate_result(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_router,
        "require_user",
        lambda request: SimpleNamespace(role="admin", id="admin-1"),
    )
    result = ReconciliationResult(scanned=2, deadline_updated=1, url_updated=1)
    service = SimpleNamespace(run=AsyncMock(return_value=result))
    monkeypatch.setattr(admin_router, "build_reconciliation_service", lambda: service)
    response = asyncio.run(admin_router.reconcile_deadlines(_request(), "2"))
    assert response.status_code == 303
    assert admin_router._reconciliation_result == result
    command = service.run.await_args.args[0]
    assert command.batch_size == 2
    assert command.requested_by == "admin-1"


def test_admin_template_has_bounded_accessible_form_and_result() -> None:
    html = templates.env.get_template("admin/panel.html").render(
        total_tenders=0,
        collection_running=False,
        collection_log=[],
        run_history=[],
        reconciliation_result=ReconciliationResult(already_running=True),
        reconciliation_error=None,
    )
    assert 'data-testid="deadline-reconcile-form"' in html
    assert 'data-testid="deadline-reconcile-batch-size"' in html
    assert 'min="1" max="200"' in html
    assert 'data-testid="deadline-reconcile-result"' in html
    assert "уже выполняется" in html
