from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.loyalty.dto import UserLoyaltyDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.summary import build_user_loyalty
from app.modules.pricing import PricingRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserRepository, get_visible_target


class GetUserLoyaltyUseCase(UseCase[int, UserLoyaltyDto]):
    required_permission = Permission.USERS_LOYALTY_VIEW

    def __init__(
        self,
        loyalty_repository: LoyaltyRepository,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._loyalty_repository = loyalty_repository
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> UserLoyaltyDto:
        async with self._uow:
            user = await get_visible_target(self._user_repository, actor, data)
            return await build_user_loyalty(
                user,
                self._loyalty_repository,
                self._transaction_repository,
                self._pricing_repository,
            )
