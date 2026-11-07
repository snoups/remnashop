import asyncio
from datetime import timedelta

import pytest
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from remnapy.models import UserResponseDto

from app.core.config import AppConfig
from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PanelSyncDirection, PlanType, Role, SubscriptionStatus
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import TOKEN_GRANTABLE_PERMISSIONS, Permission
from app.core.utils.time import datetime_now
from app.modules.plans.dto import CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.subscriptions import panel_sync
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    SyncFromPanelOptionsDto,
    SyncToPanelOptionsDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.panel_sync import (
    claim_panel_sync,
    holding_panel_sync,
    match_shop_user,
    release_panel_sync,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    GetPanelSyncStatusUseCase,
    GetSubscriptionPanelDiffUseCase,
    PullSubscriptionFromPanelUseCase,
    PushSubscriptionToPanelUseCase,
    StartPanelSyncFromUseCase,
    SyncAllFromPanelUseCase,
    SyncAllToPanelUseCase,
    SyncSubscriptionStatusUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.subscriptions.factories import create_subscription, make_eligibility

_FROM = SyncFromPanelOptionsDto(adopt_unnamed=True, respect_subscription_limit=True)
_TO = SyncToPanelOptionsDto(recreate_missing=True, delete_orphans=True)
PREFIX = AppConfig.get().remnawave.username_prefix
OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _panel_user(remnawave_user_id: int, **overrides: object) -> dict[str, object]:
    payload = _user_payload(
        user_id=remnawave_user_id,
        username=f"rs_{remnawave_user_id}",
        expire_at=datetime_now() + timedelta(days=30),
        traffic_limit_bytes=100 * GB_TO_BYTES,
        hwid_device_limit=3,
    )
    payload["subscriptionUrl"] = f"https://example.com/sub/{remnawave_user_id}"
    payload.update(overrides)
    return payload


def _sync(
    subscription_repository: SubscriptionRepository, uow: UnitOfWork, publisher: EventPublisher
) -> SyncSubscriptionStatusUseCase:
    return SyncSubscriptionStatusUseCase(
        subscription_repository,
        uow,
        publisher,
        SubscriptionLifecycleService(subscription_repository),
    )


def test_bulk_syncs_are_not_token_grantable() -> None:
    assert Permission.SUBSCRIPTIONS_PANEL_SYNC_FROM not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_PANEL_SYNC_TO not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_PUSH_TO_PANEL in TOKEN_GRANTABLE_PERMISSIONS


async def test_a_second_start_while_running_is_refused(
    redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    dispatch = RecordingDispatch()
    start = StartPanelSyncFromUseCase(redis, uow, event_publisher, dispatch)
    await release_panel_sync(redis, PanelSyncDirection.FROM_PANEL)
    try:
        started = await start(OWNER, _FROM)
        assert started.running is True
        with pytest.raises(ConflictError):
            await start(OWNER, _FROM)
        assert dispatch.messages == [
            {"direction": "FROM_PANEL", "adopt_unnamed": True, "respect_subscription_limit": True}
        ]
        status = await GetPanelSyncStatusUseCase(redis)(OWNER)
        assert status.from_panel.running is True
    finally:
        await release_panel_sync(redis, PanelSyncDirection.FROM_PANEL)


async def test_a_long_run_keeps_its_running_mark(
    redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(panel_sync, "_RUNNING_REFRESH_S", 0.05)
    key = panel_sync._running_key(PanelSyncDirection.TO_PANEL)
    await release_panel_sync(redis, PanelSyncDirection.TO_PANEL)
    try:
        await claim_panel_sync(redis, PanelSyncDirection.TO_PANEL)
        await redis.expire(key, 1)
        async with holding_panel_sync(redis, PanelSyncDirection.TO_PANEL):
            await asyncio.sleep(0.2)
            assert await redis.ttl(key) > 1
            await release_panel_sync(redis, PanelSyncDirection.TO_PANEL)
            await asyncio.sleep(0.2)
            # a finished run's mark doesn't come back
            assert not await redis.exists(key)
    finally:
        await release_panel_sync(redis, PanelSyncDirection.TO_PANEL)


async def test_sync_to_panel_skips_a_row_deleted_while_it_ran(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subscription = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_011, remnawave_user_id=89_011
    )
    remnawave_store[89_011] = _panel_user(
        89_011, trafficLimitBytes=10 * GB_TO_BYTES, expireAt=subscription.expire_at.isoformat()
    )
    deleted = subscription.model_copy(update={"status": SubscriptionStatus.DELETED})

    async def _deleted(subscription_id: int) -> object:
        return deleted

    monkeypatch.setattr(subscription_repository, "get_by_id", _deleted)

    result = await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        AppConfig.get(),
    ).system(_TO)

    assert remnawave_store[89_011]["trafficLimitBytes"] == 10 * GB_TO_BYTES
    assert result.updated == 0 and result.failed == 0


async def test_sync_to_panel_pushes_rows_that_differ_and_recreates_missing(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    lagging = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_001, remnawave_user_id=89_001
    )
    in_sync = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_002, remnawave_user_id=89_002
    )
    gone = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_003, remnawave_user_id=89_003
    )
    remnawave_store[89_001] = _panel_user(
        89_001, trafficLimitBytes=10 * GB_TO_BYTES, expireAt=lagging.expire_at.isoformat()
    )
    remnawave_store[89_002] = _panel_user(89_002, expireAt=in_sync.expire_at.isoformat())

    result = await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        AppConfig.get(),
    ).system(_TO)

    assert remnawave_store[89_001]["trafficLimitBytes"] == 100 * GB_TO_BYTES
    assert result.updated >= 1 and result.recreated >= 1 and result.missing == 0
    relinked = await subscription_repository.get_by_id(gone.id)
    assert relinked.remnawave_user_id != 89_003
    assert remnawave_store[relinked.remnawave_user_id]["telegramId"] == 89_003
    status = await GetPanelSyncStatusUseCase(redis)(OWNER)
    assert status.to_panel.last is not None
    assert status.to_panel.last.direction is PanelSyncDirection.TO_PANEL


