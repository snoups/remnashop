from dataclasses import replace
from email import message_from_bytes
from typing import Any

import aiosmtplib
import pytest
from pydantic import SecretStr

from app.core.enums import SmtpSecurity
from app.modules.email.batch import EmailOutcome, InlineImageDto, OutgoingEmailDto, SmtpBatchSender
from app.modules.email.sender import EmailSendError
from app.modules.settings import SmtpProfileDto

_PROFILE = SmtpProfileDto(
    host="smtp.example.com",
    port=587,
    security=SmtpSecurity.STARTTLS,
    username="u",
    password=None,
    from_address="news@example.com",
    from_name="Shop",
    is_bulk=True,
)


def _email(to: str = "a@example.com") -> OutgoingEmailDto:
    return OutgoingEmailDto(
        to=to,
        subject="S",
        text="t",
        html='<p><img src="cid:img-1"></p>',
        images=[InlineImageDto(cid="img-1", data=b"png", content_type="image/png")],
        headers={"List-Unsubscribe": "<https://c/api/unsubscribe?token=x>"},
    )


class FakeSmtp:
    instances: list["FakeSmtp"] = []
    connect_error: Any = None
    login_error: Any = None
    send_errors: dict[str, Exception] = {}

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.sent: list[Any] = []
        self.quit_called = False
        self.close_called = False
        FakeSmtp.instances.append(self)

    async def connect(self) -> None:
        if FakeSmtp.connect_error:
            raise FakeSmtp.connect_error

    async def login(self, username: str, password: str) -> None:
        if FakeSmtp.login_error:
            raise FakeSmtp.login_error

    async def sendmail(self, sender: str, recipients: list[str], data: bytes) -> Any:
        error = FakeSmtp.send_errors.get(recipients[0])
        if error:
            raise error
        self.sent.append((sender, recipients, data))
        return {}, "OK"

    async def quit(self) -> None:
        self.quit_called = True

    def close(self) -> None:
        self.close_called = True


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.instances, FakeSmtp.send_errors = [], {}
    FakeSmtp.connect_error = FakeSmtp.login_error = None
    monkeypatch.setattr(aiosmtplib, "SMTP", FakeSmtp)


async def test_one_connection_for_many_emails() -> None:
    async with SmtpBatchSender().open(_PROFILE) as batch:
        first = await batch.send(_email("a@example.com"))
        second = await batch.send(_email("b@example.com"))
    assert (first.outcome, second.outcome) == (EmailOutcome.SENT, EmailOutcome.SENT)
    assert len(FakeSmtp.instances) == 1
    assert len(FakeSmtp.instances[0].sent) == 2
    assert FakeSmtp.instances[0].quit_called


async def test_message_has_inline_image_and_headers() -> None:
    async with SmtpBatchSender().open(_PROFILE) as batch:
        await batch.send(_email())
    sender, recipients, data = FakeSmtp.instances[0].sent[0]
    assert (sender, recipients) == ("news@example.com", ["a@example.com"])
    mime = message_from_bytes(data)
    assert mime["List-Unsubscribe"] == "<https://c/api/unsubscribe?token=x>"
    assert mime["From"] == "Shop <news@example.com>"
    related = [p for p in mime.walk() if p.get("Content-ID") == "<img-1>"]
    assert related and related[0].get_content_type() == "image/png"


def _refused(code: int, message: str) -> aiosmtplib.SMTPRecipientsRefused:
    return aiosmtplib.SMTPRecipientsRefused(
        [aiosmtplib.SMTPRecipientRefused(code, message, "a@example.com")]
    )


