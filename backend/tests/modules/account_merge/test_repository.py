from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import BaseSql
from app.core.db.models import (
    AdLink,
    AdLinkAttribution,
    Announcement,
    AnnouncementView,
    Broadcast,
    BroadcastRecipient,
    CustomerNotification,
    LegalAcceptance,
    LegalDocumentRevision,
    OAuthIdentity,
    PasskeyCredential,
    PaymentWaitlistEntry,
    Promocode,
    Referral,
    Transaction,
)
from app.core.enums import (
    BroadcastCategory,
    BroadcastChannel,
    BroadcastRecipientStatus,
    BroadcastStatus,
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    Locale,
    OAuthProvider,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseChannel,
)
from app.modules.account_merge.repository import (
    REASSIGNED_USER_FKS,
    UNTOUCHED_USER_FKS,
    AccountMergeRepository,
)
from app.modules.account_merge.rules import merged_user_fields
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.loyalty.factories import paid_order


@pytest.fixture
def merge_repository(session: AsyncSession) -> AccountMergeRepository:
    return AccountMergeRepository(session)


def test_every_user_fk_is_classified() -> None:
    fks = {
        (fk.parent.table.name, fk.parent.name)
        for table in BaseSql.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.column.table.name == "users"
    }

    assert fks == REASSIGNED_USER_FKS | UNTOUCHED_USER_FKS


