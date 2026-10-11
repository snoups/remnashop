from typing import Any, Optional

import pytest
from pydantic import SecretStr

from app.core.enums import Locale, Role, SmtpSecurity
from app.core.exceptions import RetryableTaskError, ValidationError
from app.modules.email.dto import EmailMessageDto
from app.modules.email.sender import EmailSendError, SmtpSender
from app.modules.email.templates import render_login_code
from app.modules.email.usecases import SendEmailUseCase, SendTestEmailUseCase
from app.modules.settings import EmailSettingsDto

_CONFIGURED = EmailSettingsDto(
    host="smtp.example.com",
    port=465,
    security=SmtpSecurity.TLS,
    username="u",
    password=SecretStr("p"),
    from_address="no-reply@example.com",
    from_name="Shop",
)


class _Repo:
    def __init__(self, settings: EmailSettingsDto) -> None:
        self._settings = settings

    async def get_email_settings(self) -> EmailSettingsDto:
        return self._settings


class _Uow:
    async def __aenter__(self) -> "_Uow":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _Sender:
    def __init__(self, error: Optional[Exception] = None) -> None:
        self.error = error
        self.sent: list[EmailMessageDto] = []

    async def send(self, settings: EmailSettingsDto, message: EmailMessageDto) -> None:
        if self.error:
            raise self.error
        self.sent.append(message)


class _Actor:
    id = 1
    role = Role.ADMIN
    name = "a"
    permission_grants = None
    permission_revokes = None
    login = "a"
    telegram_id = None
    is_privileged = True
    log = "a"

    def __init__(self, email: Optional[str]) -> None:
        self.email = email


def _test_case(settings: EmailSettingsDto, sender: _Sender) -> SendTestEmailUseCase:
    return SendTestEmailUseCase(_Repo(settings), sender, _Uow())  # type: ignore[arg-type]


def test_login_code_template_contains_code() -> None:
    subject, text, html = render_login_code("123456", Locale.RU)
    assert "123456" in text and "123456" in html and subject


def test_login_code_template_falls_back_to_en() -> None:
    subject, _, _ = render_login_code("123456", Locale.DE)
    assert subject == "Your sign-in code: 123456"


async def test_sender_uses_tls_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    async def fake_send(message: Any, **kwargs: Any) -> None:
        calls.update(kwargs)
        calls["to"] = message["To"]

    monkeypatch.setattr("app.modules.email.sender.aiosmtplib.send", fake_send)
    await SmtpSender().send(
        _CONFIGURED, EmailMessageDto(to="a@b.c", subject="s", text="t", html="<p>t</p>")
    )

    assert calls["use_tls"] is True and calls["start_tls"] is False
    assert calls["hostname"] == "smtp.example.com" and calls["to"] == "a@b.c"


async def test_send_email_skips_when_not_configured() -> None:
    sender = _Sender()
    use_case = SendEmailUseCase(_Repo(EmailSettingsDto()), sender, _Uow())  # type: ignore[arg-type]
    await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"))
    assert sender.sent == []


async def test_send_email_failure_is_retryable() -> None:
    use_case = SendEmailUseCase(_Repo(_CONFIGURED), _Sender(EmailSendError("x")), _Uow())  # type: ignore[arg-type]
    with pytest.raises(RetryableTaskError):
        await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"))


async def test_test_email_goes_to_actor_email() -> None:
    sender = _Sender()
    await _test_case(_CONFIGURED, sender)(_Actor("me@x.y"))  # type: ignore[arg-type]
    assert [m.to for m in sender.sent] == ["me@x.y"]


async def test_test_email_falls_back_to_from_address() -> None:
    sender = _Sender()
    await _test_case(_CONFIGURED, sender)(_Actor(None))  # type: ignore[arg-type]
    assert [m.to for m in sender.sent] == ["no-reply@example.com"]


async def test_test_email_not_configured() -> None:
    with pytest.raises(ValidationError):
        await _test_case(EmailSettingsDto(), _Sender())(_Actor(None))  # type: ignore[arg-type]


async def test_test_email_send_failure_hides_smtp_text() -> None:
    with pytest.raises(ValidationError) as info:
        await _test_case(_CONFIGURED, _Sender(EmailSendError("secret smtp text")))(_Actor(None))  # type: ignore[arg-type]
    assert "secret" not in str(info.value)
