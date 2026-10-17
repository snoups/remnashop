import re
from email.message import EmailMessage
from email.utils import formataddr
from typing import Final, Optional

import aiosmtplib

from app.core.enums import SmtpSecurity
from app.modules.email.dto import EmailMessageDto
from app.modules.settings import AppearanceImageDto, SmtpProfileDto

# a dropped established session (SMTPServerDisconnected, also an OSError) says
# nothing about the server being unreachable
_CONNECT_ERRORS: Final[tuple[type[Exception], ...]] = (
    aiosmtplib.SMTPConnectError,
    aiosmtplib.SMTPConnectTimeoutError,
)

_PERMANENT: Final[int] = 500
_ENHANCED_STATUS: Final[re.Pattern[str]] = re.compile(r"^\s*([245])\.(\d{1,3})\.(\d{1,3})")


def mailbox_refused(code: int, message: str) -> bool:
    # only a bad mailbox marks the address; policy/blocklist (5.7.x) or a full box can pass
    if code < _PERMANENT:
        return False
    enhanced = _ENHANCED_STATUS.match(message)
    return enhanced is None or (enhanced.group(1), enhanced.group(2)) == ("5", "1")


class EmailSendError(Exception):
    def __init__(
        self,
        message: str,
        *,
        connection: bool = False,
        auth: bool = False,
        refused: bool = False,
    ) -> None:
        super().__init__(message)
        self.connection = connection
        self.auth = auth
        # the mailbox itself is refused for good: retrying won't help
        self.refused = refused


class SmtpSender:
    async def send(
        self,
        profile: SmtpProfileDto,
        message: EmailMessageDto,
        logo: Optional[AppearanceImageDto] = None,
    ) -> None:
        if profile.host is None or profile.from_address is None:
            raise EmailSendError("SMTP is not configured")
        mime = EmailMessage()
        mime["From"] = formataddr((profile.from_name or "", profile.from_address))
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
                hostname=profile.host,
                port=profile.port,
                username=profile.username,
                password=profile.password.get_secret_value() if profile.password else None,
                use_tls=profile.security is SmtpSecurity.TLS,
                start_tls=profile.security is SmtpSecurity.STARTTLS,
                timeout=15,
            )
        except aiosmtplib.SMTPRecipientsRefused as error:
            refusal = error.recipients[0] if error.recipients else None
            refused = refusal is not None and mailbox_refused(refusal.code, refusal.message)
            raise EmailSendError(str(error), refused=refused) from error
        except (aiosmtplib.SMTPException, OSError) as error:
            connect_phase = isinstance(error, _CONNECT_ERRORS) or not isinstance(
                error, aiosmtplib.SMTPException
            )
            raise EmailSendError(str(error), connection=connect_phase) from error
