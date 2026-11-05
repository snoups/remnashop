import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from functools import partial
from typing import Final, Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError
from remnapy import RemnawaveSDK
from remnapy.enums import UserStatus
from remnapy.models import UserResponseDto

from app.core.actor import Actor
from app.core.constants import GB_TO_BYTES, REDIS_KEY_PREFIX, TTL_1H, TTL_5M, TTL_7D, ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PanelSyncDirection, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import truncate_to_ms
from app.modules.plans import PlanDto
from app.modules.subscriptions.dispatch import PanelSyncDispatch
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    PanelFieldDiffDto,
    PanelSyncResultDto,
    PanelSyncStatusDto,
    PlanSnapshot,
    SubscriptionDto,
    SyncSubscriptionStatusDto,
)
from app.modules.subscriptions.eligibility import subscription_owner
from app.modules.subscriptions.events import PanelSyncStartedEvent, StatusSyncSource
from app.modules.subscriptions.panel import (
    panel_user_from_row,
    restore,
    shop_user_key_from_username,
)
from app.modules.subscriptions.panel_config import (
    changed_config_fields,
    config_update,
    panel_config,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto, UserRepository

# keyset pages, each one request to the panel
_STREAM_PAGE: Final[int] = 500
# a crashed run must not block the next one for long
_RUNNING_TTL_S: Final[int] = TTL_1H
# a live run outlasting the TTL keeps its mark, so a second one can't start
_RUNNING_REFRESH_S: Final[int] = TTL_5M
_RESULT_TTL_S: Final[int] = TTL_7D
# a purchase creates its panel user before its row commits: a younger panel
# user without a row may be one still being provisioned
_ORPHAN_MIN_AGE: Final[timedelta] = timedelta(seconds=TTL_1H)
# a snapshot naming no plan: nothing to renew, bonus days and promocodes see a
# deleted plan
_IMPORTED_PLAN_ID: Final[int] = 0
_IMPORTED_PLAN_CODE: Final[str] = "imported"
_IMPORTED_PLAN_NAME: Final[str] = "Imported"


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


def is_orphan(user: UserResponseDto, linked_ids: set[int], now: datetime) -> bool:
    """A panel user no subscription stands for, old enough not to be mid-purchase."""
    return user.id not in linked_ids and user.created_at < now - _ORPHAN_MIN_AGE


async def named_shop_user(user_repository: UserRepository, username: str) -> Optional[UserDto]:
    """The shop user a shop-format panel username (current or legacy) names."""
    if (named := shop_user_key_from_username(username)) is None:
        return None
    key, value = named
    if key == "id":
        return await user_repository.find_by_id(value)
    return await user_repository.find_by_telegram_id(value)


async def match_shop_user(
    user_repository: UserRepository, user: UserResponseDto
) -> Optional[UserDto]:
    """The shop user a panel user belongs to: by the shop's own username, its
    Telegram or email. Keys pointing at different users match nobody."""
    found = [await named_shop_user(user_repository, user.username)]
    if user.telegram_id is not None:
        found.append(await user_repository.find_by_telegram_id(user.telegram_id))
    if user.email:
        found.append(await user_repository.find_by_email(user.email))
    matched = {candidate.id: candidate for candidate in found if candidate is not None}
    if len(matched) != 1:
        return None
    return next(iter(matched.values()))


def imported_row(
    user: UserResponseDto, owner: UserDto, plans: Sequence[PlanDto]
) -> CreateSubscriptionDto:
    """A subscription row for a panel user the shop has no row for."""
    config = panel_config(user)
    tagged = [plan for plan in plans if config.tag and plan.tag == config.tag]
    if len(tagged) == 1:
        # renewable as that plan; the limits stay the panel's
        snapshot = PlanSnapshot.from_plan(
            tagged[0], price_paid=ZERO_AMOUNT, currency=Currency.USD, duration_days=0
        )
    else:
        snapshot = PlanSnapshot(
            plan_id=_IMPORTED_PLAN_ID,
            public_code=_IMPORTED_PLAN_CODE,
            name=_IMPORTED_PLAN_NAME,
            price_paid=ZERO_AMOUNT,
            currency=Currency.USD,
            duration_days=0,
            traffic_limit=config.traffic_limit,
            device_limit=config.device_limit,
            traffic_limit_strategy=config.traffic_limit_strategy,
            is_trial=False,
            internal_squads=config.internal_squads,
            external_squad=config.external_squad,
            tag=config.tag,
            credit_paid=ZERO_AMOUNT,
            credit_days=0,
        )
    return CreateSubscriptionDto(
        user_id=owner.id,
        remnawave_user_id=user.id,
        status=SubscriptionStatus(user.status),
        traffic_limit=config.traffic_limit,
        device_limit=config.device_limit,
        traffic_limit_strategy=config.traffic_limit_strategy,
        is_trial=snapshot.is_trial,
        tag=config.tag,
        internal_squads=config.internal_squads,
        external_squad=config.external_squad,
        expire_at=user.expire_at,
        url=config.url,
        plan_snapshot=snapshot,
    )


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


def _shop_contact(owner: UserDto) -> dict[str, str]:
    # only what the shop knows: a push never clears the panel's own value
    contact = {}
    if owner.telegram_id is not None:
        contact["telegram_id"] = str(owner.telegram_id)
    if owner.email is not None:
        contact["email"] = owner.email
    return contact


def _panel_contact(user: UserResponseDto) -> dict[str, str]:
    return {
        "telegram_id": str(user.telegram_id) if user.telegram_id is not None else "",
        "email": user.email or "",
    }


def _contact_lags(owner: UserDto, user: UserResponseDto) -> bool:
    panel = _panel_contact(user)
    return any(panel[name] != value for name, value in _shop_contact(owner).items())


def panel_diff(
    subscription: SubscriptionDto, user: UserResponseDto, owner: UserDto
) -> list[PanelFieldDiffDto]:
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
    shop_contact = _shop_contact(owner)
    shop.update(shop_contact)
    panel.update({name: _panel_contact(user)[name] for name in shop_contact})
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


def panel_lags_behind(subscription: SubscriptionDto, user: UserResponseDto, owner: UserDto) -> bool:
    """Whether pushing the row would change anything in the panel."""
    wanted = restore(subscription)
    return (
        # restore() leaves a past date out: the panel would refuse it
        (
            wanted.expire_at is not None
            and truncate_to_ms(user.expire_at) != truncate_to_ms(subscription.expire_at)
        )
        or int(user.traffic_limit_bytes) != subscription.effective_traffic_limit * GB_TO_BYTES
        or (user.hwid_device_limit or 0) != subscription.effective_device_limit
        or user.traffic_limit_strategy != wanted.traffic_limit_strategy
        or {s.uuid for s in user.active_internal_squads} != set(subscription.internal_squads)
        or user.external_squad_uuid != subscription.external_squad
        or _disabled_mismatch(subscription, user)
        or _contact_lags(owner, user)
    )


def _disabled_mismatch(subscription: SubscriptionDto, user: UserResponseDto) -> bool:
    # only the switch an admin flips is ours to push; expired and limited are
    # the panel's verdicts
    return (subscription.status is SubscriptionStatus.DISABLED) != (
        user.status == UserStatus.DISABLED
    )


async def push_to_panel(
    sdk: RemnawaveSDK, subscription: SubscriptionDto, owner: UserDto
) -> UserResponseDto:
    """Puts the row's configuration, on/off switch and the owner's contacts into the panel."""
    pushed: UserResponseDto = await sdk.users.update_user(restore(subscription, owner))
    if _disabled_mismatch(subscription, pushed):
        if subscription.status is SubscriptionStatus.DISABLED:
            pushed = await sdk.users.disable_user(subscription.remnawave_user_id)
        else:
            pushed = await sdk.users.enable_user(subscription.remnawave_user_id)
    return pushed


async def recreate_in_panel(
    sdk: RemnawaveSDK,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    subscription: SubscriptionDto,
) -> SubscriptionDto:
    """Gives a row whose panel user is gone a new one built from the row."""
    async with uow:
        owner = await subscription_owner(user_repository, subscription)
    created = await sdk.users.create_user(panel_user_from_row(subscription, owner))
    try:
        async with uow:
            locked = await subscription_repository.get_by_id_for_update(subscription.id)
            if locked.status is SubscriptionStatus.DELETED:
                raise ValidationError(
                    f"Subscription '{subscription.id}' was deleted",
                    code=ErrorCode.SUBSCRIPTION_DELETED,
                )
            if locked.remnawave_user_id != subscription.remnawave_user_id:
                # recreated by a concurrent push: ours is a spare
                with suppress(Exception):
                    await sdk.users.delete_user(created.id)
                return locked
            return await subscription_repository.relink_panel_user(
                locked.id, created.id, created.subscription_url
            )
    except BaseException:
        # nothing points at it, and an unlinked panel user would give free access
        with suppress(Exception):
            await sdk.users.delete_user(created.id)
        raise


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


@asynccontextmanager
async def holding_panel_sync(redis: Redis, direction: PanelSyncDirection) -> AsyncIterator[None]:
    async def _refresh() -> None:
        while True:
            await asyncio.sleep(_RUNNING_REFRESH_S)
            # EXPIRE on a released mark is a no-op: nothing comes back after finish
            with suppress(RedisError):
                await redis.expire(_running_key(direction), _RUNNING_TTL_S)

    task = asyncio.create_task(_refresh())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


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
