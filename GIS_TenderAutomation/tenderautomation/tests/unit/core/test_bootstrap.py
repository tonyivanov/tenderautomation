from unittest.mock import patch

from core.bootstrap import (
    build_adapter_registry,
    build_export_readiness_service,
    build_reconciliation_service,
)


def test_registry_contains_each_platform_once() -> None:
    assert build_adapter_registry().platform_ids() == ["b2bcenter", "bidzaar"]


def test_reconciliation_construction_does_not_authenticate() -> None:
    with patch("adapters.b2bcenter.adapter.B2BCenterAdapter.authenticate") as b2b_auth, patch(
        "adapters.bidzaar.adapter.BidzaarAdapter.authenticate"
    ) as bidzaar_auth:
        service = build_reconciliation_service()
    assert service is not None
    b2b_auth.assert_not_called()
    bidzaar_auth.assert_not_called()


def test_export_readiness_construction_has_no_io_or_authentication() -> None:
    with patch("adapters.b2bcenter.adapter.B2BCenterAdapter.authenticate") as b2b_auth, patch(
        "adapters.bidzaar.adapter.BidzaarAdapter.authenticate"
    ) as bidzaar_auth, patch("sqlite3.connect") as sqlite_connect:
        service = build_export_readiness_service()
    assert service is not None
    b2b_auth.assert_not_called()
    bidzaar_auth.assert_not_called()
    sqlite_connect.assert_not_called()
