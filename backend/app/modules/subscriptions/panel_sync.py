from collections.abc import AsyncIterator
from functools import partial
from typing import Final, Optional

from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from remnapy.enums import UserStatus
from remnapy.models import UserResponseDto

from app.core.actor import Actor
from app.core.constants import GB_TO_BYTES, REDIS_KEY_PREFIX, TTL_1H, TTL_7D
from app.core.db.uow import UnitOfWork
from app.core.enums import PanelSyncDirection, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.utils.time import truncate_to_ms
from app.modules.subscriptions.dispatch import PanelSyncDispatch
from app.modules.subscriptions.dto import (
    PanelFieldDiffDto,
    PanelSyncResultDto,
    PanelSyncStatusDto,
    SubscriptionDto,
    SyncSubscriptionStatusDto,
)
from app.modules.subscriptions.events import PanelSyncStartedEvent, StatusSyncSource
from app.modules.subscriptions.panel import restore
from app.modules.subscriptions.panel_config import (
    changed_config_fields,
    config_update,
    panel_config,
)

# keyset pages, each one request to the panel
_STREAM_PAGE: Final[int] = 500
# a crashed run must not block the next one for long
_RUNNING_TTL_S: Final[int] = TTL_1H
_RESULT_TTL_S: Final[int] = TTL_7D


async def panel_users(sdk: RemnawaveSDK) -> AsyncIterator[UserResponseDto]:
    """Every panel user, a page at a time."""
    cursor: Optional[int] = None
    while True:
        page = await sdk.users.get_users_stream(size=_STREAM_PAGE, cursor=cursor)
        for user in page.users:
            yield user
        if not page.has_more or page.next_cursor is None:
            return
        cursor = int(page.next_cursor)


def from_panel(
    user: Optional[UserResponseDto], remnawave_user_id: int, source: StatusSyncSource
) -> SyncSubscriptionStatusDto:
    """What the row should take from the panel; a missing panel user deletes it."""
    if user is None:
        return SyncSubscriptionStatusDto(
            remnawave_user_id=remnawave_user_id, status=SubscriptionStatus.DELETED, source=source
        )
    return SyncSubscriptionStatusDto(
        remnawave_user_id=remnawave_user_id,
        status=SubscriptionStatus(user.status),
        source=source,
        expire_at=user.expire_at,
        config=panel_config(user),
    )


def panel_diff(subscription: SubscriptionDto, user: UserResponseDto) -> list[PanelFieldDiffDto]:
    """Fields where the row and the panel disagree, in the panel's (effective) terms."""
    config = panel_config(user)
    shop = {
        "status": subscription.status.value,
        "expire_at": truncate_to_ms(subscription.expire_at).isoformat(),
        "url": subscription.url,
        "traffic_limit": str(subscription.effective_traffic_limit),
        "device_limit": str(subscription.effective_device_limit),
        "traffic_limit_strategy": str(subscription.traffic_limit_strategy),
        "tag": subscription.tag or "",
        "internal_squads": ",".join(sorted(str(s) for s in subscription.internal_squads)),
        "external_squad": str(subscription.external_squad or ""),
    }
    panel = {
        "status": SubscriptionStatus(user.status).value,
        "expire_at": truncate_to_ms(user.expire_at).isoformat(),
        "url": config.url,
        "traffic_limit": str(config.traffic_limit),
        "device_limit": str(config.device_limit),
        "traffic_limit_strategy": str(config.traffic_limit_strategy),
        "tag": config.tag or "",
        "internal_squads": ",".join(sorted(str(s) for s in config.internal_squads)),
        "external_squad": str(config.external_squad or ""),
    }
    return [
        PanelFieldDiffDto(field=name, shop=shop[name], panel=panel[name])
        for name in shop
        if shop[name] != panel[name]
    ]


