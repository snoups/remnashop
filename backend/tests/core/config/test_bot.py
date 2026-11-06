import pytest

from app.core.config.bot import _is_local_host


@pytest.mark.parametrize(
    ("host", "local"),
    [
        ("telegram-bot-api", True),
        ("localhost", True),
        ("127.0.0.1", True),
        ("10.0.0.5", True),
        ("::1", True),
        ("bot-api.example.com", False),
        ("8.8.8.8", False),
    ],
)
def test_plain_http_is_quiet_only_for_a_local_host(host: str, local: bool) -> None:
    assert _is_local_host(host) is local
