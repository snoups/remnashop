from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentOutcome, PurchaseChannel
from app.core.ports import BotSignals
from app.core.usecase import UseCase
from app.modules.customer_notifications.dto import ShowPaymentCanceledDto
from app.modules.transactions import TransactionRepository
from app.modules.users import UserRepository


class ShowPaymentCanceledUseCase(UseCase[ShowPaymentCanceledDto, None]):
    required_permission = None

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        bot_signals: BotSignals,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._bot_signals = bot_signals
        self._uow = uow

    async def _execute(self, actor: Actor, data: ShowPaymentCanceledDto) -> None:
        async with self._uow:
            order = await self._transaction_repository.get_by_id(data.order_id)
            if order.channel is not PurchaseChannel.BOT:
                return
            # the customer already moved on to another bot checkout
            if await self._transaction_repository.has_newer_order(
                order.user_id, PurchaseChannel.BOT, order.id
            ):
                return
            user = await self._user_repository.find_by_id(order.user_id)
        if (
            user is None
            or user.telegram_id is None
            or user.is_blocked
            or user.is_bot_blocked
            or user.deleted_at is not None
        ):
            return
        await self._bot_signals.payment_outcome(user.telegram_id, order.id, PaymentOutcome.CANCELED)
