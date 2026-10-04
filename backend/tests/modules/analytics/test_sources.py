from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdLinkChannel
from app.modules.advertising.dto import CreateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.analytics.sources import SourceKind, resolve_sources
from app.modules.referrals.repository import ReferralRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_resolve_sources_ranks_ad_link_over_referral_over_organic(
    user_repository: UserRepository, session: AsyncSession
) -> None:
    ad_links = AdLinkRepository(session)
    referrals = ReferralRepository(session)
    a = (await user_repository.create(CreateUserDto(name="A", telegram_id=829_001))).id
    b = (await user_repository.create(CreateUserDto(name="B", telegram_id=829_002))).id
    c = (await user_repository.create(CreateUserDto(name="C", telegram_id=829_003))).id
    d = (await user_repository.create(CreateUserDto(name="D", telegram_id=829_004))).id
    link = await ad_links.create(CreateAdLinkDto(name="Blogger", code="blogger-src"))
    await ad_links.create_attribution(ad_link_id=link.id, user_id=a, channel=AdLinkChannel.BOT)
    await referrals.create_referral(referrer_id=b, referred_id=a, level=1)
    await referrals.create_referral(referrer_id=b, referred_id=c, level=2)

    sources = await resolve_sources([a, c, d], ad_links=ad_links, referrals=referrals)

    assert sources[a].kind == SourceKind.AD_LINK
    assert sources[a].ad_link_name == "Blogger"
    assert sources[a].ad_link_id == link.id
    assert sources[c].kind == SourceKind.REFERRAL
    assert sources[c].referral_level == 2
    assert sources[c].referrer_id == b
    assert sources[d].kind == SourceKind.ORGANIC