async def test_push_disables_the_panel_user_of_a_disabled_row(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=89_011,
        remnawave_user_id=89_011,
        status=SubscriptionStatus.DISABLED,
    )
    remnawave_store[89_011] = _panel_user(89_011)

    await PushSubscriptionToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        event_publisher,
        uow,
        AppConfig.get(),
    )(OWNER, created.id)

    assert remnawave_store[89_011]["status"] == "DISABLED"


async def test_sync_to_panel_fills_the_owners_contacts_and_keeps_unknown_ones(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_031, remnawave_user_id=89_031
    )
    # no email in the shop: the panel's own stays
    remnawave_store[89_031] = _panel_user(
        89_031, expireAt=created.expire_at.isoformat(), email="panel@example.com"
    )

    result = await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        AppConfig.get(),
    ).system(_TO)

    assert result.updated >= 1
    assert remnawave_store[89_031]["telegramId"] == 89_031
    assert remnawave_store[89_031]["email"] == "panel@example.com"


async def test_diff_lists_a_telegram_id_the_panel_lacks(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_041, remnawave_user_id=89_041
    )
    remnawave_store[89_041] = _panel_user(89_041, expireAt=created.expire_at.isoformat())

    diff = await GetSubscriptionPanelDiffUseCase(
        subscription_repository, user_repository, remnawave_sdk, uow
    )(OWNER, created.id)

    assert [(f.field, f.shop, f.panel) for f in diff.fields] == [("telegram_id", "89041", "")]


def _old() -> str:
    # past the guard for a panel user still being provisioned
    return (datetime_now() - timedelta(days=2)).isoformat()


