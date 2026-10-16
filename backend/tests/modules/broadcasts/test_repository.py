from datetime import timedelta
from typing import Final

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.broadcast import Broadcast, BroadcastRecipient
from app.core.db.models.user import User
from app.core.enums import (
    BroadcastCategory,
    BroadcastChannel,
    BroadcastDelivery,
    BroadcastStatus,
    Locale,
    Role,
)
from app.core.enums import (
    BroadcastRecipientStatus as R,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastContentDto,
    BroadcastEmailContentDto,
    ListBroadcastRecipientsDto,
    ListBroadcastsDto,
    SaveBroadcastDto,
)
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.factories import add_subscription, make_customer

_LEASE: Final[timedelta] = timedelta(minutes=5)


def save_dto(**overrides: object) -> SaveBroadcastDto:
    values: dict[str, object] = {
        "category": BroadcastCategory.SERVICE,
        "audience": BroadcastAudienceDto(),
        "default_locale": Locale.EN,
        "contents": {Locale.EN: BroadcastContentDto(text="Hi { $name }")},
        "buttons": [],
        "promocode_id": None,
        "post_to_channel": False,
    }
    values.update(overrides)
    return SaveBroadcastDto(**values)  # type: ignore[arg-type]


async def test_create_roundtrips_json(broadcast_repository: BroadcastRepository) -> None:
    created = await broadcast_repository.create(save_dto(), created_by=None)
    loaded = await broadcast_repository.find_by_id(created.id)
    assert loaded is not None
    assert loaded.status is BroadcastStatus.DRAFT
    assert loaded.contents[Locale.EN].text == "Hi { $name }"


async def test_replace_resets_to_draft(broadcast_repository: BroadcastRepository) -> None:
    created = await broadcast_repository.create(save_dto(), created_by=None)
    await broadcast_repository.update_fields(
        created.id, status=BroadcastStatus.SCHEDULED, scheduled_at=datetime_now()
    )
    replaced = await broadcast_repository.replace(
        created.id, save_dto(contents={Locale.EN: BroadcastContentDto(text="New")})
    )
    assert replaced.status is BroadcastStatus.DRAFT
    assert replaced.scheduled_at is None
    assert replaced.contents[Locale.EN].text == "New"


async def test_list_newest_first(broadcast_repository: BroadcastRepository) -> None:
    first = await broadcast_repository.create(save_dto(), created_by=None)
    second = await broadcast_repository.create(save_dto(), created_by=None)
    items, total = await broadcast_repository.list(ListBroadcastsDto())
    assert total == 2
    assert [item.id for item in items] == [second.id, first.id]


async def test_materialize_is_idempotent_and_claims_in_order(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    a = await make_customer(user_repository, session, telegram_id=8101)
    b = await make_customer(user_repository, session, telegram_id=8102)
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=[a, b])), created_by=None
    )
    now = datetime_now()
    assert (
        await broadcast_repository.materialize(
            created.id, created.audience, created.category, BroadcastDelivery.TELEGRAM, False, now
        )
        == 2
    )
    assert (
        await broadcast_repository.materialize(
            created.id, created.audience, created.category, BroadcastDelivery.TELEGRAM, False, now
        )
        == 2
    )
    claimed = await broadcast_repository.claim_pending(created.id, 10, _LEASE, marketing=False)
    assert [r.user_id for r in claimed] == [a, b]
    assert claimed[0].telegram_id == 8101


async def test_claim_pending_fails_unreachable_recipients(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    a = await make_customer(user_repository, session, telegram_id=8111)
    b = await make_customer(user_repository, session, telegram_id=8112)
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=[a, b])), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    await session.execute(update(User).where(User.id == a).values(telegram_id=None))
    claimed = await broadcast_repository.claim_pending(created.id, 10, _LEASE, marketing=False)
    assert [r.user_id for r in claimed] == [b]
    failed, total = await broadcast_repository.list_recipients(
        ListBroadcastRecipientsDto(broadcast_id=created.id, status=R.FAILED)
    )
    assert total == 1 and failed[0].user_id == a and failed[0].error == "no telegram"


