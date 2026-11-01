from collections.abc import Awaitable, Callable
from typing import Optional

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import GetAccessSettingsUseCase
from app.modules.transactions.dto import NotifyPaymentWaitlistDto
from app.modules.transactions.usecases import (
    JoinPaymentWaitlistUseCase,
    NotifyPaymentWaitlistUseCase,
    notify_payment_waitlist,
)
from app.modules.transactions.waitlist_repository import WaitlistClaims, WaitlistRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


class _FakeNotifier:
    def __init__(self, on_notify: Optional[Callable[[list[int]], Awaitable[None]]] = None) -> None:
        self._on_notify = on_notify
        self.calls: list[tuple[list[int], int]] = []

    async def notify(self, user_ids: list[int], outbox_id: int) -> None:
        self.calls.append((user_ids, outbox_id))
        if self._on_notify is not None:
            await self._on_notify(user_ids)


_DTO = NotifyPaymentWaitlistDto(outbox_id=31)


@pytest.fixture
def session_maker(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    # claim transactions become savepoints of the test's own rolled-back transaction
    return async_sessionmaker(
        bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


def _use_case(
    session_maker: async_sessionmaker[AsyncSession],
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    notifier: _FakeNotifier,
) -> NotifyPaymentWaitlistUseCase:
    return NotifyPaymentWaitlistUseCase(
        WaitlistClaims(session_maker), GetAccessSettingsUseCase(settings_repository, uow), notifier
    )


async def _waitlisted(
    user_repository: UserRepository, uow: UnitOfWork, waitlist: WaitlistRepository, count: int
) -> list[int]:
    ids = []
    async with uow:
        for n in range(count):
            user = await user_repository.create(
                CreateUserDto(name=f"w{n}", telegram_id=811_000 + n)
            )
            await waitlist.add(user.id)
            ids.append(user.id)
    return ids


async def test_add_is_idempotent_and_counted(
    waitlist_repository: WaitlistRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await user_repository.create(CreateUserDto(name="w", telegram_id=810_001))
    async with uow:
        await waitlist_repository.add(user.id)
        await waitlist_repository.add(user.id)
        assert await waitlist_repository.count() == 1


async def test_claim_batch_honours_limit_and_exclude(
    waitlist_repository: WaitlistRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    a, b, c = await _waitlisted(user_repository, uow, waitlist_repository, 3)
    async with uow:
        assert await waitlist_repository.claim_batch(2, set()) == [a, b]
        assert await waitlist_repository.claim_batch(5, {a}) == [b, c]


async def test_notify_queues_in_batches_and_empties_the_waitlist(
    session_maker: async_sessionmaker[AsyncSession],
    settings_repository: SettingsRepository,
    waitlist_repository: WaitlistRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notify_payment_waitlist, "_BATCH_SIZE", 2)
    a, b, c = await _waitlisted(user_repository, uow, waitlist_repository, 3)
    notifier = _FakeNotifier()

    await _use_case(session_maker, settings_repository, uow, notifier).system(_DTO)

    assert notifier.calls == [([a, b], _DTO.outbox_id), ([c], _DTO.outbox_id)]
    async with uow:
        assert await waitlist_repository.count() == 0


async def test_notify_with_empty_waitlist_sends_nothing(
    session_maker: async_sessionmaker[AsyncSession],
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    notifier = _FakeNotifier()
    await _use_case(session_maker, settings_repository, uow, notifier).system(_DTO)
    assert notifier.calls == []


async def test_notify_does_nothing_while_payments_are_disabled(
    session_maker: async_sessionmaker[AsyncSession],
    settings_repository: SettingsRepository,
    waitlist_repository: WaitlistRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    ids = await _waitlisted(user_repository, uow, waitlist_repository, 2)
    async with uow:
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(payments_enabled=False)
        )
    notifier = _FakeNotifier()

    await _use_case(session_maker, settings_repository, uow, notifier).system(_DTO)

    assert notifier.calls == []
    async with uow:
        assert await waitlist_repository.claim_batch(100, set()) == ids


async def test_concurrent_run_skips_rows_claimed_by_a_running_batch(
    engine: AsyncEngine, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    # real commits on the machine-wide test DB: only this test's ids are marked done
    # or asserted on, so other sessions' rows are never removed
    real_sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with real_sessions() as setup, setup.begin():
        users = [
            await UserRepository(setup).create(CreateUserDto(name=f"c{n}", telegram_id=812_000 + n))
            for n in range(2)
        ]
        ids = [user.id for user in users]
        for user_id in ids:
            await WaitlistRepository(setup).add(user_id)

    seen_by_second_run: list[int] = []

    async def _claim_from_second_run(batch: list[int]) -> None:
        async with real_sessions() as other, other.begin():
            seen_by_second_run.extend(await WaitlistRepository(other).claim_batch(500, set()))

    try:
        notifier = _FakeNotifier(on_notify=_claim_from_second_run)
        await _use_case(real_sessions, settings_repository, uow, notifier).system(_DTO)

        assert set(ids) <= set(notifier.calls[0][0])
        assert not set(ids) & set(seen_by_second_run)
    finally:
        async with real_sessions() as cleanup, cleanup.begin():
            await cleanup.execute(delete(User).where(User.id.in_(ids)))


@pytest.mark.parametrize("payments_enabled", [False, True])
async def test_join_adds_the_user_only_while_payments_are_off(
    payments_enabled: bool,
    settings_repository: SettingsRepository,
    waitlist_repository: WaitlistRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        user = await user_repository.create(CreateUserDto(name="j", telegram_id=813_001))
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(payments_enabled=payments_enabled)
        )
    use_case = JoinPaymentWaitlistUseCase(
        GetAccessSettingsUseCase(settings_repository, uow), waitlist_repository, uow
    )
    await use_case(user)
    async with uow:
        assert await waitlist_repository.count() == (0 if payments_enabled else 1)
