import json
import time

import pytest

from core.services.scoring_v3 import deep_analyzer


def test_private_bidzaar_token_is_read_from_manual_session_cache(
    tmp_path, monkeypatch
) -> None:
    token_path = tmp_path / "data" / "bidzaar_token.json"
    token_path.parent.mkdir()
    token_path.write_text(
        json.dumps({"access_token": "test-token", "expires_at": int(time.time()) + 3600}),
        encoding="utf-8",
    )
    monkeypatch.setattr(deep_analyzer, "__file__", str(tmp_path / "src/a/b/c/d.py"))

    assert deep_analyzer._get_bidzaar_token() == "test-token"


def test_private_bidzaar_token_rejects_expired_cache(tmp_path, monkeypatch) -> None:
    token_path = tmp_path / "data" / "bidzaar_token.json"
    token_path.parent.mkdir()
    token_path.write_text(
        json.dumps({"access_token": "expired", "expires_at": int(time.time()) - 1}),
        encoding="utf-8",
    )
    monkeypatch.setattr(deep_analyzer, "__file__", str(tmp_path / "src/a/b/c/d.py"))

    with pytest.raises(PermissionError, match="expired"):
        deep_analyzer._get_bidzaar_token()
