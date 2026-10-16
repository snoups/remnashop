from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways import REQUIRE_PAID_PURCHASE_FIELD_KEY, GatewayRepository, gateway_flags
from app.modules.transactions.dto import PaymentMethodDto
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY, gateway_currency
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserDto


class ListPaymentMethodsUseCase(UseCase[None, list[PaymentMethodDto], UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        gateway_repository: GatewayRepository,
        transaction_repository: TransactionRepository,
        uow: UnitOfWork,
    ) -> None:
        self._gateway_repository = gateway_repository
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[PaymentMethodDto]:
        methods: list[PaymentMethodDto] = []
        async with self._uow:
            for gateway in await self._gateway_repository.get_all():
                if not gateway.is_active or not gateway.is_configured:
                    continue
                gateway_class = GATEWAY_REGISTRY.get(gateway.type)
                if gateway_class is None:
                    continue
                settings = await self._gateway_repository.get_raw_settings(gateway.type)
                if actor.email is None and gateway_class.requires_customer_email(settings):
                    continue
                if gateway_flags(gateway.type, settings).get(
                    REQUIRE_PAID_PURCHASE_FIELD_KEY, False
                ) and not await self._transaction_repository.has_paid_purchase(actor.id):
                    continue
                methods.append(
                    PaymentMethodDto(
                        gateway_type=gateway.type,
                        currency=gateway_currency(gateway.type, settings),
                    )
                )
        return methods
