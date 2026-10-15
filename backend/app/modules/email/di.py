from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.email.dispatch import SendEmailDispatch
from app.modules.email.sender import SmtpSender
from app.modules.email.tasks import send_email_task
from app.modules.email.usecases import SendEmailUseCase, SendTestEmailUseCase


class EmailProvider(Provider):
    scope = Scope.REQUEST

    sender = provide(SmtpSender, scope=Scope.APP)
    use_cases = provide_all(SendEmailUseCase, SendTestEmailUseCase)

    @provide(scope=Scope.APP)
    def send_email_dispatch(self) -> SendEmailDispatch:
        return cast(SendEmailDispatch, send_email_task)


def get_email_providers() -> list[Provider]:
    return [EmailProvider()]
