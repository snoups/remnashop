from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.core.enums import SmtpSecurity
from app.modules.email.dto import EmailMessageDto
from app.modules.settings import EmailSettingsDto


class EmailSendError(Exception): ...


class SmtpSender:
    async def send(self, settings: EmailSettingsDto, message: EmailMessageDto) -> None:
        if settings.host is None or settings.from_address is None:
            raise EmailSendError("SMTP is not configured")
        mime = EmailMessage()
        mime["From"] = formataddr((settings.from_name or "", settings.from_address))
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
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
            raise EmailSendError(str(error)) from error
