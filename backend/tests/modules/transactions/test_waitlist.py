from collections.abc import Awaitable, Callable
from typing import Optional

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.modules.notifications.dto import SendTelegramTextsDto
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import GetAccessSettingsUseCase
from app.modules.transactions.usecases import NotifyPaymentWaitlistUseCase, notify_payment_waitlist
from app.modules.transactions.waitlist_repository import WaitlistClaims, WaitlistRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


class _FakeSender:
    def __init__(
        self,
        fail: frozenset[int] = frozenset(),
        on_send: Optional[Callable[[list[int]], Awaitable[None]]] = None,
        only: Optional[set[int]] = None,
    ) -> None:
        self._fail = fail
        self._on_send = on_send
        self._only = only
        self.calls: list[SendTelegramTextsDto] = []

    @property
    def system(self) -> "_FakeSender":
        return self

    async def __call__(self, data: SendTelegramTextsDto) -> set[int]:
        self.calls.append(data)
        if self._on_send is not None:
            await self._on_send(data.user_ids)
        done = set(data.user_ids) - self._fail
        return done if self._only is None else done & self._only


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
    sender: _FakeSender,
) -> NotifyPaymentWaitlistUseCase:
    return NotifyPaymentWaitlistUseCase(
        WaitlistClaims(session_maker),
        GetAccessSettingsUseCase(settings_repository, uow),
        sender,  # type: ignore[arg-type]
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


async def test_notify_sends_in_batches_and_keeps_failed_users(
    session_maker: async_sessionmaker[AsyncSession],
    settings_repository: SettingsRepository,
    waitlist_repository: WaitlistRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notify_payment_waitlist, "_BATCH_SIZE", 2)
    a, b, c = await _waitlisted(user_repository, uow, waitlist_repository, 3)
    sender = _FakeSender(fail=frozenset({b}))

    await _use_case(session_maker, settings_repository, uow, sender).system()

    assert sender.calls[0].key == "ntf-access.payments-restored"
    assert [call.user_ids for call in sender.calls] == [[a, b], [c]]
    async with uow:
        assert await waitlist_repository.claim_batch(100, set()) == [b]


async def test_notify_with_empty_waitlist_sends_nothing(
    session_maker: async_sessionmaker[AsyncSession],
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    sender = _FakeSender()
    await _use_case(session_maker, settings_repository, uow, sender).system()
    assert sender.calls == []


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
    sender = _FakeSender()

    await _use_case(session_maker, settings_repository, uow, sender).system()

    assert sender.calls == []
    async with uow:
        assert await waitlist_repository.claim_batch(100, set()) == ids


async def test_a_batch_with_nobody_done_ends_the_run(
    session_maker: async_sessionmaker[AsyncSession],
    settings_repository: SettingsRepository,
    waitlist_repository: WaitlistRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # no bot, missing translation or Telegram down: retrying further batches won't help
    monkeypatch.setattr(notify_payment_waitlist, "_BATCH_SIZE", 2)
    ids = await _waitlisted(user_repository, uow, waitlist_repository, 3)
    sender = _FakeSender(fail=frozenset(ids))

    await _use_case(session_maker, settings_repository, uow, sender).system()

    assert len(sender.calls) == 1
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
        sender = _FakeSender(on_send=_claim_from_second_run, only=set(ids))
        await _use_case(real_sessions, settings_repository, uow, sender).system()

        assert set(ids) <= set(sender.calls[0].user_ids)
        assert not set(ids) & set(seen_by_second_run)
    finally:
        async with real_sessions() as cleanup, cleanup.begin():
            await cleanup.execute(delete(User).where(User.id.in_(ids)))
