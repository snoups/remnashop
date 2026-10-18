from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionPanelDiffDto
from app.modules.subscriptions.eligibility import get_manageable_subscription
from app.modules.subscriptions.panel_sync import panel_diff
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class GetSubscriptionPanelDiffUseCase(UseCase[int, SubscriptionPanelDiffDto]):
    required_permission = Permission.SUBSCRIPTIONS_PANEL_DIFF_VIEW

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> SubscriptionPanelDiffDto:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data
            )
        try:
            user = await self._remnawave_sdk.users.get_user_by_id(subscription.remnawave_user_id)
        except RemnawaveNotFoundError:
            return SubscriptionPanelDiffDto(
                subscription_id=subscription.id, missing_in_panel=True, fields=[]
            )
        return SubscriptionPanelDiffDto(
            subscription_id=subscription.id,
            missing_in_panel=False,
            fields=panel_diff(subscription, user),
        )