async def test_sync_from_panel_imports_a_shop_users_panel_user(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="owner", telegram_id=89_051))
    fresh = await user_repository.create(CreateUserDto(name="fresh", telegram_id=89_053))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="import-vip",
            name="VIP",
            type=PlanType.BOTH,
            traffic_limit=50,
            device_limit=1,
            tag="IMPORT_VIP",
        )
    )
    remnawave_store[89_051] = _panel_user(
        89_051, telegramId=89_051, tag="IMPORT_VIP", createdAt=_old()
    )
    remnawave_store[89_052] = _panel_user(89_052, telegramId=1_777, createdAt=_old())
    remnawave_store[89_053] = _panel_user(89_053, telegramId=fresh.telegram_id)

    result = await SyncAllFromPanelUseCase(
        subscription_repository,
        user_repository,
        plan_repository,
        remnawave_sdk,
        _sync(subscription_repository, uow, event_publisher),
        uow,
        redis,
        event_publisher,
        make_eligibility(subscription_repository.session),
        AppConfig.get(),
    ).system(_FROM)

    imported = await subscription_repository.find_by_remnawave_user_id(89_051)
    assert imported is not None
    assert imported.user_id == owner.id
    assert imported.plan_snapshot.plan_id == plan.id
    # the panel's limits, not the plan's
    assert (imported.traffic_limit, imported.device_limit) == (100, 3)
    assert await subscription_repository.find_by_remnawave_user_id(89_052) is None
    assert await subscription_repository.find_by_remnawave_user_id(89_053) is None
    assert result.imported == 1


async def test_sync_to_panel_deletes_a_shop_users_panel_user_without_a_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    await user_repository.create(CreateUserDto(name="orphan", telegram_id=89_061))
    long_expired = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=89_063,
        remnawave_user_id=89_063,
        status=SubscriptionStatus.EXPIRED,
        expire_at=datetime_now() - timedelta(days=100),
    )
    remnawave_store[89_061] = _panel_user(89_061, telegramId=89_061, createdAt=_old())
    remnawave_store[89_062] = _panel_user(89_062, telegramId=1_778, createdAt=_old())
    remnawave_store[89_063] = _panel_user(
        89_063,
        telegramId=89_063,
        createdAt=_old(),
        expireAt=long_expired.expire_at.isoformat(),
    )

    result = await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        AppConfig.get(),
    ).system(_TO)

    assert 89_061 not in remnawave_store
    # someone else's, and one an expired subscription still stands for
    assert 89_062 in remnawave_store and 89_063 in remnawave_store
    assert result.deleted == 1


async def test_push_without_a_panel_user_creates_one_from_the_row(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=89_021,
        remnawave_user_id=89_021,
        status=SubscriptionStatus.DISABLED,
    )

    pushed = await PushSubscriptionToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        event_publisher,
        uow,
        AppConfig.get(),
    )(OWNER, created.id)

    panel_user = remnawave_store[pushed.remnawave_user_id]
    assert pushed.remnawave_user_id != 89_021
    assert pushed.url == panel_user["subscriptionUrl"]
    assert panel_user["status"] == "DISABLED"
    assert panel_user["trafficLimitBytes"] == 100 * GB_TO_BYTES
    assert panel_user["hwidDeviceLimit"] == 3
    assert (await subscription_repository.get_by_id(created.id)).remnawave_user_id == (
        pushed.remnawave_user_id
    )


async def test_diff_lists_fields_that_differ_and_pull_takes_them(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_031, remnawave_user_id=89_031
    )
    remnawave_store[89_031] = _panel_user(
        89_031,
        hwidDeviceLimit=7,
        tag="VIP",
        expireAt=created.expire_at.isoformat(),
        telegramId=89_031,
    )

    diff = await GetSubscriptionPanelDiffUseCase(
        subscription_repository, user_repository, remnawave_sdk, uow
    )(OWNER, created.id)

    assert diff.missing_in_panel is False
    assert {f.field: (f.shop, f.panel) for f in diff.fields} == {
        "device_limit": ("3", "7"),
        "tag": ("", "VIP"),
    }

    pulled = await PullSubscriptionFromPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        _sync(subscription_repository, uow, event_publisher),
        event_publisher,
        uow,
    )(OWNER, created.id)

    assert (pulled.device_limit, pulled.tag) == (7, "VIP")


