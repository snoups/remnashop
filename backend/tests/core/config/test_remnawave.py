import pytest

from app.core.config.remnawave import RemnawaveConfig


def test_starts_without_token_or_webhook_secret() -> None:
    config = RemnawaveConfig(token=None, webhook_secret=None)
    assert config.token is None
    assert config.webhook_secret is None


def test_rejects_change_me_token() -> None:
    with pytest.raises(ValueError, match="TOKEN must be set"):
        RemnawaveConfig(token="change_me")


def test_rejects_empty_webhook_secret() -> None:
    with pytest.raises(ValueError, match="WEBHOOK_SECRET must be set"):
        RemnawaveConfig(webhook_secret="")


def test_accepts_a_real_token_and_webhook_secret() -> None:
    config = RemnawaveConfig(token="real-token", webhook_secret="real-secret")  # noqa: S106
    assert config.token is not None
    assert config.token.get_secret_value() == "real-token"
