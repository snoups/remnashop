from dishka.integrations.taskiq import FromDishka, inject

from app.core.broker import broker
from app.modules.email.dto import EmailMessageDto
from app.modules.email.usecases import SendEmailUseCase


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def send_email_task(
    to: str, subject: str, text: str, html: str, use_case: FromDishka[SendEmailUseCase]
) -> None:
    await use_case.system(EmailMessageDto(to=to, subject=subject, text=text, html=html))
