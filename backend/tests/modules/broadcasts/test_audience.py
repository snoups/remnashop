from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.ad_link import AdLink
from app.core.db.models.ad_link_attribution import AdLinkAttribution
from app.core.db.models.referral import Referral
from app.core.db.models.user import User
from app.core.enums import (
    BroadcastCategory,
    Locale,
    Role,
    SubscriptionStatus,
)
from app.core.enums import (
    BroadcastSubscriptionFilter as F,
)
from app.core.utils.time import datetime_now
from app.modules.broadcasts.audience import audience_predicate
from app.modules.broadcasts.dto import BroadcastAudienceDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.factories import add_paid_transaction, add_subscription, make_customer


async def _match(
    session: AsyncSession,
    audience: BroadcastAudienceDto,
    category: BroadcastCategory = BroadcastCategory.SERVICE,
) -> set[int]:
    rows = await session.scalars(
        select(User.id).where(audience_predicate(audience, category, datetime_now()))
    )
    return set(rows)


@pytest.fixture
async def people(session: AsyncSession, user_repository: UserRepository) -> dict[str, int]:
    now = datetime_now()
    ids = {
        "active": await make_customer(user_repository, session, telegram_id=7001),
        "trial": await make_customer(
            user_repository, session, telegram_id=7002, language=Locale.RU
        ),
        "expired": await make_customer(user_repository, session, telegram_id=7003),
        "none": await make_customer(user_repository, session, telegram_id=7004),
        "no_tg": await make_customer(user_repository, session, telegram_id=None),
        "blocked": await make_customer(user_repository, session, telegram_id=7005, is_blocked=True),
        "deleted": await make_customer(user_repository, session, telegram_id=7006, deleted_at=now),
        "opted_out": await make_customer(
            user_repository, session, telegram_id=7007, marketing_opt_out=True
        ),
        "admin": await make_customer(user_repository, session, telegram_id=7008, role=Role.ADMIN),
    }
    await add_subscription(session, ids["active"], plan_id=3, expire_at=now + timedelta(days=2))
    await add_subscription(session, ids["trial"], is_trial=True)
    await add_subscription(
        session,
        ids["expired"],
        status=SubscriptionStatus.EXPIRED,
        expire_at=now - timedelta(days=5),
    )
    await add_paid_transaction(session, ids["active"])
    return ids


async def test_everyone_reachable(session: AsyncSession, people: dict[str, int]) -> None:
    found = await _match(session, BroadcastAudienceDto())
    assert found >= {people[k] for k in ("active", "trial", "expired", "none", "opted_out")}
    assert not found & {people[k] for k in ("no_tg", "blocked", "deleted", "admin")}


async def test_marketing_skips_opted_out(session: AsyncSession, people: dict[str, int]) -> None:
    found = await _match(session, BroadcastAudienceDto(), BroadcastCategory.MARKETING)
    assert people["opted_out"] not in found and people["active"] in found


@pytest.mark.parametrize(
    "filters,expected",
    [
        ([F.ACTIVE], {"active"}),
        ([F.TRIAL], {"trial"}),
        ([F.EXPIRED], {"expired"}),
        ([F.ACTIVE, F.TRIAL], {"active", "trial"}),
    ],
)
async def test_subscription_filter(
    session: AsyncSession, people: dict[str, int], filters: list[F], expected: set[str]
) -> None:
    found = await _match(session, BroadcastAudienceDto(subscription=filters))
    assert found & set(people.values()) == {people[k] for k in expected}


async def test_none_means_no_subscription(session: AsyncSession, people: dict[str, int]) -> None:
    found = await _match(session, BroadcastAudienceDto(subscription=[F.NONE]))
    assert (
        people["none"] in found and people["active"] not in found and people["expired"] not in found
    )


async def test_plan_expiry_paid_locale(session: AsyncSession, people: dict[str, int]) -> None:
    mine = set(people.values())
    assert await _match(session, BroadcastAudienceDto(plan_ids=[3])) & mine == {people["active"]}
    assert await _match(session, BroadcastAudienceDto(expires_within_days=3)) & mine == {
        people["active"]
    }
    assert await _match(session, BroadcastAudienceDto(expired_within_days=7)) & mine == {
        people["expired"]
    }
    assert await _match(session, BroadcastAudienceDto(paid=True)) & mine == {people["active"]}
    assert people["active"] not in await _match(session, BroadcastAudienceDto(paid=False))
    assert await _match(session, BroadcastAudienceDto(locales=[Locale.RU])) & mine == {
        people["trial"]
    }


async def test_expired_within_days_skips_customers_who_renewed(
    session: AsyncSession, people: dict[str, int]
) -> None:
    now = datetime_now()
    await add_subscription(session, people["expired"], expire_at=now + timedelta(days=30))
    found = await _match(session, BroadcastAudienceDto(expired_within_days=7))
    assert people["expired"] not in found


async def test_user_ids_override_filters(session: AsyncSession, people: dict[str, int]) -> None:
    audience = BroadcastAudienceDto(user_ids=[people["none"]], subscription=[F.ACTIVE])
    assert await _match(session, audience) == {people["none"]}


async def test_user_ids_still_respect_hard_rules(
    session: AsyncSession, people: dict[str, int]
) -> None:
    assert await _match(session, BroadcastAudienceDto(user_ids=[people["blocked"]])) == set()


async def test_registered_range_and_sources(
    session: AsyncSession, user_repository: UserRepository, people: dict[str, int]
) -> None:
    today = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    found = await _match(session, BroadcastAudienceDto(registered_from=today, registered_to=today))
    assert people["active"] in found

    link = AdLink(name="tg-ads", code="tgads")
    session.add(link)
    await session.flush()
    session.add(AdLinkAttribution(ad_link_id=link.id, user_id=people["trial"]))
    session.add(Referral(referrer_id=people["active"], referred_id=people["none"], level=1))
    await session.flush()
    assert await _match(session, BroadcastAudienceDto(ad_link_ids=[link.id])) == {people["trial"]}
    assert people["none"] in await _match(session, BroadcastAudienceDto(referred=True))
    assert people["none"] not in await _match(session, BroadcastAudienceDto(referred=False))
