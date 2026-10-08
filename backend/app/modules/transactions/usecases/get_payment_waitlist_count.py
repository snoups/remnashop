from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.dto import PaymentWaitlistCountDto
from app.modules.transactions.waitlist_repository import WaitlistRepository


class GetPaymentWaitlistCountUseCase(UseCase[None, PaymentWaitlistCountDto]):
    required_permission = Permission.PAYMENT_WAITLIST_VIEW

    def __init__(self, waitlist_repository: WaitlistRepository, uow: UnitOfWork) -> None:
        self._waitlist_repository = waitlist_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> PaymentWaitlistCountDto:
        async with self._uow:
            return PaymentWaitlistCountDto(total=await self._waitlist_repository.count())
