import httpx
import pytest

import app.modules.oauth.providers.oidc as oidc_module
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.oauth.providers.oidc import OIDCOAuthClient


async def _fake_assert_public_https_host(url: str) -> None:
    return None


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    original_client_cls = oidc_module.httpx.AsyncClient

    def patched_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return original_client_cls(*args, **kwargs, transport=handler)  # type: ignore[arg-type]

    monkeypatch.setattr(oidc_module.httpx, "AsyncClient", patched_client)
    # the SSRF guard resolves real DNS (tested in tests/core/utils/test_http.py);
    # stubbed so the request reaches MockTransport
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


async def test_discover_does_not_follow_a_redirect_off_the_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The SSRF guard only vets the issuer's own host, so a followed redirect
    # would carry this server-side request to an unvetted one.
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "idp.example.com":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta"})
        return httpx.Response(200, json={"authorization_endpoint": "http://169.254.169.254/auth"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    client = OIDCOAuthClient("https://idp.example.com", "client-id", "client-secret")

    with pytest.raises(httpx.HTTPStatusError):
        await client._discover()

    assert requested == ["https://idp.example.com/.well-known/openid-configuration"]


async def test_authorization_url_rejects_a_non_https_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"authorization_endpoint": "javascript:alert(1)//"})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    client = OIDCOAuthClient("https://idp.example.com", "client-id", "client-secret")

    with pytest.raises(ValidationError) as excinfo:
        await client.authorization_url("https://shop.example.com/cb", "state", "verifier")

    assert excinfo.value.code == ErrorCode.URL_NOT_HTTPS
