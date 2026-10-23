from typing import Any, Optional

import aiosmtplib
import pytest
from pydantic import SecretStr
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.core.enums import Locale, Role, SmtpSecurity
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, RetryableTaskError, ValidationError
from app.modules.email import EmailBrandDto
from app.modules.email.dto import EmailMessageDto, SendTestEmailDto
from app.modules.email.sender import EmailSendError, SmtpSender
from app.modules.email.templates import render_link_code, render_login_code
from app.modules.email.usecases import SendEmailUseCase, SendTestEmailUseCase
from app.modules.settings import AppearanceImageDto, EmailSettingsDto, SmtpProfileDto
from app.modules.users import UserDto

_CONFIGURED = EmailSettingsDto(
    host="smtp.example.com",
    port=465,
    security=SmtpSecurity.TLS,
    username="u",
    password=SecretStr("p"),
    from_address="no-reply@example.com",
    from_name="Shop",
)


_BRAND = EmailBrandDto(brand="Shop", color=None, has_logo=False)


class _Repo:
    def __init__(self, settings: EmailSettingsDto) -> None:
        self._settings = settings

    async def get_email_settings(self) -> EmailSettingsDto:
        return self._settings


class _Users:
    def __init__(self, user: Optional[UserDto] = None) -> None:
        self.user = user
        self.undeliverable: list[int] = []

    async def get_by_email(self, email: str) -> Optional[UserDto]:
        return self.user

    async def set_email_undeliverable(self, user_id: int, at: object) -> None:
        self.undeliverable.append(user_id)


class _Uow:
    async def __aenter__(self) -> "_Uow":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _Sender:
    def __init__(self, error: Optional[Exception] = None) -> None:
        self.error = error
        self.sent: list[EmailMessageDto] = []
        self.profiles: list[SmtpProfileDto] = []
        self.calls = 0

    async def send(
        self,
        settings: SmtpProfileDto,
        message: EmailMessageDto,
        logo: Optional[tuple[bytes, str]] = None,
    ) -> None:
        self.calls += 1
        self.profiles.append(settings)
        if self.error:
            raise self.error
        self.sent.append(message)


class _Logo:
    def __init__(self, found: bool = False) -> None:
        self.found = found
        self.calls = 0

    async def execute(self, kind: object) -> tuple[bytes, str]:
        self.calls += 1
        if not self.found:
            raise NotFoundError("no logo", code=ErrorCode.APPEARANCE_IMAGE_NOT_SET)
        return b"\x89PNG", "image/png"


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
    subject, text, html = render_login_code("123456", Locale.RU, _BRAND, None)
    assert "123456" in text and "123456" in html and subject


def test_login_code_template_falls_back_to_en() -> None:
    subject, _, _ = render_login_code("123456", Locale.DE, _BRAND, None)
    assert subject == "Your sign-in code: 123456"


def test_link_code_template() -> None:
    subject, text, html = render_link_code("123456", Locale.RU, _BRAND, None)
    assert subject == "Код для привязки почты: 123456"
    assert "123456" in text and "123456" in html
    assert render_link_code("123456", Locale.DE, _BRAND, None)[0] == "Your linking code: 123456"


async def test_sender_uses_tls_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    async def fake_send(message: Any, **kwargs: Any) -> None:
        calls.update(kwargs)
        calls["to"] = message["To"]

    monkeypatch.setattr("app.modules.email.sender.aiosmtplib.send", fake_send)
    await SmtpSender().send(
        _CONFIGURED.profile(bulk=False),
        EmailMessageDto(to="a@b.c", subject="s", text="t", html="<p>t</p>"),
    )

    assert calls["use_tls"] is True and calls["start_tls"] is False
    assert calls["hostname"] == "smtp.example.com" and calls["to"] == "a@b.c"