async def test_pull_marks_a_subscription_gone_from_the_panel_deleted(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_041, remnawave_user_id=89_041
    )

    pulled = await PullSubscriptionFromPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        _sync(subscription_repository, uow, event_publisher),
        event_publisher,
        uow,
    )(OWNER, created.id)

    assert pulled.status is SubscriptionStatus.DELETED


def _named(username: str, **overrides: object) -> UserResponseDto:
    return UserResponseDto.model_validate(_panel_user(1, username=username, **overrides))


async def test_match_shop_user_reads_legacy_and_current_names(
    user_repository: UserRepository,
) -> None:
    by_telegram = await user_repository.create(CreateUserDto(name="tg", telegram_id=89_071))
    web = await user_repository.create(CreateUserDto(name="web"))

    legacy = await match_shop_user(user_repository, _named("rs_89071"), PREFIX)
    legacy_web = await match_shop_user(user_repository, _named(f"rs_web_{web.id}"), PREFIX)
    current = await match_shop_user(user_repository, _named(f"rs_{web.id}_0123abcd"), PREFIX)

    assert legacy is not None and legacy.id == by_telegram.id
    assert legacy_web is not None and legacy_web.id == web.id
    assert current is not None and current.id == web.id


async def test_match_shop_user_refuses_keys_pointing_at_different_users(
    user_repository: UserRepository,
) -> None:
    await user_repository.create(CreateUserDto(name="tg", telegram_id=89_072))
    other = await user_repository.create(CreateUserDto(name="mail", email="other@example.com"))

    assert (
        await match_shop_user(user_repository, _named("rs_89072", email=other.email), PREFIX)
        is None
    )


@pytest.mark.parametrize("username", ["rs_abc", "rs_", "rs_web_", "rs_web_x", "someone"])
async def test_match_shop_user_ignores_other_names(
    user_repository: UserRepository, username: str
) -> None:
    owner = await user_repository.create(CreateUserDto(name="tg", telegram_id=89_073))

    assert await match_shop_user(user_repository, _named(username), PREFIX) is None
    by_telegram = await match_shop_user(
        user_repository, _named(username, telegramId=89_073), PREFIX
    )
    assert by_telegram is not None and by_telegram.id == owner.id


async def test_orphans_are_deleted_only_when_the_shop_named_them(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    current = await user_repository.create(CreateUserDto(name="cur"))
    web = await user_repository.create(CreateUserDto(name="web"))
    await user_repository.create(CreateUserDto(name="tg", telegram_id=89_081))
    await user_repository.create(CreateUserDto(name="hand", telegram_id=89_082))
    await user_repository.create(CreateUserDto(name="mail", email="hand@example.com"))
    names = {
        89_091: f"rs_{current.id}_0123abcd",
        89_092: "rs_89081",
        89_093: f"rs_web_{web.id}",
        89_094: "made_by_hand",
        89_095: "made_by_mail",
    }
    for panel_id, username in names.items():
        remnawave_store[panel_id] = _panel_user(panel_id, username=username, createdAt=_old())
    remnawave_store[89_094]["telegramId"] = 89_082
    remnawave_store[89_095]["email"] = "hand@example.com"

    result = await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        AppConfig.get(),
    ).system(_TO)

    assert not {89_091, 89_092, 89_093} & set(remnawave_store)
    assert {89_094, 89_095} <= set(remnawave_store)
    assert (result.deleted, result.failed) == (3, 0)


@pytest.mark.parametrize("adopt_unnamed", [True, False])
async def test_sync_from_panel_adopts_unnamed_panel_users_only_when_asked(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    adopt_unnamed: bool,
) -> None:
    named = await user_repository.create(CreateUserDto(name="named", telegram_id=89_101))
    await user_repository.create(CreateUserDto(name="hand", telegram_id=89_102))
    remnawave_store[89_111] = _panel_user(
        89_111, username=f"rs_{named.id}_0123abcd", createdAt=_old()
    )
    remnawave_store[89_112] = _panel_user(
        89_112, username="made_by_hand", telegramId=89_102, createdAt=_old()
    )

    await SyncAllFromPanelUseCase(
        subscription_repository,
        user_repository,
        plan_repository,
        remnawave_sdk,
        _sync(subscription_repository, uow, event_publisher),
        uow,
        redis,
        event_publisher,
        make_eligibility(subscription_repository.session),
        AppConfig.get(),
    ).system(SyncFromPanelOptionsDto(adopt_unnamed=adopt_unnamed, respect_subscription_limit=True))

    assert await subscription_repository.find_by_remnawave_user_id(89_111) is not None
    adopted = await subscription_repository.find_by_remnawave_user_id(89_112)
    assert (adopted is not None) is adopt_unnamed


