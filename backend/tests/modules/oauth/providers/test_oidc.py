import httpx
import pytest

import app.modules.oauth.providers.oidc as oidc_module
from app.modules.oauth.providers.oidc import OIDCOAuthClient


async def _fake_assert_public_https_host(url: str) -> None:
    return None


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    original_client_cls = oidc_module.httpx.AsyncClient

    def patched_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return original_client_cls(*args, **kwargs, transport=handler)  # type: ignore[arg-type]

    monkeypatch.setattr(oidc_module.httpx, "AsyncClient", patched_client)
    # SSRF guard resolves real DNS -- covered by its own tests
    # (tests/core/utils/test_http.py); stubbed here so MockTransport can
    # actually intercept the request instead of it failing before dispatch.
    monkeypatch.setattr(oidc_module, "assert_public_https_host", _fake_assert_public_https_host)


async def test_discover_returns_metadata_on_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"authorization_endpoint": "https://idp.example.com/auth"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    client = OIDCOAuthClient("https://idp.example.com", "client-id", "client-secret")

    metadata = await client._discover()

    assert metadata["authorization_endpoint"] == "https://idp.example.com/auth"


async def test_discover_raises_key_error_on_non_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    client = OIDCOAuthClient("https://idp.example.com", "client-id", "client-secret")

    with pytest.raises(KeyError):
        await client._discover()


async def test_discover_raises_key_error_on_non_dict_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "a", "dict"])

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    client = OIDCOAuthClient("https://idp.example.com", "client-id", "client-secret")

    with pytest.raises(KeyError):
        await client._discover()
