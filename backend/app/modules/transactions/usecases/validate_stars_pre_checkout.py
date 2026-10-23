from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, TransactionStatus
from app.core.usecase import UseCase
from app.modules.gateways import REQUIRE_PAID_PURCHASE_FIELD_KEY, GatewayRepository, gateway_flags
from app.modules.transactions.dto import StarsPreCheckoutDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases._stars import find_matching_stars_order
from app.modules.users import UserRepository


class ValidateStarsPreCheckoutUseCase(UseCase[StarsPreCheckoutDto, bool]):
    required_permission = None

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        gateway_repository: GatewayRepository,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._gateway_repository = gateway_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: StarsPreCheckoutDto) -> bool:
        async with self._uow:
            order = await find_matching_stars_order(
                self._transaction_repository,
                self._user_repository,
                telegram_id=data.telegram_id,
                payload=data.payload,
                currency=data.currency,
                total_amount=data.total_amount,
            )
            if order is None or order.status is not TransactionStatus.PENDING:
                return False
            payer = await self._user_repository.find_by_telegram_id(data.telegram_id)
            if payer is None or payer.is_blocked:
                return False
            settings = await self._gateway_repository.get_raw_settings(
                PaymentGatewayType.TELEGRAM_STARS
            )
            if gateway_flags(PaymentGatewayType.TELEGRAM_STARS, settings).get(
                REQUIRE_PAID_PURCHASE_FIELD_KEY, False
            ):
                return await self._transaction_repository.has_paid_purchase(order.user_id)
            return True
