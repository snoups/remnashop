from uuid import UUID, uuid4

from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PanelSyncDirection, Role
from app.core.ports import EventPublisher
from app.modules.subscriptions.dto import (
    PushSubscriptionToPanelDto,
    SubscriptionDto,
    SyncToPanelOptionsDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.panel_squads import missing_by_kind, replace_squads
from app.modules.subscriptions.panel_sync import release_panel_sync
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    GetSubscriptionPanelDiffUseCase,
    ListMissingPanelSquadsUseCase,
    PushSubscriptionToPanelUseCase,
    StartPanelSyncToUseCase,
    SyncAllToPanelUseCase,
)
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.panel_squads import FixedPanelSquads
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.subscriptions.factories import create_subscription

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
KEPT, GONE, NEW, GONE_EXTERNAL = uuid4(), uuid4(), uuid4(), uuid4()


def test_replace_squads_swaps_drops_and_merges() -> None:
    other = uuid4()

    assert replace_squads([GONE, KEPT], None, {GONE: NEW}) == ([NEW, KEPT], None)
    assert replace_squads([GONE, KEPT], GONE_EXTERNAL, {GONE: None, GONE_EXTERNAL: None}) == (
        [KEPT],
        None,
    )
    assert replace_squads([GONE, other], None, {GONE: KEPT, other: KEPT}) == ([KEPT], None)
    assert replace_squads([KEPT], NEW, {}) == ([KEPT], NEW)


def test_missing_by_kind_counts_holders() -> None:
    known = frozenset({KEPT})

    missing = missing_by_kind(
        [([GONE, KEPT], GONE_EXTERNAL), ([GONE], None), ([KEPT], None)], known
    )

    assert {(m.uuid, m.kind, m.subscriptions) for m in missing} == {
        (GONE, "internal", 2),
        (GONE_EXTERNAL, "external", 1),
    }


async def _with_squads(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_store: FakeUserStore,
    remnawave_user_id: int,
    internal: list[UUID],
) -> SubscriptionDto:
    created = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=remnawave_user_id,
        remnawave_user_id=remnawave_user_id,
    )
    remnawave_store[remnawave_user_id] = _user_payload(
        user_id=remnawave_user_id,
        username=f"rs_{remnawave_user_id}",
        expire_at=created.expire_at,
        traffic_limit_bytes=0,
        hwid_device_limit=0,
    )
    return await subscription_repository.update_squads(
        UpdateSubscriptionSquadsDto(
            subscription_id=created.id, internal_squads=internal, external_squad=None
        )
    )


async def test_diff_names_the_rows_squads_the_panel_lacks(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
) -> None:
    created = await _with_squads(
        subscription_repository, user_repository, remnawave_store, 89_301, [GONE, KEPT]
    )

    diff = await GetSubscriptionPanelDiffUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        FixedPanelSquads(frozenset({KEPT, NEW})),
        uow,
    )(OWNER, created.id)

    assert [(m.uuid, m.kind) for m in diff.missing_squads] == [(GONE, "internal")]


async def test_push_replaces_the_picked_squads_before_it_writes(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> None:
    created = await _with_squads(
        subscription_repository, user_repository, remnawave_store, 89_302, [GONE, KEPT]
    )

    pushed = await PushSubscriptionToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        event_publisher,
        uow,
        AppConfig.get(),
    )(OWNER, PushSubscriptionToPanelDto(subscription_id=created.id, squad_replacements={GONE: NEW}))

    assert pushed.internal_squads == [NEW, KEPT]
    stored = await subscription_repository.get_by_id(created.id)
    assert stored.internal_squads == [NEW, KEPT]


async def test_bulk_push_replaces_squads_on_every_row_holding_them(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    first = await _with_squads(
        subscription_repository, user_repository, remnawave_store, 89_303, [GONE]
    )
    second = await _with_squads(
        subscription_repository, user_repository, remnawave_store, 89_304, [GONE, KEPT]
    )
    untouched = await _with_squads(
        subscription_repository, user_repository, remnawave_store, 89_305, [KEPT]
    )

    missing = await ListMissingPanelSquadsUseCase(
        subscription_repository, FixedPanelSquads(frozenset({KEPT, NEW})), uow
    )(OWNER)
    await SyncAllToPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        redis,
        event_publisher,
        AppConfig.get(),
    ).system(
        SyncToPanelOptionsDto(
            recreate_missing=False, delete_orphans=False, squad_replacements={GONE: NEW}
        )
    )

    assert [(m.uuid, m.subscriptions) for m in missing] == [(GONE, 2)]
    rows = [await subscription_repository.get_by_id(s.id) for s in (first, second, untouched)]
    assert [row.internal_squads for row in rows] == [[NEW], [NEW, KEPT], [KEPT]]


async def test_bulk_push_queues_the_replacements_as_strings(
    redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    dispatch = RecordingDispatch()
    await release_panel_sync(redis, PanelSyncDirection.TO_PANEL)
    try:
        await StartPanelSyncToUseCase(redis, uow, event_publisher, dispatch)(
            OWNER,
            SyncToPanelOptionsDto(
                recreate_missing=True, delete_orphans=True, squad_replacements={GONE: None}
            ),
        )
    finally:
        await release_panel_sync(redis, PanelSyncDirection.TO_PANEL)

    assert dispatch.messages == [
        {
            "direction": "TO_PANEL",
            "recreate_missing": True,
            "delete_orphans": True,
            "squad_replacements": {str(GONE): None},
        }
    ]