async def test_sync_to_panel_can_skip_recreating_and_deleting(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    gone = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_121, remnawave_user_id=89_121
    )
    orphan_owner = await user_repository.create(CreateUserDto(name="orphan"))
    remnawave_store[89_122] = _panel_user(
        89_122, username=f"rs_{orphan_owner.id}_0123abcd", createdAt=_old()
    )

    result = await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        AppConfig.get(),
    ).system(SyncToPanelOptionsDto(recreate_missing=False, delete_orphans=False))

    assert (result.recreated, result.deleted) == (0, 0)
    assert (await subscription_repository.get_by_id(gone.id)).remnawave_user_id == 89_121
    assert 89_121 not in remnawave_store
    assert 89_122 in remnawave_store


async def test_sync_to_panel_leaves_another_prefixs_panel_users_alone(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="shared", telegram_id=89_131))
    remnawave_store[89_131] = _panel_user(
        89_131, username=f"rs_{owner.id}_0123abcd", telegramId=89_131, createdAt=_old()
    )
    remnawave_store[89_132] = _panel_user(
        89_132, username=f"shopb_{owner.id}_0123abcd", createdAt=_old()
    )
    config = AppConfig.get()
    shop_b = config.model_copy(
        update={"remnawave": config.remnawave.model_copy(update={"username_prefix": "shopb_"})}
    )

    result = await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        shop_b,
    ).system(_TO)

    assert 89_131 in remnawave_store
    assert 89_132 not in remnawave_store
    assert result.deleted == 1


@pytest.mark.parametrize("respect_limit", [True, False])
async def test_sync_from_panel_imports_past_the_subscription_cap_only_when_asked(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    plan_repository: PlanRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    respect_limit: bool,
) -> None:
    # two live subscriptions of the default cap of 3, two more panel users of the same person
    sub = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_201, remnawave_user_id=89_211
    )
    await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=sub.user_id,
            remnawave_user_id=89_212,
            status=sub.status,
            is_trial=False,
            traffic_limit=sub.traffic_limit,
            device_limit=sub.device_limit,
            expire_at=sub.expire_at,
            url="https://example.com/sub/89212",
            plan_snapshot=sub.plan_snapshot,
        )
    )
    for remnawave_user_id in (89_211, 89_212):
        remnawave_store[remnawave_user_id] = _panel_user(
            remnawave_user_id, telegramId=89_201, createdAt=_old()
        )
    for remnawave_user_id, username in ((89_213, "hand_a"), (89_214, "hand_b")):
        remnawave_store[remnawave_user_id] = _panel_user(
            remnawave_user_id, username=username, telegramId=89_201, createdAt=_old()
        )

    result = await SyncAllFromPanelUseCase(
        subscription_repository,
        user_repository,
        plan_repository,
        remnawave_sdk,
        _sync(subscription_repository, uow, event_publisher),
        uow,
        redis,
        event_publisher,
        make_eligibility(subscription_repository.session),
        AppConfig.get(),
    ).system(SyncFromPanelOptionsDto(adopt_unnamed=True, respect_subscription_limit=respect_limit))

    imported = [
        await subscription_repository.find_by_remnawave_user_id(remnawave_user_id)
        for remnawave_user_id in (89_213, 89_214)
    ]
    if respect_limit:
        assert sum(row is not None for row in imported) == 1
        assert (result.imported, result.over_limit) == (1, 1)
    else:
        assert all(row is not None for row in imported)
        assert (result.imported, result.over_limit) == (2, 0)
