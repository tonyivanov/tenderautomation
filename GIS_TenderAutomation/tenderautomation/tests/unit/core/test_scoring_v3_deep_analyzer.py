import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.services.scoring_v3 import deep_analyzer


class _ClientContext:
    def __init__(self, *, get_response=None, post_response=None, **kwargs) -> None:
        self.get_response = get_response
        self.post_response = post_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        if isinstance(self.get_response, Exception):
            raise self.get_response
        return self.get_response

    async def post(self, *args, **kwargs):
        return self.post_response


def _response(*, content=b"", text="", status_code=200, data=None):
    return SimpleNamespace(
        content=content,
        text=text,
        status_code=status_code,
        raise_for_status=lambda: None,
        json=lambda: data,
    )


def test_bidzaar_token_validation(monkeypatch) -> None:
    valid = json.dumps({"access_token": "token", "expires_at": int(time.time()) + 600})
    monkeypatch.setattr(deep_analyzer.Path, "read_text", lambda *a, **k: valid)
    assert deep_analyzer._get_bidzaar_token() == "token"

    expired = json.dumps({"access_token": "token", "expires_at": 1})
    monkeypatch.setattr(deep_analyzer.Path, "read_text", lambda *a, **k: expired)
    with pytest.raises(PermissionError, match="expired"):
        deep_analyzer._get_bidzaar_token()

    monkeypatch.setattr(deep_analyzer.Path, "read_text", lambda *a, **k: "not-json")
    with pytest.raises(PermissionError, match="unavailable"):
        deep_analyzer._get_bidzaar_token()


def test_download_extract_text_and_failure_paths() -> None:
    client = SimpleNamespace(get=AsyncMock(return_value=_response(content=b"hello")))
    assert asyncio.run(deep_analyzer._download_and_extract(client, "url", "file.txt")) == "hello"
    assert asyncio.run(deep_analyzer._download_and_extract(client, "url", "file.exe")) is None

    failing = SimpleNamespace(get=AsyncMock(side_effect=RuntimeError("offline")))
    assert asyncio.run(deep_analyzer._download_and_extract(failing, "url", "file.txt")) is None

    empty = SimpleNamespace(get=AsyncMock(return_value=_response(content=b"")))
    assert asyncio.run(deep_analyzer._download_and_extract(empty, "url", "file.txt")) is None


def test_fetch_bidzaar_files_validates_url_and_schema(monkeypatch) -> None:
    assert asyncio.run(deep_analyzer._fetch_bidzaar_files("https://bidzaar.com/no-id")) == []
    monkeypatch.setattr(deep_analyzer, "_get_bidzaar_token", lambda: "token")
    response = _response(
        data={"generalInformation": {"files": [{"id": "f1", "name": "TZ"}, "bad"]}}
    )
    monkeypatch.setattr(
        deep_analyzer.httpx,
        "AsyncClient",
        lambda **kwargs: _ClientContext(get_response=response),
    )
    url = "https://bidzaar.com/app/process/light/12345678-1234-1234-1234-123456789abc"
    assert asyncio.run(deep_analyzer._fetch_bidzaar_files(url)) == [{"id": "f1", "name": "TZ"}]


def test_scrape_tender_page_removes_navigation_and_truncates(monkeypatch) -> None:
    html = "<nav>menu</nav><main>Useful tender text</main><script>secret()</script>"
    monkeypatch.setattr(
        deep_analyzer.httpx,
        "AsyncClient",
        lambda **kwargs: _ClientContext(get_response=_response(text=html)),
    )
    text = asyncio.run(deep_analyzer.scrape_tender_page("https://example.test/tender"))
    assert text == "Useful tender text"


def test_analyze_tender_uses_mocked_transport_and_detects_tier(monkeypatch) -> None:
    monkeypatch.setattr(deep_analyzer, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        deep_analyzer, "scrape_tender_page", AsyncMock(return_value="Description")
    )
    monkeypatch.setattr(
        deep_analyzer, "_fetch_bidzaar_files", AsyncMock(return_value=[{"id": "f1"}])
    )
    monkeypatch.setattr(
        deep_analyzer, "_download_bidzaar_files", AsyncMock(return_value="File text")
    )
    llm_response = _response(
        data={"choices": [{"message": {"content": "⭐ Подходит"}}]}
    )
    monkeypatch.setattr(
        deep_analyzer.httpx,
        "AsyncClient",
        lambda **kwargs: _ClientContext(post_response=llm_response),
    )
    result = asyncio.run(
        deep_analyzer.analyze_tender(
            "Kubernetes", "https://bidzaar.com/tender", buyer="Buyer"
        )
    )
    assert result.tier == "⭐"
    assert result.rationale == "⭐ Подходит"


def test_analyze_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(deep_analyzer, "DEEPSEEK_API_KEY", "")
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        asyncio.run(deep_analyzer.analyze_tender("title", "https://example.test"))
