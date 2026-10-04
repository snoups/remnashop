from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Optional

from app.modules.advertising import AdLinkRepository
from app.modules.referrals import ReferralRepository


class SourceKind(StrEnum):
    ORGANIC = "organic"
    AD_LINK = "ad_link"
    REFERRAL = "referral"


@dataclass(frozen=True, kw_only=True)
class UserSource:
    kind: SourceKind
    ad_link_id: Optional[int] = None
    ad_link_name: Optional[str] = None
    referrer_id: Optional[int] = None
    referral_level: Optional[int] = None


_ORGANIC: Final[UserSource] = UserSource(kind=SourceKind.ORGANIC)


async def resolve_sources(
    user_ids: list[int], *, ad_links: AdLinkRepository, referrals: ReferralRepository
) -> dict[int, UserSource]:
    sources = dict.fromkeys(user_ids, _ORGANIC)
    for referred_id, referrer_id, level in await referrals.list_edges(user_ids):
        sources[referred_id] = UserSource(
            kind=SourceKind.REFERRAL, referrer_id=referrer_id, referral_level=level
        )
    # an ad link beats a referral: the link is what brought them in
    for user_id, ad_link_id, name in await ad_links.list_user_links(user_ids):
        sources[user_id] = UserSource(
            kind=SourceKind.AD_LINK, ad_link_id=ad_link_id, ad_link_name=name
        )
    return sources
