from app.core.enums import EmailOutcome
from app.modules.email.batch import (
    SMTP_PAUSE_SECONDS,
    EmailDeliveryDto,
    InlineImageDto,
    OutgoingEmailDto,
    SmtpBatch,
    SmtpBatchSender,
    smtp_pause_key,
)
from app.modules.email.di import get_email_providers
from app.modules.email.dispatch import SendEmailDispatch
from app.modules.email.dto import EmailBrandDto, EmailMessageDto
from app.modules.email.layout import brand_accent, load_email_brand, render_email, render_email_html
from app.modules.email.sender import EmailSendError
from app.modules.email.templates import render_login_code

__all__ = [
    "SMTP_PAUSE_SECONDS",
    "EmailBrandDto",
    "EmailDeliveryDto",
    "EmailMessageDto",
    "EmailOutcome",
    "EmailSendError",
    "InlineImageDto",
    "OutgoingEmailDto",
    "SendEmailDispatch",
    "SmtpBatch",
    "SmtpBatchSender",
    "brand_accent",
    "get_email_providers",
    "load_email_brand",
    "render_email",
    "render_email_html",
    "render_login_code",
    "smtp_pause_key",
]
