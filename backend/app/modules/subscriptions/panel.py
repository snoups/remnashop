import re
from contextlib import suppress
from datetime import datetime
from typing import Any, Final, Literal, Optional
from uuid import uuid4

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.enums import UserStatus
from remnapy.models import CreateUserRequestDto, UpdateUserRequestDto, UserResponseDto

from app.core.constants import GB_TO_BYTES, INT32_MAX, INT64_MAX, REMNASHOP_PREFIX, WEB_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto

_PANEL_USERNAME: Final[re.Pattern[str]] = re.compile(rf"^{REMNASHOP_PREFIX}(\d+)_[0-9a-f]{{8}}$")
_LEGACY_TELEGRAM_USERNAME: Final[re.Pattern[str]] = re.compile(rf"^{REMNASHOP_PREFIX}(\d+)$")
_LEGACY_WEB_USERNAME: Final[re.Pattern[str]] = re.compile(rf"^{REMNASHOP_PREFIX}{WEB_PREFIX}(\d+)$")
# null clears these in the panel; the SDK sends every field it was given, and
# the panel refuses null in the others with a 400
_PANEL_NULLABLE: Final[frozenset[str]] = frozenset({"tag", "external_squad_uuid"})


def _sent(fields: dict[str, Any]) -> dict[str, Any]:
    """The fields to send: None means "leave as is" except where null clears."""
    return {
        name: value
        for name, value in fields.items()
        if value is not None or name in _PANEL_NULLABLE
    }


def panel_update(**fields: Any) -> UpdateUserRequestDto:
    return UpdateUserRequestDto(**_sent(fields))


def _panel_username(user_id: int) -> str:
    return f"{REMNASHOP_PREFIX}{user_id}_{uuid4().hex[:8]}"


def shop_user_key_from_username(
    username: str,
) -> Optional[tuple[Literal["id", "telegram_id"], int]]:
    """The shop user a panel user was named for: by id in the current format
    and the legacy web one, by Telegram id in the legacy `rs_<telegram_id>`."""
    keys: tuple[tuple[re.Pattern[str], Literal["id", "telegram_id"], int], ...] = (
        (_PANEL_USERNAME, "id", INT32_MAX),
        (_LEGACY_WEB_USERNAME, "id", INT32_MAX),
        (_LEGACY_TELEGRAM_USERNAME, "telegram_id", INT64_MAX),
    )
    for pattern, key, limit in keys:
        if match := pattern.match(username):
            # usernames are panel-side input; a number past the column is no match
            value = int(match.group(1))
            return (key, value) if value <= limit else None
    return None


def new_panel_user(user: UserDto, plan: PlanSnapshot, expire_at: datetime) -> CreateUserRequestDto:
    return CreateUserRequestDto(
        **_sent(
            {
                "username": _panel_username(user.id),
                "telegram_id": user.telegram_id,
                "email": user.email,
                "expire_at": expire_at,
                "traffic_limit_bytes": plan.traffic_limit * GB_TO_BYTES,
                "traffic_limit_strategy": plan.traffic_limit_strategy,
                "hwid_device_limit": plan.device_limit,
                "active_internal_squads": plan.internal_squads or None,
                "external_squad_uuid": plan.external_squad,
                "tag": plan.tag,
            }
        )
    )


def panel_user_from_row(subscription: SubscriptionDto, user: UserDto) -> CreateUserRequestDto:
    """A new panel user for a row whose own one is gone."""
    return CreateUserRequestDto(
        **_sent(
            {
                "username": _panel_username(user.id),
                "telegram_id": user.telegram_id,
                "email": user.email,
                # the panel takes a past date on create, unlike on update
                "expire_at": subscription.expire_at,
                "status": (
                    UserStatus.DISABLED
                    if subscription.status is SubscriptionStatus.DISABLED
                    else None
                ),
                "traffic_limit_bytes": subscription.effective_traffic_limit * GB_TO_BYTES,
                "traffic_limit_strategy": subscription.traffic_limit_strategy,
                "hwid_device_limit": subscription.effective_device_limit,
                "active_internal_squads": subscription.internal_squads or None,
                "external_squad_uuid": subscription.external_squad,
                "tag": subscription.tag,
            }
        )
    )