async def test_sender_envelope_is_the_validated_address(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    async def fake_send(message: Any, **kwargs: Any) -> None:
        calls.update(kwargs)

    monkeypatch.setattr("app.modules.email.sender.aiosmtplib.send", fake_send)
    await SmtpSender().send(
        _CONFIGURED.profile(bulk=False),
        EmailMessageDto(to="=?utf-8?q?bad?=@gmail.com", subject="s", text="t", html="<p>t</p>"),
    )

    # without explicit recipients aiosmtplib decodes the To header into bad@gmail.com
    assert calls["recipients"] == ["=?utf-8?q?bad?=@gmail.com"]
    assert calls["sender"] == "no-reply@example.com"


async def test_send_email_skips_when_not_configured(redis: Redis) -> None:
    sender = _Sender()
    use_case = SendEmailUseCase(_Repo(EmailSettingsDto()), sender, redis, _Logo(), _Users(), _Uow())  # type: ignore[arg-type]
    await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"))
    assert sender.sent == []


async def test_send_email_failure_is_retryable(redis: Redis) -> None:
    use_case = SendEmailUseCase(
        _Repo(_CONFIGURED), _Sender(EmailSendError("x")), redis, _Logo(), _Users(), _Uow()
    )  # type: ignore[arg-type]
    with pytest.raises(RetryableTaskError):
        await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"))


async def test_test_email_goes_to_actor_email() -> None:
    sender = _Sender()
    await _test_case(_CONFIGURED, sender)(_Actor("me@x.y"), SendTestEmailDto(bulk=False))  # type: ignore[arg-type]
    assert [m.to for m in sender.sent] == ["me@x.y"]


async def test_test_email_falls_back_to_from_address() -> None:
    sender = _Sender()
    await _test_case(_CONFIGURED, sender)(_Actor(None), SendTestEmailDto(bulk=False))  # type: ignore[arg-type]
    assert [m.to for m in sender.sent] == ["no-reply@example.com"]


async def test_test_email_not_configured() -> None:
    with pytest.raises(ValidationError):
        await _test_case(EmailSettingsDto(), _Sender())(_Actor(None), SendTestEmailDto(bulk=False))  # type: ignore[arg-type]


async def test_test_email_send_failure_hides_smtp_text() -> None:
    with pytest.raises(ValidationError) as info:
        await _test_case(_CONFIGURED, _Sender(EmailSendError("secret smtp text")))(
            _Actor(None), SendTestEmailDto(bulk=False)
        )  # type: ignore[arg-type]
    assert "secret" not in str(info.value)


async def test_sender_attaches_inline_logo(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}

    async def fake_send(message: Any, **_kwargs: Any) -> None:
        sent["message"] = message

    monkeypatch.setattr("app.modules.email.sender.aiosmtplib.send", fake_send)
    settings = EmailSettingsDto(host="h", port=25, security=SmtpSecurity.NONE, from_address="a@b.c")
    await SmtpSender().send(
        settings.profile(bulk=False),
        EmailMessageDto(to="x@y.z", subject="s", text="t", html='<img src="cid:logo">'),
        logo=AppearanceImageDto(data=b"\x89PNG", content_type="image/png"),
    )
    parts = [p for p in sent["message"].walk() if p.get("Content-ID")]
    assert parts and parts[0]["Content-ID"] == "<logo>"


async def test_connection_failure_pauses_smtp(redis: Redis) -> None:
    sender = _Sender(EmailSendError("down", connection=True))
    use_case = SendEmailUseCase(_Repo(_CONFIGURED), sender, redis, _Logo(), _Users(), _Uow())  # type: ignore[arg-type]
    message = EmailMessageDto(to="a@b.c", subject="s", text="t", html="h")
    with pytest.raises(RetryableTaskError):
        await use_case.system(message)
    assert await redis.get(f"{REDIS_KEY_PREFIX}smtp_unavailable") is not None
    with pytest.raises(RetryableTaskError, match="SMTP unavailable"):
        await use_case.system(message)
    assert sender.calls == 1


async def test_other_send_failure_does_not_pause_smtp(redis: Redis) -> None:
    use_case = SendEmailUseCase(
        _Repo(_CONFIGURED), _Sender(EmailSendError("x")), redis, _Logo(), _Users(), _Uow()
    )  # type: ignore[arg-type]
    with pytest.raises(RetryableTaskError):
        await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"))
    assert await redis.get(f"{REDIS_KEY_PREFIX}smtp_unavailable") is None


async def test_logo_is_read_only_when_html_references_it(redis: Redis) -> None:
    logo = _Logo(found=True)
    sender = _Sender()
    use_case = SendEmailUseCase(_Repo(_CONFIGURED), sender, redis, logo, _Users(), _Uow())  # type: ignore[arg-type]
    await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"))
    assert logo.calls == 0
    await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="cid:logo"))
    assert logo.calls == 1 and len(sender.sent) == 2


