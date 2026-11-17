import httpx
import pytest

from app import learning_catalog


def test_catalog_disabled_and_missing_configuration(monkeypatch):
    monkeypatch.delenv("LEARNING_RESOURCES_CATALOG", raising=False)
    assert learning_catalog.published_resources() is None
    monkeypatch.setenv("LEARNING_RESOURCES_CATALOG", "1")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="requires"):
        learning_catalog.published_resources()


def test_catalog_pagination_and_validation(monkeypatch):
    monkeypatch.setenv("LEARNING_RESOURCES_CATALOG", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.com")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    calls = []
    entry = {"title": "Learn Python", "provider": "Example", "url": "https://example.com/course",
             "keywords": [" Python "]}

    def handle(request):
        calls.append(request)
        assert request.url.params["published"] == "eq.true"
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json=[entry] * (500 if offset == 0 else 1))

    original_client = httpx.Client
    monkeypatch.setattr(learning_catalog.httpx, "Client",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    result = learning_catalog.published_resources()
    assert len(result) == 501
    assert result[0][0] == ("python",)
    assert len(calls) == 2

    entry["url"] = "javascript:alert(1)"
    with pytest.raises(ValueError, match="Invalid"):
        learning_catalog.published_resources()


def test_catalog_network_error_is_not_silently_ignored(monkeypatch):
    monkeypatch.setenv("LEARNING_RESOURCES_CATALOG", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.com")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    original_client = httpx.Client
    def handle(request):
        return httpx.Response(503)
    monkeypatch.setattr(learning_catalog.httpx, "Client",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(httpx.HTTPStatusError):
        learning_catalog.published_resources()