@pytest.mark.parametrize(
    ("marketing", "canceled"),
    [(True, {"a": "opted out", "b": "blocked"}), (False, {"b": "blocked"})],
)
async def test_claim_pending_cancels_opted_out_and_blocked(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    marketing: bool,
    canceled: dict[str, str],
) -> None:
    ids = {
        name: await make_customer(user_repository, session, telegram_id=8121 + i)
        for i, name in enumerate("abc")
    }
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=list(ids.values()))), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    await session.execute(update(User).where(User.id == ids["a"]).values(marketing_opt_out=True))
    await session.execute(update(User).where(User.id == ids["b"]).values(is_blocked=True))
    claimed = await broadcast_repository.claim_pending(created.id, 10, _LEASE, marketing=marketing)
    names = {v: k for k, v in ids.items()}
    assert {names[r.user_id] for r in claimed} == {"a", "b", "c"} - canceled.keys()
    rows, _ = await broadcast_repository.list_recipients(
        ListBroadcastRecipientsDto(broadcast_id=created.id, status=R.CANCELED)
    )
    assert {names[r.user_id]: r.error for r in rows} == canceled


async def test_counts_and_attempts(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    ids = [await make_customer(user_repository, session, telegram_id=8200 + i) for i in range(3)]
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=ids)), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    first, second, third = await broadcast_repository.claim_pending(
        created.id, 10, _LEASE, marketing=False
    )
    await broadcast_repository.mark_recipient(first.id, R.SENT, message_id=11)
    await broadcast_repository.mark_recipient(second.id, R.BLOCKED)
    for _ in range(3):
        await broadcast_repository.bump_attempt(third.id, max_attempts=3, error="timeout")
    refreshed = await broadcast_repository.refresh_counts(created.id)
    assert (refreshed.sent_count, refreshed.blocked_count, refreshed.failed_count) == (1, 1, 1)
    assert not await broadcast_repository.has_pending(created.id)
    recallable = await broadcast_repository.list_recallable(created.id, 10)
    assert [(r.telegram_id, r.telegram_message_id) for r in recallable] == [(8200, 11)]
    assert await broadcast_repository.reset_failed(created.id) == 1
    assert await broadcast_repository.has_pending(created.id)


async def test_recipient_context_uses_live_subscription(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    user_id = await make_customer(user_repository, session, telegram_id=8301, bonus_days=4)
    await add_subscription(
        session, user_id, plan_name="Pro", expire_at=datetime_now() + timedelta(days=10)
    )
    context = (await broadcast_repository.recipient_contexts([user_id]))[user_id]
    assert context.plan_name == "Pro" and context.bonus_days == 4 and context.expire_at is not None


async def test_scheduling_queries(broadcast_repository: BroadcastRepository) -> None:
    now = datetime_now()
    due = await broadcast_repository.create(save_dto(), created_by=None)
    later = await broadcast_repository.create(save_dto(), created_by=None)
    await broadcast_repository.update_fields(
        due.id, status=BroadcastStatus.SCHEDULED, scheduled_at=now - timedelta(minutes=1)
    )
    await broadcast_repository.update_fields(
        later.id, status=BroadcastStatus.SCHEDULED, scheduled_at=now + timedelta(hours=1)
    )
    assert await broadcast_repository.next_due(now) == due.id
    assert not await broadcast_repository.has_sending()


async def test_refresh_counts_reads_fresh_status(
    broadcast_repository: BroadcastRepository, session: AsyncSession
) -> None:
    created = await broadcast_repository.create(save_dto(), created_by=None)
    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == created.id)
        .values(status=BroadcastStatus.CANCELED)
        .execution_options(synchronize_session=False)
    )
    assert (
        await broadcast_repository.refresh_counts(created.id)
    ).status is BroadcastStatus.CANCELED