async def test_missing_logo_still_sends(redis: Redis) -> None:
    sender = _Sender()
    use_case = SendEmailUseCase(_Repo(_CONFIGURED), sender, redis, _Logo(), _Users(), _Uow())  # type: ignore[arg-type]
    await use_case.system(EmailMessageDto(to="a@b.c", subject="s", text="t", html="cid:logo"))
    assert len(sender.sent) == 1


@pytest.mark.parametrize(
    ("error", "connection"),
    [
        (aiosmtplib.SMTPConnectError("refused"), True),
        (aiosmtplib.SMTPConnectTimeoutError("timeout"), True),
        (OSError("unreachable"), True),
        (aiosmtplib.SMTPServerDisconnected("dropped"), False),
        (aiosmtplib.SMTPRecipientRefused(550, "no", "a@b.c"), False),
        (aiosmtplib.SMTPAuthenticationError(535, "bad credentials"), False),
    ],
)
async def test_only_connect_phase_failures_count_as_connection(
    monkeypatch: pytest.MonkeyPatch, error: Exception, connection: bool
) -> None:
    async def fail(*args: Any, **kwargs: Any) -> None:
        raise error

    monkeypatch.setattr(aiosmtplib, "send", fail)
    with pytest.raises(EmailSendError) as raised:
        await SmtpSender().send(
            _CONFIGURED.profile(bulk=False),
            EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"),
        )
    assert raised.value.connection is connection


async def test_test_email_uses_bulk_profile() -> None:
    settings = _CONFIGURED.model_copy(
        update={"bulk_host": "smtp.bulk", "bulk_from_address": "news@example.com"}
    )
    sender = _Sender()
    await _test_case(settings, sender)(_Actor("me@x.y"), SendTestEmailDto(bulk=True))  # type: ignore[arg-type]
    assert [(p.host, p.is_bulk) for p in sender.profiles] == [("smtp.bulk", True)]


async def test_bulk_test_email_without_bulk_profile_is_not_configured() -> None:
    sender = _Sender()
    with pytest.raises(ValidationError) as info:
        await _test_case(_CONFIGURED, sender)(_Actor("me@x.y"), SendTestEmailDto(bulk=True))  # type: ignore[arg-type]
    assert info.value.code == ErrorCode.EMAIL_NOT_CONFIGURED
    assert sender.sent == []


async def test_a_mailbox_refused_for_good_is_marked_and_not_retried(redis: Redis) -> None:
    users = _Users(UserDto(id=7, name="a", email="gone@example.com", language=Locale.EN))
    use_case = SendEmailUseCase(
        _Repo(_CONFIGURED),
        _Sender(EmailSendError("550 5.1.1 no such user", refused=True)),
        redis,
        _Logo(),
        users,
        _Uow(),
    )  # type: ignore[arg-type]

    await use_case.system(EmailMessageDto(to="Gone@example.com", subject="s", text="t", html="h"))

    assert users.undeliverable == [7]


@pytest.mark.parametrize(
    ("code", "message", "refused"),
    [
        (550, "5.1.1 User unknown", True),
        (550, "5.7.1 Blocked by policy", False),
        (450, "4.2.2", False),
    ],
)
async def test_sender_tells_a_refused_mailbox_from_other_refusals(
    monkeypatch: pytest.MonkeyPatch, code: int, message: str, refused: bool
) -> None:
    async def refuse(*args: Any, **kwargs: Any) -> None:
        raise aiosmtplib.SMTPRecipientsRefused(
            [aiosmtplib.SMTPRecipientRefused(code, message, "a@b.c")]
        )

    monkeypatch.setattr(aiosmtplib, "send", refuse)
    with pytest.raises(EmailSendError) as raised:
        await SmtpSender().send(
            _CONFIGURED.profile(bulk=False),
            EmailMessageDto(to="a@b.c", subject="s", text="t", html="h"),
        )
    assert raised.value.refused is refused
