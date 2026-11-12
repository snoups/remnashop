from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import DeleteUserAllHwidDeviceRequestDto

from app.core.db.uow import UnitOfWork
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository


async def reissue_link(
    remnawave_sdk: RemnawaveSDK,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    subscription: SubscriptionDto,
) -> SubscriptionDto:
    # Nodes know only the user's shared credentials, never a HWID: rotating them is the only
    # way to cut off a device that already holds a config.
    panel_user = await remnawave_sdk.users.revoke_user_subscription(subscription.remnawave_user_id)
    async with uow:
        updated = await subscription_repository.set_url(
            subscription.id, panel_user.subscription_url
        )

    # the new link already works, so a failure here only leaves stale slots taken
    try:
        await remnawave_sdk.hwid.delete_all_hwid_user(
            DeleteUserAllHwidDeviceRequestDto(user_id=subscription.remnawave_user_id)
        )
    except Exception:
        logger.exception(f"Failed to clear devices of reissued subscription '{subscription.id}'")
    return updated
