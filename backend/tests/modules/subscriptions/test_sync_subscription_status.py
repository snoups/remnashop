import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SubscriptionStatus
from app.core.exceptions import PermissionDeniedError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import CreateSubscriptionDto, SyncSubscriptionStatusDto
from app.modules.subscriptions.events import SubscriptionStatusSyncedEvent
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import SyncSubscriptionStatusUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot


async def _create_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_user_id: int,
    status: SubscriptionStatus,
) -> int:
    user = await user_repository.create(
        CreateUserDto(name=f"user{remnawave_user_id}", telegram_id=remnawave_user_id)
    )
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=remnawave_user_id,
            status=status,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url=f"https://fake-panel.test/sub/{remnawave_user_id}",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    return created.id


async def test_sync_updates_status_on_a_matching_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await _create_subscription(
        subscription_repository, user_repository, 71001, SubscriptionStatus.ACTIVE
    )
    lifecycle_service = SubscriptionLifecycleService(subscription_repository)
    use_case = SyncSubscriptionStatusUseCase(
        subscription_repository, uow, event_publisher, lifecycle_service
    )

    result = await use_case.system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=71001, status=SubscriptionStatus.LIMITED, source="webhook"
        )
    )

    assert result is not None
    assert result.status == SubscriptionStatus.LIMITED


async def test_sync_is_a_noop_for_an_unknown_remnawave_user_id(
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    lifecycle_service = SubscriptionLifecycleService(subscription_repository)
    use_case = SyncSubscriptionStatusUseCase(
        subscription_repository, uow, event_publisher, lifecycle_service
    )

    result = await use_case.system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=999999, status=SubscriptionStatus.LIMITED, source="webhook"
        )
    )

    assert result is None


async def test_sync_is_a_noop_when_already_at_the_target_status(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await _create_subscription(
        subscription_repository, user_repository, 71002, SubscriptionStatus.LIMITED
    )
    lifecycle_service = SubscriptionLifecycleService(subscription_repository)
    use_case = SyncSubscriptionStatusUseCase(
        subscription_repository, uow, event_publisher, lifecycle_service
    )

    result = await use_case.system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=71002, status=SubscriptionStatus.LIMITED, source="webhook"
        )
    )

    assert result is not None
    assert result.status == SubscriptionStatus.LIMITED


async def test_sync_is_a_noop_on_an_already_deleted_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await _create_subscription(
        subscription_repository, user_repository, 71003, SubscriptionStatus.DELETED
    )
    lifecycle_service = SubscriptionLifecycleService(subscription_repository)
    use_case = SyncSubscriptionStatusUseCase(
        subscription_repository, uow, event_publisher, lifecycle_service
    )

    result = await use_case.system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=71003, status=SubscriptionStatus.ACTIVE, source="webhook"
        )
    )

    assert result is not None
    assert result.status == SubscriptionStatus.DELETED


async def test_real_actor_cannot_call_sync_directly(
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    actor = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
    lifecycle_service = SubscriptionLifecycleService(subscription_repository)
    use_case = SyncSubscriptionStatusUseCase(
        subscription_repository, uow, event_publisher, lifecycle_service
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            actor,
            SyncSubscriptionStatusDto(
                remnawave_user_id=1, status=SubscriptionStatus.ACTIVE, source="webhook"
            ),
        )


class _RecordingEventPublisher:
    def __init__(self) -> None:
        self.events: list[SubscriptionStatusSyncedEvent] = []

    async def publish(self, event: object) -> None:
        if isinstance(event, SubscriptionStatusSyncedEvent):
            self.events.append(event)


async def test_concurrent_syncs_on_the_same_row_serialize_last_writer_wins(
    engine: AsyncEngine,
) -> None:
    # A genuine concurrency check needs two independent DB connections --
    # SQLAlchemy's AsyncSession forbids concurrent use from two coroutines on
    # one session ("Session is already flushing"), which is what the shared
    # subscription_repository/uow fixtures this file otherwise uses would be.
    # Row is committed for real so both connections can see it, then cleaned
    # up explicitly (in `finally`) since it bypasses the usual
    # rollback-per-test fixture.
    async with engine.connect() as conn_a, engine.connect() as conn_b:
        session_a = AsyncSession(bind=conn_a, expire_on_commit=False)
        session_b = AsyncSession(bind=conn_b, expire_on_commit=False)
        repo_a = SubscriptionRepository(session_a)
        repo_b = SubscriptionRepository(session_b)

        created = await create_subscription(
            repo_a, UserRepository(session_a), telegram_id=701, remnawave_user_id=701001
        )
        await session_a.commit()

        try:
            event_publisher = _RecordingEventPublisher()
            use_case_a = SyncSubscriptionStatusUseCase(
                repo_a,
                UnitOfWork(session_a),
                event_publisher,
                SubscriptionLifecycleService(repo_a),
            )
            use_case_b = SyncSubscriptionStatusUseCase(
                repo_b,
                UnitOfWork(session_b),
                event_publisher,
                SubscriptionLifecycleService(repo_b),
            )

            await asyncio.gather(
                use_case_a.system(
                    SyncSubscriptionStatusDto(
                        remnawave_user_id=created.remnawave_user_id,
                        status=SubscriptionStatus.LIMITED,
                        source="webhook",
                    )
                ),
                use_case_b.system(
                    SyncSubscriptionStatusDto(
                        remnawave_user_id=created.remnawave_user_id,
                        status=SubscriptionStatus.DISABLED,
                        source="reconcile",
                    )
                ),
            )

            reloaded = await repo_a.get_by_id(created.id)
            assert reloaded.status in (SubscriptionStatus.LIMITED, SubscriptionStatus.DISABLED)

            # The lock forces a genuine causal chain: whichever call ran
            # second must have observed the FIRST call's committed write as
            # its old_status, not the original seed status -- under the old
            # unlocked code both could read the stale seed and this would fail.
            assert len(event_publisher.events) == 2
            by_new_status = {e.new_status: e for e in event_publisher.events}
            limited_event = by_new_status[SubscriptionStatus.LIMITED.value]
            disabled_event = by_new_status[SubscriptionStatus.DISABLED.value]
            assert (
                limited_event.old_status == SubscriptionStatus.ACTIVE.value
                and disabled_event.old_status == SubscriptionStatus.LIMITED.value
            ) or (
                disabled_event.old_status == SubscriptionStatus.ACTIVE.value
                and limited_event.old_status == SubscriptionStatus.DISABLED.value
            )

        finally:
            await session_a.close()
            await session_b.close()
            async with engine.connect() as cleanup_conn:
                await cleanup_conn.execute(
                    text("DELETE FROM subscriptions WHERE id = :id"), {"id": created.id}
                )
                await cleanup_conn.execute(
                    text("DELETE FROM users WHERE id = :id"), {"id": created.user_id}
                )
                await cleanup_conn.commit()