@pytest.mark.parametrize(
    ("code", "message", "outcome"),
    [
        (550, "5.1.1 no such user", EmailOutcome.REFUSED),
        (550, "no such user", EmailOutcome.REFUSED),
        # policy, auth or blocklist: says nothing about the mailbox
        (554, "5.7.1 Relay access denied", EmailOutcome.RETRY),
        (552, "5.2.2 mailbox full", EmailOutcome.RETRY),
    ],
)
async def test_rcpt_refusal_outcome(code: int, message: str, outcome: EmailOutcome) -> None:
    FakeSmtp.send_errors["a@example.com"] = _refused(code, message)
    async with SmtpBatchSender().open(_PROFILE) as batch:
        result = await batch.send(_email())
    assert result.outcome is outcome


@pytest.mark.parametrize(
    "error",
    [
        aiosmtplib.SMTPRecipientsRefused(
            [aiosmtplib.SMTPRecipientRefused(451, "try later", "a@example.com")]
        ),
        aiosmtplib.SMTPDataError(554, "rejected"),
        aiosmtplib.SMTPSenderRefused(550, "sender", "news@example.com"),
    ],
)
async def test_other_errors_retry(error: Exception) -> None:
    FakeSmtp.send_errors["a@example.com"] = error
    async with SmtpBatchSender().open(_PROFILE) as batch:
        result = await batch.send(_email())
    assert result.outcome is EmailOutcome.RETRY


async def test_connect_failure_is_connection_error() -> None:
    FakeSmtp.connect_error = aiosmtplib.SMTPConnectError("down")
    with pytest.raises(EmailSendError) as caught:
        async with SmtpBatchSender().open(_PROFILE):
            pass
    assert caught.value.connection


async def test_login_failure_is_auth_error() -> None:
    FakeSmtp.login_error = aiosmtplib.SMTPAuthenticationError(535, "5.7.8 bad credentials")
    profile = replace(_PROFILE, password=SecretStr("p"))
    with pytest.raises(EmailSendError) as caught:
        async with SmtpBatchSender().open(profile):
            pass
    assert caught.value.auth
    assert not caught.value.connection


async def test_failure_after_connect_closes_socket() -> None:
    FakeSmtp.login_error = aiosmtplib.SMTPServerDisconnected("gone")
    profile = replace(_PROFILE, password=SecretStr("p"))
    with pytest.raises(EmailSendError):
        async with SmtpBatchSender().open(profile):
            pass
    assert FakeSmtp.instances[0].close_called


async def test_dropped_session_mid_batch_is_connection_error() -> None:
    FakeSmtp.send_errors["a@example.com"] = aiosmtplib.SMTPServerDisconnected("gone")
    with pytest.raises(EmailSendError) as caught:
        async with SmtpBatchSender().open(_PROFILE) as batch:
            await batch.send(_email())
    assert caught.value.connection


async def test_long_list_unsubscribe_is_not_rfc2047_encoded() -> None:
    url = "https://cab.example/api/unsubscribe?token=" + "7." + "A" * 43
    email = OutgoingEmailDto(
        to="a@example.com",
        subject="S",
        text="t",
        html='<img src="cid:img-1">',
        images=[InlineImageDto(cid="img-1", data=b"png", content_type="image/png")],
        headers={"List-Unsubscribe": f"<{url}>"},
    )
    async with SmtpBatchSender().open(_PROFILE) as batch:
        await batch.send(email)
    data = FakeSmtp.instances[0].sent[0][2]
    assert len(url) > 78
    assert f"List-Unsubscribe: <{url}>".encode() in data
    assert b"=?utf-8?" not in data.split(b"\r\n\r\n", 1)[0]
    assert b"Content-ID: <img-1>" in data


async def test_a_message_that_cannot_be_built_does_not_stop_the_batch() -> None:
    profile = replace(_PROFILE, from_name="Shop\nBcc: x@y.z")  # saved before validation existed
    async with SmtpBatchSender().open(profile) as batch:
        broken = await batch.send(_email("a@example.com"))
    assert broken.outcome is EmailOutcome.RETRY

    async with SmtpBatchSender().open(_PROFILE) as batch:
        assert (await batch.send(_email("b@example.com"))).outcome is EmailOutcome.SENT
