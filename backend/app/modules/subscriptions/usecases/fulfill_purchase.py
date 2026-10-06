from dataclasses import replace

from app.core.actor import Actor
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UserRepository


class FulfillPurchaseUseCase(UseCase[PurchaseSubscriptionDto, SubscriptionDto]):
    """Provisions a paid order on behalf of its buyer."""

    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    ) -> None:
        self._user_repository = user_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case

    async def _execute(self, actor: Actor, data: PurchaseSubscriptionDto) -> SubscriptionDto:
        buyer = await self._user_repository.get_by_id(data.user_id)
        if buyer is None:
            raise NotFoundError(f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND)
        # the cap and the disabled target were checked at checkout; refusing after the charge would
        # leave the customer paid with nothing
        return await self._purchase_subscription_use_case(
            buyer, replace(data, enforce_subscription_cap=False, refuse_disabled_target=False)
        )