def configure_for_plan(
    remnawave_user_id: int,
    plan: PlanSnapshot,
    expire_at: datetime,
    *,
    enable: bool = False,
) -> UpdateUserRequestDto:
    return panel_update(
        id=remnawave_user_id,
        # None keeps the panel's status
        status=UserStatus.ACTIVE if enable else None,
        expire_at=expire_at,
        traffic_limit_bytes=plan.traffic_limit * GB_TO_BYTES,
        hwid_device_limit=plan.device_limit,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        active_internal_squads=plan.internal_squads or None,
        external_squad_uuid=plan.external_squad,
        tag=plan.tag,
    )


def restore(subscription: SubscriptionDto, owner: Optional[UserDto] = None) -> UpdateUserRequestDto:
    """Puts a panel user back to the configuration its subscription row holds;
    with `owner`, also to the owner's Telegram and email where the shop knows them."""
    return panel_update(
        id=subscription.remnawave_user_id,
        telegram_id=owner.telegram_id if owner else None,
        email=owner.email if owner else None,
        # the panel refuses a past expireAt on update and expires the user itself
        expire_at=subscription.expire_at if subscription.expire_at > datetime_now() else None,
        traffic_limit_bytes=subscription.effective_traffic_limit * GB_TO_BYTES,
        hwid_device_limit=subscription.effective_device_limit,
        traffic_limit_strategy=subscription.traffic_limit_strategy,
        active_internal_squads=subscription.internal_squads or None,
        external_squad_uuid=subscription.external_squad,
        tag=subscription.tag,
    )


async def revert_panel_to_owner(
    sdk: RemnawaveSDK,
    repository: SubscriptionRepository,
    uow: UnitOfWork,
    current: SubscriptionDto,
) -> None:
    """Best effort: puts the panel user back to the row that owns it in the
    database, `current` or the newer row that took the panel user over."""

    with suppress(Exception):
        owner: Optional[SubscriptionDto] = None
        with suppress(Exception):
            async with uow:
                owner = await repository.find_by_remnawave_user_id(current.remnawave_user_id)
        # unreadable database: current is the best guess left
        owner = owner or current
        if owner.status is SubscriptionStatus.DELETED:
            return
        await sdk.users.update_user(restore(owner))


def subscription_row(
    data: PurchaseSubscriptionDto,
    panel_user: UserResponseDto,
    expire_at: Optional[datetime] = None,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> CreateSubscriptionDto:
    plan = data.plan_snapshot
    return CreateSubscriptionDto(
        user_id=data.user_id,
        remnawave_user_id=panel_user.id,
        status=status,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        is_trial=plan.is_trial,
        internal_squads=plan.internal_squads,
        external_squad=plan.external_squad,
        tag=plan.tag,
        expire_at=expire_at or panel_user.expire_at,
        url=panel_user.subscription_url,
        plan_snapshot=plan,
    )


async def reset_traffic_if_paid(
    sdk: RemnawaveSDK,
    repository: SubscriptionRepository,
    uow: UnitOfWork,
    data: PurchaseSubscriptionDto,
    subscription: SubscriptionDto,
) -> SubscriptionDto:
    if not data.reset_traffic:
        return subscription
    # a failure leaves the old counter running, nothing to revert
    try:
        panel_user = await sdk.users.reset_user_traffic(subscription.remnawave_user_id)
    except Exception:
        logger.exception(f"Failed to reset traffic of subscription '{subscription.id}'")
        return subscription
    return await sync_status_after_reset(repository, uow, subscription, panel_user)


async def sync_status_after_reset(
    repository: SubscriptionRepository,
    uow: UnitOfWork,
    subscription: SubscriptionDto,
    panel_user: UserResponseDto,
) -> SubscriptionDto:
    # the reset lifts LIMITED, but the row holds the panel's state from before
    # it, and the webhook that would sync it may never come
    if subscription.status is not SubscriptionStatus.LIMITED or (
        SubscriptionStatus(panel_user.status) is not SubscriptionStatus.ACTIVE
    ):
        return subscription
    try:
        async with uow:
            return await SubscriptionLifecycleService(repository).sync_status(
                subscription.id, SubscriptionStatus.ACTIVE
            )
    except Exception:
        logger.exception(f"Failed to sync status of subscription '{subscription.id}'")
        return subscription
