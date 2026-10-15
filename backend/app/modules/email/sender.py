from email.message import EmailMessage
from email.utils import formataddr
from typing import Final, Optional

import aiosmtplib

from app.core.enums import SmtpSecurity
from app.modules.email.dto import EmailMessageDto
from app.modules.settings import AppearanceImageDto, EmailSettingsDto

# a dropped established session (SMTPServerDisconnected, also an OSError) says
# nothing about the server being unreachable
_CONNECT_ERRORS: Final[tuple[type[Exception], ...]] = (
    aiosmtplib.SMTPConnectError,
    aiosmtplib.SMTPConnectTimeoutError,
)


class EmailSendError(Exception):
    def __init__(self, message: str, *, connection: bool = False) -> None:
        super().__init__(message)
        self.connection = connection


class SmtpSender:
    async def send(
        self,
        settings: EmailSettingsDto,
        message: EmailMessageDto,
        logo: Optional[AppearanceImageDto] = None,
    ) -> None:
        if settings.host is None or settings.from_address is None:
            raise EmailSendError("SMTP is not configured")
        mime = EmailMessage()
        mime["From"] = formataddr((settings.from_name or "", settings.from_address))
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        if logo is not None and "cid:logo" in message.html:
            maintype, subtype = logo.content_type.split("/", 1)
            html_part = mime.get_body(("html",))
            if html_part is not None:
                html_part.add_related(logo.data, maintype=maintype, subtype=subtype, cid="<logo>")
        try:
            await aiosmtplib.send(
                mime,
                hostname=settings.host,
                port=settings.port,
                username=settings.username,
                password=settings.password.get_secret_value() if settings.password else None,
                use_tls=settings.security is SmtpSecurity.TLS,
                start_tls=settings.security is SmtpSecurity.STARTTLS,
                timeout=15,
            )
        except (aiosmtplib.SMTPException, OSError) as error:
            connect_phase = isinstance(error, _CONNECT_ERRORS) or not isinstance(
                error, aiosmtplib.SMTPException
            )
            raise EmailSendError(str(error), connection=connect_phase) from error