async def test_reassign_drops_mutual_referral(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    invited = await user_repository.create(CreateUserDto(name="i"))
    session.add_all(
        [
            Referral(referrer_id=target.id, referred_id=source.id, level=1),
            Referral(referrer_id=source.id, referred_id=invited.id, level=1),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    rows = (await session.scalars(select(Referral))).all()
    assert [(r.referrer_id, r.referred_id) for r in rows] == [(target.id, invited.id)]


async def test_reassign_resolves_referred_by_choice(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source, target, a, b = [
        await user_repository.create(CreateUserDto(name=n)) for n in ("s", "t", "a", "b")
    ]
    session.add_all(
        [
            Referral(referrer_id=a.id, referred_id=source.id, level=1),
            Referral(referrer_id=b.id, referred_id=target.id, level=1),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {"referred_by": "source"})

    [row] = (await session.scalars(select(Referral))).all()
    assert (row.referrer_id, row.referred_id) == (a.id, target.id)


async def test_reassign_oauth_collision_keeps_chosen_side(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    session.add_all(
        [
            OAuthIdentity(user_id=source.id, provider=OAuthProvider.GITHUB, external_id="s-gh"),
            OAuthIdentity(user_id=target.id, provider=OAuthProvider.GITHUB, external_id="t-gh"),
            OAuthIdentity(user_id=source.id, provider=OAuthProvider.OIDC, external_id="s-oidc"),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {"oauth:GITHUB": "source"})

    rows = (await session.scalars(select(OAuthIdentity))).all()
    assert {(r.user_id, r.external_id) for r in rows} == {
        (target.id, "s-gh"),
        (target.id, "s-oidc"),
    }


async def test_reassign_drops_credentials_of_given_user(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    session.add_all(
        [
            OAuthIdentity(user_id=source.id, provider=OAuthProvider.GITHUB, external_id="s-gh"),
            OAuthIdentity(user_id=target.id, provider=OAuthProvider.GITHUB, external_id="t-gh"),
            PasskeyCredential(
                user_id=source.id,
                credential_id="merge-src-pk",
                public_key=b"k",
                sign_count=0,
                device_type="single_device",
                backed_up=False,
            ),
        ]
    )
    await session.flush()

    await merge_repository.reassign(
        source.id, target.id, {"oauth:GITHUB": "source"}, drop_credentials_of=source.id
    )

    identities = (await session.scalars(select(OAuthIdentity))).all()
    assert {(r.user_id, r.external_id) for r in identities} == {(target.id, "t-gh")}
    assert (await session.scalars(select(PasskeyCredential))).all() == []


async def test_reassign_keeps_earliest_attribution_and_waitlist(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    link = AdLink(code="mergeadl", name="l")
    session.add(link)
    await session.flush()
    early = datetime.now(timezone.utc) - timedelta(days=3)
    session.add_all(
        [
            AdLinkAttribution(ad_link_id=link.id, user_id=source.id, created_at=early),
            AdLinkAttribution(ad_link_id=link.id, user_id=target.id),
            PaymentWaitlistEntry(user_id=source.id, created_at=early),
            PaymentWaitlistEntry(user_id=target.id),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    [attribution] = (await session.scalars(select(AdLinkAttribution))).all()
    assert attribution.user_id == target.id and attribution.created_at == early
    [entry] = (await session.scalars(select(PaymentWaitlistEntry))).all()
    assert entry.user_id == target.id and entry.created_at == early


async def test_merge_moves_source_telegram_to_target(
    user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s", telegram_id=900))
    target = await user_repository.create(CreateUserDto(name="t"))

    merged_fields = merged_user_fields(source, target, {})
    await user_repository.anonymize(source.id)
    await merge_repository.write_target(target.id, merged_fields)

    merged = await user_repository.find_by_id(target.id)
    assert merged is not None and merged.telegram_id == 900


async def test_reassign_dedups_promocode_allowlists(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))

    def promocode(code: str, ids: list[int]) -> Promocode:
        return Promocode(
            code=code,
            reward_type=PromocodeRewardType.DURATION,
            availability=PromocodeAvailability.ALLOWED,
            allowed_user_ids=ids,
        )

    touched = promocode("mergeallow1", [source.id, 999001, target.id])
    untouched = promocode("mergeallow2", [999001, target.id])
    session.add_all([touched, untouched])
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    assert touched.allowed_user_ids == [target.id, 999001]
    assert untouched.allowed_user_ids == [999001, target.id]


async def test_reassign_dedups_broadcast_recipients(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    shared, solo = [
        Broadcast(
            status=BroadcastStatus.COMPLETED,
            category=BroadcastCategory.SERVICE,
            audience={},
            default_locale=Locale.EN,
            contents={},
            buttons=[],
        )
        for _ in range(2)
    ]
    session.add_all([shared, solo])
    await session.flush()
    status = BroadcastRecipientStatus.SENT
    session.add_all(
        [
            BroadcastRecipient(broadcast_id=shared.id, user_id=source.id, status=status),
            BroadcastRecipient(broadcast_id=shared.id, user_id=target.id, status=status),
            BroadcastRecipient(broadcast_id=solo.id, user_id=source.id, status=status),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    rows = (await session.scalars(select(BroadcastRecipient))).all()
    assert sorted((r.broadcast_id, r.user_id) for r in rows) == sorted(
        [(shared.id, target.id), (solo.id, target.id)]
    )


async def test_reassign_keeps_recipient_rows_of_other_channels(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    broadcast = Broadcast(
        status=BroadcastStatus.COMPLETED,
        category=BroadcastCategory.SERVICE,
        audience={},
        default_locale=Locale.EN,
        contents={},
        buttons=[],
    )
    session.add(broadcast)
    await session.flush()
    status = BroadcastRecipientStatus.SENT
    session.add_all(
        [
            BroadcastRecipient(
                broadcast_id=broadcast.id,
                user_id=source.id,
                status=status,
                channel=BroadcastChannel.EMAIL,
            ),
            BroadcastRecipient(
                broadcast_id=broadcast.id,
                user_id=target.id,
                status=status,
                channel=BroadcastChannel.TELEGRAM,
            ),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    rows = (await session.scalars(select(BroadcastRecipient))).all()
    assert sorted((r.user_id, r.channel) for r in rows) == [
        (target.id, BroadcastChannel.EMAIL),
        (target.id, BroadcastChannel.TELEGRAM),
    ]


async def test_reassign_dedups_announcement_views(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    now = datetime.now(timezone.utc)
    shared, solo = [
        Announcement(id=name, notify_at=now, auto_open=False, content={})
        for name in ("merge-ann-shared", "merge-ann-solo")
    ]
    session.add_all([shared, solo])
    await session.flush()
    session.add_all(
        [
            AnnouncementView(user_id=source.id, announcement_id=shared.id, seen_at=now),
            AnnouncementView(user_id=target.id, announcement_id=shared.id, seen_at=now),
            AnnouncementView(user_id=source.id, announcement_id=solo.id, seen_at=now),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    rows = (await session.scalars(select(AnnouncementView))).all()
    assert sorted((r.announcement_id, r.user_id) for r in rows) == [
        ("merge-ann-shared", target.id),
        ("merge-ann-solo", target.id),
    ]


async def test_reassign_default_sides_keep_target(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source, target, a, b = [
        await user_repository.create(CreateUserDto(name=n)) for n in ("s", "t", "a", "b")
    ]
    session.add_all(
        [
            OAuthIdentity(user_id=source.id, provider=OAuthProvider.GITHUB, external_id="s-gh"),
            OAuthIdentity(user_id=target.id, provider=OAuthProvider.GITHUB, external_id="t-gh"),
            Referral(referrer_id=a.id, referred_id=source.id, level=1),
            Referral(referrer_id=b.id, referred_id=target.id, level=1),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    [identity] = (await session.scalars(select(OAuthIdentity))).all()
    assert (identity.user_id, identity.external_id) == (target.id, "t-gh")
    [referral] = (await session.scalars(select(Referral))).all()
    assert (referral.referrer_id, referral.referred_id) == (b.id, target.id)


async def test_reassign_breaks_a_referral_cycle_through_the_target(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source, target, middle = [
        await user_repository.create(CreateUserDto(name=n)) for n in ("s", "t", "x")
    ]
    # target -> middle -> source; merged, source's referrer becomes target's
    session.add_all(
        [
            Referral(referrer_id=target.id, referred_id=middle.id, level=1),
            Referral(referrer_id=middle.id, referred_id=source.id, level=1),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    parents = {
        r.referred_id: r.referrer_id for r in (await session.scalars(select(Referral))).all()
    }
    current, seen = target.id, set()
    while current in parents:
        assert current not in seen
        seen.add(current)
        current = parents[current]
    assert parents == {middle.id: target.id}


async def test_reassign_keeps_a_real_referrer_over_a_deleted_one(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source, target, referrer = [
        await user_repository.create(CreateUserDto(name=n)) for n in ("s", "t", "r")
    ]
    # target's inviter was deleted: its row stays with referrer_id NULL
    session.add_all(
        [
            Referral(referrer_id=None, referred_id=target.id, level=1),
            Referral(referrer_id=referrer.id, referred_id=source.id, level=1),
        ]
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    [referral] = (await session.scalars(select(Referral))).all()
    assert (referral.referrer_id, referral.referred_id) == (referrer.id, target.id)


async def test_reassign_keeps_a_moved_order_paid_at_its_own_time(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    invited = await user_repository.create(CreateUserDto(name="i"))
    order_id = await paid_order(session, source.id, "10", days_ago=30)
    session.add(Referral(referrer_id=source.id, referred_id=invited.id, level=1))
    await session.flush()
    paid_at = await session.scalar(select(Transaction.updated_at).where(Transaction.id == order_id))
    referred_at = await session.scalar(
        select(Referral.updated_at).where(Referral.referred_id == invited.id)
    )

    await merge_repository.reassign(source.id, target.id, {})

    session.expire_all()
    order = await session.get_one(Transaction, order_id)
    referral = await session.scalar(select(Referral).where(Referral.referred_id == invited.id))
    assert order.user_id == target.id
    # updated_at of a paid order is when it was paid; revenue and loyalty read it
    assert order.updated_at == paid_at
    assert referral is not None
    assert referral.referrer_id == target.id
    assert referral.updated_at == referred_at


async def test_merge_moves_legal_acceptances(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    revision = LegalDocumentRevision(
        kind=LegalDocumentKind.OFFER, locale=Locale.EN, title="Offer", body="text"
    )
    session.add(revision)
    await session.flush()
    session.add(
        LegalAcceptance(
            user_id=source.id,
            revision_id=revision.id,
            channel=PurchaseChannel.BOT,
            trigger=LegalAcceptanceTrigger.SIGN_UP,
        )
    )
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    session.expire_all()
    [acceptance] = (await session.scalars(select(LegalAcceptance))).all()
    assert acceptance.user_id == target.id


async def test_reassign_moves_customer_notifications_dedup_by_outbox(
    session: AsyncSession, user_repository: UserRepository, merge_repository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))

    def row(user_id: int, outbox_id: int) -> CustomerNotification:
        return CustomerNotification(user_id=user_id, outbox_id=outbox_id, event_type="e", args={})

    session.add_all([row(source.id, 1), row(source.id, 2), row(target.id, 1)])
    await session.flush()

    await merge_repository.reassign(source.id, target.id, {})

    rows = (await session.scalars(select(CustomerNotification))).all()
    assert sorted((r.user_id, r.outbox_id) for r in rows) == [(target.id, 1), (target.id, 2)]
