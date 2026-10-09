from datetime import datetime
from typing import Final, Optional
from uuid import uuid4

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import CreateUserRequestDto, UpdateUserRequestDto, UserResponseDto

from app.core.constants import GB_TO_BYTES
from app.core.enums import SubscriptionStatus
from app.core.exceptions import ValidationError
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)

_PANEL_USERNAME_PREFIX: Final[str] = "rs_"


class SupersededError(ValidationError):
    """A concurrent purchase committed first and now owns the panel identity
    this one reconfigured; reverting it would overwrite the winner's config."""


def new_panel_user(user_id: int, plan: PlanSnapshot, expire_at: datetime) -> CreateUserRequestDto:
    return CreateUserRequestDto(
        username=f"{_PANEL_USERNAME_PREFIX}{user_id}_{uuid4().hex[:8]}",
        expire_at=expire_at,
        traffic_limit_bytes=plan.traffic_limit * GB_TO_BYTES,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        hwid_device_limit=plan.device_limit,
        active_internal_squads=plan.internal_squads or None,
        external_squad_uuid=plan.external_squad,
    )


def configure_for_plan(
    remnawave_user_id: int, plan: PlanSnapshot, expire_at: datetime
) -> UpdateUserRequestDto:
    return UpdateUserRequestDto(
        id=remnawave_user_id,
        expire_at=expire_at,
        traffic_limit_bytes=plan.traffic_limit * GB_TO_BYTES,
        hwid_device_limit=plan.device_limit,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        active_internal_squads=plan.internal_squads or None,
        external_squad_uuid=plan.external_squad,
    )


def restore(subscription: SubscriptionDto) -> UpdateUserRequestDto:
    """Puts a panel user back to the configuration its subscription row holds."""
    return UpdateUserRequestDto(
        id=subscription.remnawave_user_id,
        expire_at=subscription.expire_at,
        traffic_limit_bytes=subscription.effective_traffic_limit * GB_TO_BYTES,
        hwid_device_limit=subscription.effective_device_limit,
        traffic_limit_strategy=subscription.traffic_limit_strategy,
        active_internal_squads=subscription.internal_squads or None,
        external_squad_uuid=subscription.external_squad,
    )


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
        expire_at=expire_at or panel_user.expire_at,
        url=panel_user.subscription_url,
        plan_snapshot=plan,
    )


async def reset_traffic_if_paid(
    sdk: RemnawaveSDK, data: PurchaseSubscriptionDto, subscription: SubscriptionDto
) -> None:
    if not data.reset_traffic:
        return
    # a failure leaves the old counter running, nothing to revert
    try:
        await sdk.users.reset_user_traffic(subscription.remnawave_user_id)
    except Exception:
        logger.exception(f"Failed to reset traffic of subscription '{subscription.id}'")