async def test_recall_keeps_send_history(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    user_id = await make_customer(user_repository, session, telegram_id=8401)
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=[user_id])), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    (pending,) = await broadcast_repository.claim_pending(created.id, 10, _LEASE, marketing=False)
    await broadcast_repository.mark_recipient(pending.id, R.SENT, message_id=11)
    await broadcast_repository.mark_recipient(pending.id, R.RECALLED)
    row = (
        await session.execute(
            select(BroadcastRecipient)
            .where(BroadcastRecipient.id == pending.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert row.status is R.RECALLED and row.telegram_message_id == 11 and row.sent_at is not None


async def test_lock_for_update_returns_fresh_state_and_raises_for_missing(
    session: AsyncSession, broadcast_repository: BroadcastRepository
) -> None:
    created = await broadcast_repository.create(save_dto(), created_by=None)
    await session.execute(
        update(Broadcast).where(Broadcast.id == created.id).values(status=BroadcastStatus.SENDING)
    )
    locked = await broadcast_repository.get_by_id_for_update(created.id)
    assert locked.status is BroadcastStatus.SENDING
    with pytest.raises(NotFoundError) as error:
        await broadcast_repository.get_by_id_for_update(999_999)
    assert error.value.code is ErrorCode.BROADCAST_NOT_FOUND


async def test_claim_pending_leases_rows(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    ids = [await make_customer(user_repository, session, telegram_id=8500 + i) for i in range(3)]
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=ids)), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    first = await broadcast_repository.claim_pending(created.id, 2, _LEASE, marketing=False)
    second = await broadcast_repository.claim_pending(created.id, 2, _LEASE, marketing=False)
    assert [r.user_id for r in first] == ids[:2]
    assert [r.user_id for r in second] == ids[2:]
    assert await broadcast_repository.claim_pending(created.id, 2, _LEASE, marketing=False) == []

    await session.execute(
        update(BroadcastRecipient)
        .where(BroadcastRecipient.id == first[0].id)
        .values(claimed_until=datetime_now() - timedelta(seconds=1))
    )
    again = await broadcast_repository.claim_pending(created.id, 2, _LEASE, marketing=False)
    assert [r.id for r in again] == [first[0].id]


async def test_bump_attempt_releases_lease_and_keeps_cancel(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    ids = [await make_customer(user_repository, session, telegram_id=8510 + i) for i in range(2)]
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=ids)), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    retried, canceled = await broadcast_repository.claim_pending(
        created.id, 10, _LEASE, marketing=False
    )
    await broadcast_repository.mark_recipient(canceled.id, R.CANCELED)

    await broadcast_repository.bump_attempt(retried.id, max_attempts=3, error="timeout")
    await broadcast_repository.bump_attempt(canceled.id, max_attempts=3, error="timeout")

    rows = {
        row.id: row
        for row in await session.scalars(
            select(BroadcastRecipient)
            .where(BroadcastRecipient.broadcast_id == created.id)
            .execution_options(populate_existing=True)
        )
    }
    assert (rows[canceled.id].status, rows[canceled.id].attempts) == (R.CANCELED, 0)
    assert (rows[retried.id].status, rows[retried.id].attempts) == (R.PENDING, 1)
    assert [
        r.id
        for r in await broadcast_repository.claim_pending(created.id, 10, _LEASE, marketing=False)
    ] == [retried.id]


async def test_sent_clears_stale_error(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    user_id = await make_customer(user_repository, session, telegram_id=8410)
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=[user_id])), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    (pending,) = await broadcast_repository.claim_pending(created.id, 10, _LEASE, marketing=False)
    await broadcast_repository.bump_attempt(pending.id, max_attempts=3, error="timeout")
    await broadcast_repository.mark_recipient(pending.id, R.SENT, message_id=11)
    row = (
        await session.execute(
            select(BroadcastRecipient)
            .where(BroadcastRecipient.id == pending.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert row.status is R.SENT and row.error is None


async def test_list_search_matches_title_and_text_and_escapes(
    broadcast_repository: BroadcastRepository,
) -> None:
    by_title = await broadcast_repository.create(save_dto(title="Spring sale"), created_by=None)
    by_text = await broadcast_repository.create(
        save_dto(contents={Locale.EN: BroadcastContentDto(text="Big DISCOUNT 50%")}),
        created_by=None,
    )
    await broadcast_repository.create(save_dto(), created_by=None)
    found, _ = await broadcast_repository.list(ListBroadcastsDto(search="spring"))
    assert [b.id for b in found] == [by_title.id]
    found, _ = await broadcast_repository.list(ListBroadcastsDto(search="discount"))
    assert [b.id for b in found] == [by_text.id]
    found, _ = await broadcast_repository.list(ListBroadcastsDto(search="%"))
    assert [b.id for b in found] == [by_text.id]
    found, _ = await broadcast_repository.list(ListBroadcastsDto(search="_"))
    assert found == []


async def test_list_filters_by_several_statuses(broadcast_repository: BroadcastRepository) -> None:
    draft = await broadcast_repository.create(save_dto(), created_by=None)
    failed = await broadcast_repository.create(save_dto(), created_by=None)
    done = await broadcast_repository.create(save_dto(), created_by=None)
    await broadcast_repository.update_fields(failed.id, status=BroadcastStatus.FAILED)
    await broadcast_repository.update_fields(done.id, status=BroadcastStatus.COMPLETED)
    found, total = await broadcast_repository.list(
        ListBroadcastsDto(statuses=[BroadcastStatus.DRAFT, BroadcastStatus.FAILED])
    )
    assert total == 2
    assert {b.id for b in found} == {draft.id, failed.id}


async def test_title_is_stripped_and_blank_becomes_none(
    broadcast_repository: BroadcastRepository,
) -> None:
    padded = await broadcast_repository.create(save_dto(title="  Hello  "), created_by=None)
    blank = await broadcast_repository.create(save_dto(title="   "), created_by=None)
    assert padded.title == "Hello"
    assert blank.title is None


async def test_creator_name_prefers_login(
    user_repository: UserRepository, broadcast_repository: BroadcastRepository
) -> None:
    creator = await user_repository.create(
        CreateUserDto(name="Display", role=Role.ADMIN, login="bc-creator")
    )
    created = await broadcast_repository.create(save_dto(), created_by=creator.id)
    fetched = await broadcast_repository.get_by_id(created.id)
    assert fetched.created_by_name == "bc-creator"
    items, _ = await broadcast_repository.list(ListBroadcastsDto())
    assert items[0].created_by_name == "bc-creator"


async def test_recipients_carry_user_fields(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    a = await make_customer(
        user_repository, session, telegram_id=8301, language=Locale.RU, username="alice"
    )
    created = await broadcast_repository.create(
        save_dto(audience=BroadcastAudienceDto(user_ids=[a])), created_by=None
    )
    await broadcast_repository.materialize(
        created.id,
        created.audience,
        created.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    items, total = await broadcast_repository.list_recipients(
        ListBroadcastRecipientsDto(broadcast_id=created.id)
    )
    assert total == 1
    assert (items[0].user_name, items[0].username) == ("c8301", "alice")
    assert (items[0].telegram_id, items[0].language) == (8301, Locale.RU)


async def test_summary_counts_window_and_audience(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    now = datetime_now()
    reachable = await make_customer(user_repository, session, telegram_id=8401)
    opted = await make_customer(user_repository, session, telegram_id=8402, marketing_opt_out=True)
    await make_customer(user_repository, session, telegram_id=None)
    await make_customer(
        user_repository,
        session,
        telegram_id=None,
        email="opted@example.com",
        marketing_opt_out=True,
    )
    await make_customer(
        user_repository,
        session,
        telegram_id=None,
        email="bad@example.com",
        email_undeliverable_at=now,
        marketing_opt_out=True,
    )
    await make_customer(user_repository, session, telegram_id=8403, is_blocked=True)
    await make_customer(
        user_repository, session, telegram_id=8404, is_blocked=True, marketing_opt_out=True
    )
    ids = [await make_customer(user_repository, session, telegram_id=8410 + i) for i in range(3)]
    recent = await broadcast_repository.create(save_dto(), created_by=None)
    old = await broadcast_repository.create(save_dto(), created_by=None)
    scheduled = await broadcast_repository.create(save_dto(), created_by=None)
    await broadcast_repository.update_fields(
        recent.id, status=BroadcastStatus.COMPLETED, started_at=now - timedelta(days=2)
    )
    await broadcast_repository.update_fields(
        old.id, status=BroadcastStatus.COMPLETED, started_at=now - timedelta(days=40)
    )
    await broadcast_repository.update_fields(
        scheduled.id, status=BroadcastStatus.SCHEDULED, scheduled_at=now + timedelta(days=1)
    )
    session.add_all(
        [
            BroadcastRecipient(
                broadcast_id=recent.id,
                user_id=ids[0],
                status=R.SENT,
            ),
            BroadcastRecipient(broadcast_id=recent.id, user_id=ids[1], status=R.FAILED),
            BroadcastRecipient(broadcast_id=recent.id, user_id=ids[2], status=R.PENDING),
            BroadcastRecipient(
                broadcast_id=old.id, user_id=ids[0], status=R.SENT, sent_at=now - timedelta(days=40)
            ),
        ]
    )
    await session.flush()
    summary = await broadcast_repository.summary(now)
    assert summary.by_status[BroadcastStatus.COMPLETED] == 2
    assert summary.by_status[BroadcastStatus.SCHEDULED] == 1
    assert summary.by_status[BroadcastStatus.DRAFT] == 0
    assert (
        summary.next_scheduled_at
        == (await broadcast_repository.get_by_id(scheduled.id)).scheduled_at
    )
    assert summary.delivered_30d == 1
    assert summary.processed_30d == 2
    assert summary.opted_out == 2
    assert summary.reachable_customers == 1 + 1 + 3 + 1
    assert reachable and opted


async def test_email_content_roundtrips(broadcast_repository: BroadcastRepository) -> None:
    created = await broadcast_repository.create(
        save_dto(
            delivery=BroadcastDelivery.ALL,
            email_contents={Locale.EN: BroadcastEmailContentDto(subject="S", html="<p>b</p>")},
        ),
        created_by=None,
    )
    loaded = await broadcast_repository.get_by_id(created.id)
    assert loaded.delivery is BroadcastDelivery.ALL
    assert loaded.email_contents[Locale.EN].subject == "S"
    assert loaded.sends_email and loaded.sends_telegram


async def _five_customers(session: AsyncSession, user_repository: UserRepository) -> dict[str, int]:
    return {
        "tg": await make_customer(user_repository, session, telegram_id=9900),
        "both": await make_customer(
            user_repository, session, telegram_id=9901, email="both@x.example"
        ),
        "mail": await make_customer(
            user_repository, session, telegram_id=None, email="mail@x.example"
        ),
        "dead": await make_customer(
            user_repository,
            session,
            telegram_id=None,
            email="dead@x.example",
            email_undeliverable_at=datetime_now(),
        ),
        "none": await make_customer(user_repository, session, telegram_id=None),
    }


@pytest.mark.parametrize(
    ("delivery", "fallback", "expected"),
    [
        (BroadcastDelivery.TELEGRAM, False, {("tg", "TELEGRAM"), ("both", "TELEGRAM")}),
        (
            BroadcastDelivery.TELEGRAM,
            True,
            {("tg", "TELEGRAM"), ("both", "TELEGRAM"), ("mail", "EMAIL")},
        ),
        (BroadcastDelivery.EMAIL, False, {("mail", "EMAIL"), ("both", "EMAIL")}),
        (
            BroadcastDelivery.ALL,
            False,
            {("tg", "TELEGRAM"), ("both", "TELEGRAM"), ("both", "EMAIL"), ("mail", "EMAIL")},
        ),
    ],
)
async def test_materialize_rows_per_mode(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    delivery: BroadcastDelivery,
    fallback: bool,
    expected: set[tuple[str, str]],
) -> None:
    ids = await _five_customers(session, user_repository)
    names = {v: k for k, v in ids.items()}
    created = await broadcast_repository.create(save_dto(), created_by=None)
    total = await broadcast_repository.materialize(
        created.id,
        BroadcastAudienceDto(user_ids=list(ids.values())),
        BroadcastCategory.SERVICE,
        delivery,
        fallback,
        datetime_now(),
    )
    rows = await session.execute(
        select(BroadcastRecipient.user_id, BroadcastRecipient.channel).where(
            BroadcastRecipient.broadcast_id == created.id
        )
    )
    got = {(names[u], c.value) for u, c in rows.tuples()}
    assert got == expected
    assert total == len(expected)


async def test_marketing_skips_opted_out_on_email(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    opted_out = await make_customer(
        user_repository, session, telegram_id=None, email="out@x.example", marketing_opt_out=True
    )
    subscribed = await make_customer(
        user_repository, session, telegram_id=None, email="in@x.example"
    )
    created = await broadcast_repository.create(save_dto(), created_by=None)
    total = await broadcast_repository.materialize(
        created.id,
        BroadcastAudienceDto(user_ids=[opted_out, subscribed]),
        BroadcastCategory.MARKETING,
        BroadcastDelivery.EMAIL,
        False,
        datetime_now(),
    )
    users = await session.scalars(
        select(BroadcastRecipient.user_id).where(BroadcastRecipient.broadcast_id == created.id)
    )
    assert list(users) == [subscribed]
    assert total == 1


async def test_count_audience_by_channel(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    ids = await _five_customers(session, user_repository)
    audience = BroadcastAudienceDto(user_ids=list(ids.values()))
    preview = await broadcast_repository.count_audience(
        audience, BroadcastCategory.SERVICE, BroadcastDelivery.ALL, False, datetime_now()
    )
    assert preview.by_channel == {BroadcastChannel.TELEGRAM: 2, BroadcastChannel.EMAIL: 2}
    assert preview.total == 3
    assert preview.by_locale == {Locale.EN: 3}

    telegram_only = await broadcast_repository.count_audience(
        audience, BroadcastCategory.SERVICE, BroadcastDelivery.TELEGRAM, False, datetime_now()
    )
    assert telegram_only.by_channel == {BroadcastChannel.TELEGRAM: 2}
    assert telegram_only.total == 2


async def test_claim_and_list_split_by_channel(
    session: AsyncSession,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
) -> None:
    both = await make_customer(user_repository, session, telegram_id=9910, email="c@x.example")
    created = await broadcast_repository.create(save_dto(), created_by=None)
    await broadcast_repository.materialize(
        created.id,
        BroadcastAudienceDto(user_ids=[both]),
        BroadcastCategory.SERVICE,
        BroadcastDelivery.ALL,
        False,
        datetime_now(),
    )
    await session.execute(update(User).where(User.id == both).values(telegram_id=None))
    assert await broadcast_repository.claim_pending(created.id, 10, _LEASE, marketing=False) == []
    emails, total = await broadcast_repository.list_recipients(
        ListBroadcastRecipientsDto(broadcast_id=created.id, channel=BroadcastChannel.EMAIL)
    )
    assert total == 1
    assert (emails[0].status, emails[0].email) == (R.PENDING, "c@x.example")
    telegrams, _ = await broadcast_repository.list_recipients(
        ListBroadcastRecipientsDto(broadcast_id=created.id, channel=BroadcastChannel.TELEGRAM)
    )
    assert (telegrams[0].status, telegrams[0].error) == (R.FAILED, "no telegram")
