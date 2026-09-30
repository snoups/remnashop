from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.repository import SubscriptionRepository


class PanelSubscriptionRevoker:
    """SubscriptionRevoker for callers that can't import this module (users
    sits below subscriptions). Builds its own repository so it needs only
    core-provided dependencies."""

    def __init__(self, session: AsyncSession, remnawave_sdk: RemnawaveSDK) -> None:
        self._subscription_repository = SubscriptionRepository(session)
        self._remnawave_sdk = remnawave_sdk

    async def revoke_all_by_user(self, user_id: int) -> None:
        # Panel first, same as DeleteSubscriptionUseCase: a failed call
        # propagates before anything local claims access is gone. The rows
        # stay as history, marked DELETED so reconcile leaves them alone.
        for subscription in await self._subscription_repository.get_live_by_user(user_id):
            try:
                await self._remnawave_sdk.users.delete_user(subscription.remnawave_user_id)
            except RemnawaveNotFoundError:
                pass
            await self._subscription_repository.mark_deleted(subscription.id)
            logger.info(
                f"Revoked panel user '{subscription.remnawave_user_id}' of user '{user_id}'"
            )
