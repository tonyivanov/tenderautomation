from types import SimpleNamespace
from unittest.mock import AsyncMock

from click.testing import CliRunner

from core import cli
from core.models import ReconciliationResult


def test_reconcile_deadlines_outputs_same_safe_counters(monkeypatch) -> None:
    result = ReconciliationResult(
        scanned=3,
        deadline_updated=1,
        url_updated=2,
        unresolved=1,
        remaining_candidates=4,
    )
    service = SimpleNamespace(run=AsyncMock(return_value=result))
    monkeypatch.setattr(cli, "build_reconciliation_service", lambda: service)
    invocation = CliRunner().invoke(
        cli.main, ["reconcile-deadlines", "--batch-size", "3"]
    )
    assert invocation.exit_code == 0
    assert '"scanned": 3' in invocation.output
    assert '"remaining_candidates": 4' in invocation.output
    assert service.run.await_args.args[0].batch_size == 3


def test_reconcile_deadlines_rejects_invalid_batch_before_service(monkeypatch) -> None:
    builder = AsyncMock()
    monkeypatch.setattr(cli, "build_reconciliation_service", builder)
    invocation = CliRunner().invoke(
        cli.main, ["reconcile-deadlines", "--batch-size", "0"]
    )
    assert invocation.exit_code == 2
    builder.assert_not_awaited()


def test_unresolved_rows_do_not_fail_cli(monkeypatch) -> None:
    service = SimpleNamespace(
        run=AsyncMock(return_value=ReconciliationResult(unresolved=2))
    )
    monkeypatch.setattr(cli, "build_reconciliation_service", lambda: service)
    assert CliRunner().invoke(cli.main, ["reconcile-deadlines"]).exit_code == 0