def differs_from_panel(subscription: SubscriptionDto, user: UserResponseDto) -> bool:
    return (
        subscription.status is not SubscriptionStatus(user.status)
        or truncate_to_ms(subscription.expire_at) != truncate_to_ms(user.expire_at)
        or bool(
            changed_config_fields(subscription, config_update(subscription, panel_config(user)))
        )
    )


def panel_lags_behind(subscription: SubscriptionDto, user: UserResponseDto) -> bool:
    """Whether pushing the row would change anything in the panel."""
    wanted = restore(subscription)
    return (
        truncate_to_ms(user.expire_at) != truncate_to_ms(subscription.expire_at)
        or int(user.traffic_limit_bytes) != subscription.effective_traffic_limit * GB_TO_BYTES
        or (user.hwid_device_limit or 0) != subscription.effective_device_limit
        or user.traffic_limit_strategy != wanted.traffic_limit_strategy
        or {s.uuid for s in user.active_internal_squads} != set(subscription.internal_squads)
        or user.external_squad_uuid != subscription.external_squad
        or _disabled_mismatch(subscription, user)
    )


def _disabled_mismatch(subscription: SubscriptionDto, user: UserResponseDto) -> bool:
    # only the switch an admin flips is ours to push; expired and limited are
    # the panel's own verdicts
    return (subscription.status is SubscriptionStatus.DISABLED) != (
        user.status == UserStatus.DISABLED
    )


async def push_to_panel(
    sdk: RemnawaveSDK, subscription: SubscriptionDto, user: UserResponseDto
) -> UserResponseDto:
    """Puts the row's configuration and on/off switch into the panel."""
    pushed: UserResponseDto = await sdk.users.update_user(restore(subscription))
    if _disabled_mismatch(subscription, pushed):
        if subscription.status is SubscriptionStatus.DISABLED:
            pushed = await sdk.users.disable_user(subscription.remnawave_user_id)
        else:
            pushed = await sdk.users.enable_user(subscription.remnawave_user_id)
    return pushed


def _running_key(direction: PanelSyncDirection) -> str:
    return f"{REDIS_KEY_PREFIX}panel_sync:{direction.value}:running"


def _result_key(direction: PanelSyncDirection) -> str:
    return f"{REDIS_KEY_PREFIX}panel_sync:{direction.value}:last"


async def claim_panel_sync(redis: Redis, direction: PanelSyncDirection) -> None:
    if not await redis.set(_running_key(direction), "1", nx=True, ex=_RUNNING_TTL_S):
        raise ConflictError("A panel sync is already running", code=ErrorCode.PANEL_SYNC_RUNNING)


async def finish_panel_sync(
    redis: Redis, direction: PanelSyncDirection, result: PanelSyncResultDto
) -> None:
    await redis.set(_result_key(direction), result.model_dump_json(), ex=_RESULT_TTL_S)
    await redis.delete(_running_key(direction))


async def read_panel_sync_status(redis: Redis, direction: PanelSyncDirection) -> PanelSyncStatusDto:
    running = bool(await redis.exists(_running_key(direction)))
    raw = await redis.get(_result_key(direction))
    last = PanelSyncResultDto.model_validate_json(raw) if raw else None
    return PanelSyncStatusDto(direction=direction, running=running, last=last)


async def release_panel_sync(redis: Redis, direction: PanelSyncDirection) -> None:
    await redis.delete(_running_key(direction))


async def start_panel_sync(
    redis: Redis,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    dispatch: PanelSyncDispatch,
    actor: Actor,
    direction: PanelSyncDirection,
) -> PanelSyncStatusDto:
    await claim_panel_sync(redis, direction)
    try:
        async with uow:
            await event_publisher.publish(PanelSyncStartedEvent(actor=actor, direction=direction))
            await uow.after_commit(partial(dispatch.kiq, direction=direction.value))
    except BaseException:
        await release_panel_sync(redis, direction)
        raise
    return await read_panel_sync_status(redis, direction)
