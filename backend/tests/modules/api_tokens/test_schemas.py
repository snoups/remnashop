import pydantic
import pytest

from app.modules.api_tokens.api.schemas import CreateApiTokenRequest


def _request(entries: int) -> CreateApiTokenRequest:
    return CreateApiTokenRequest(
        name="t",
        scopes=["*"],
        expires_in_days=30,
        ip_allowlist=[f"10.0.0.{i}" for i in range(entries)],
    )


def test_ip_allowlist_accepts_up_to_64_entries() -> None:
    assert len(_request(64).ip_allowlist) == 64


def test_ip_allowlist_rejects_more_than_64_entries() -> None:
    with pytest.raises(pydantic.ValidationError):
        _request(65)
