from contextlib import suppress

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository


class PanelSubscriptionRevoker:
    """Also the SubscriptionRevoker port for users, which sits below this module."""

    def __init__(
        self, subscription_repository: SubscriptionRepository, remnawave_sdk: RemnawaveSDK
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk

    async def revoke(self, subscription: SubscriptionDto) -> None:
        # Panel first: a failed call propagates before anything local claims
        # access is gone. The row stays as history, marked DELETED so reconcile
        # leaves it alone.
        with suppress(RemnawaveNotFoundError):  # already removed in the panel itself
            await self._remnawave_sdk.users.delete_user(subscription.remnawave_user_id)
        await self._subscription_repository.mark_deleted(subscription.id)
        logger.info(
            f"Revoked panel user '{subscription.remnawave_user_id}' "
            f"of user '{subscription.user_id}'"
        )

    async def revoke_all_by_user(self, user_id: int) -> None:
        for subscription in await self._subscription_repository.get_live_by_user(user_id):
            await self.revoke(subscription)
