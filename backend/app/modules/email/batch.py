import email.policy
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from typing import Final, Optional

import aiosmtplib

from app.core.constants import REDIS_KEY_PREFIX, TIME_1M
from app.core.enums import EmailOutcome, SmtpSecurity
from app.modules.email.sender import EmailSendError, mailbox_refused
from app.modules.settings import SmtpProfileDto

SMTP_PAUSE_SECONDS: Final[int] = TIME_1M
_TIMEOUT_S: Final[int] = 15
# the default SMTP policy wraps at 78 and RFC 2047-encodes a long List-Unsubscribe
_WIRE_POLICY: Final[email.policy.Policy] = email.policy.SMTP.clone(max_line_length=998)


def smtp_pause_key(*, bulk: bool) -> str:
    return f"{REDIS_KEY_PREFIX}{'smtp_bulk_unavailable' if bulk else 'smtp_unavailable'}"


@dataclass(frozen=True, kw_only=True)
class InlineImageDto:
    cid: str
    data: bytes
    content_type: str


@dataclass(frozen=True, kw_only=True)
class OutgoingEmailDto:
    to: str
    subject: str
    text: str
    html: str
    images: list[InlineImageDto] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class EmailDeliveryDto:
    outcome: EmailOutcome
    error: Optional[str] = None


def build_mime(profile: SmtpProfileDto, email: OutgoingEmailDto) -> EmailMessage:
    mime = EmailMessage()
    mime["From"] = formataddr((profile.from_name or "", profile.from_address or ""))
    mime["To"] = email.to
    mime["Subject"] = email.subject
    for name, value in email.headers.items():
        mime[name] = value
    mime.set_content(email.text)
    mime.add_alternative(email.html, subtype="html")
    html_part = mime.get_body(("html",))
    if html_part is not None:
        for image in email.images:
            maintype, subtype = image.content_type.split("/", 1)
            html_part.add_related(
                image.data, maintype=maintype, subtype=subtype, cid=f"<{image.cid}>"
            )
    return mime


class SmtpBatch:
    def __init__(self, client: aiosmtplib.SMTP, profile: SmtpProfileDto) -> None:
        self._client = client
        self._profile = profile

    async def send(self, email: OutgoingEmailDto) -> EmailDeliveryDto:
        try:
            await self._client.sendmail(
                self._profile.from_address or "",
                [email.to],
                build_mime(self._profile, email).as_bytes(policy=_WIRE_POLICY),
            )
        except aiosmtplib.SMTPRecipientsRefused as error:
            refusal = error.recipients[0] if error.recipients else None
            if refusal is not None and mailbox_refused(refusal.code, refusal.message):
                return EmailDeliveryDto(outcome=EmailOutcome.REFUSED, error=str(refusal))
            return EmailDeliveryDto(outcome=EmailOutcome.RETRY, error=str(error))
        except aiosmtplib.SMTPServerDisconnected as error:
            raise EmailSendError(str(error), connection=True) from error
        except aiosmtplib.SMTPException as error:
            return EmailDeliveryDto(outcome=EmailOutcome.RETRY, error=str(error))
        return EmailDeliveryDto(outcome=EmailOutcome.SENT)


class SmtpBatchSender:
    @asynccontextmanager
    async def open(self, profile: SmtpProfileDto) -> AsyncIterator[SmtpBatch]:
        if profile.host is None or profile.from_address is None:
            raise EmailSendError("SMTP is not configured")
        client = aiosmtplib.SMTP(
            hostname=profile.host,
            port=profile.port,
            use_tls=profile.security is SmtpSecurity.TLS,
            start_tls=profile.security is SmtpSecurity.STARTTLS,
            timeout=_TIMEOUT_S,
        )
        try:
            await client.connect()
            if profile.username and profile.password:
                await client.login(profile.username, profile.password.get_secret_value())
        except (aiosmtplib.SMTPException, OSError) as error:
            client.close()
            # wrong credentials won't fix themselves: no pause-and-retry loop
            auth = isinstance(error, aiosmtplib.SMTPAuthenticationError)
            raise EmailSendError(str(error), connection=not auth, auth=auth) from error
        try:
            yield SmtpBatch(client, profile)
        finally:
            try:
                await client.quit()
            except (aiosmtplib.SMTPException, OSError):
                pass
