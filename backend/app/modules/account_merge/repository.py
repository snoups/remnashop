from datetime import datetime
from typing import Any, Final, Optional

from sqlalchemy import ColumnElement, and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.db.models import (
    AdLinkAttribution,
    AnnouncementView,
    ApiToken,
    BroadcastRecipient,
    OAuthIdentity,
    PasskeyCredential,
    PaymentWaitlistEntry,
    Promocode,
    PromocodeActivation,
    PushSubscription,
    Referral,
    ReferralReward,
    Subscription,
    Transaction,
    User,
)
from app.core.enums import SubscriptionStatus
from app.modules.account_merge.dto import MergeCountsDto, MergeLinksDto, MergeSide
from app.modules.users import UserDto

REASSIGNED_USER_FKS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("subscriptions", "user_id"),
        ("transactions", "user_id"),
        ("promocode_activations", "user_id"),
        ("passkey_credentials", "user_id"),
        ("api_tokens", "created_by_user_id"),
        ("push_subscriptions", "user_id"),
        ("oauth_identities", "user_id"),
        ("broadcast_recipients", "user_id"),
        ("announcement_views", "user_id"),
        ("payment_waitlist", "user_id"),
        ("ad_link_attributions", "user_id"),
        ("referrals", "referrer_id"),
        ("referrals", "referred_id"),
        ("referral_rewards", "referrer_id"),
    }
)
# history stays as it happened; sessions are revoked through SessionRevoker
UNTOUCHED_USER_FKS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("event_log_entries", "actor_id"),
        ("event_log_entries", "target_id"),
        ("event_outbox", "actor_id"),
        ("backup_runs", "triggered_by"),
        ("ad_links", "created_by"),
        ("broadcasts", "created_by"),
        ("user_sessions", "user_id"),
    }
)


class AccountMergeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_users(self, user_ids: list[int]) -> None:
        await self.session.execute(
            select(User.id).where(User.id.in_(user_ids)).order_by(User.id).with_for_update()
        )

    async def read_links(self, source_id: int, target_id: int) -> MergeLinksDto:
        return MergeLinksDto(
            source_referrer_id=await self._referrer_of(source_id),
            target_referrer_id=await self._referrer_of(target_id),
            source_oauth=await self._oauth_labels(source_id),
            target_oauth=await self._oauth_labels(target_id),
        )

    async def _referrer_of(self, user_id: int) -> Optional[int]:
        return await self.session.scalar(
            select(Referral.referrer_id).where(Referral.referred_id == user_id)
        )

    async def _oauth_labels(self, user_id: int) -> dict[str, str]:
        rows = await self.session.execute(
            select(
                OAuthIdentity.provider, OAuthIdentity.external_login, OAuthIdentity.external_id
            ).where(OAuthIdentity.user_id == user_id)
        )
        return {str(provider): login or external_id for provider, login, external_id in rows}

    async def count_owned(self, user_id: int) -> MergeCountsDto:
        async def count(*where: ColumnElement[bool]) -> int:
            return int(await self.session.scalar(select(func.count()).where(*where)) or 0)

        return MergeCountsDto(
            subscriptions=await count(
                Subscription.user_id == user_id,
                Subscription.status != SubscriptionStatus.DELETED,
            ),
            transactions=await count(Transaction.user_id == user_id),
            referrals=await count(Referral.referrer_id == user_id),
            passkeys=await count(PasskeyCredential.user_id == user_id),
            oauth_identities=await count(OAuthIdentity.user_id == user_id),
        )

    async def reassign(
        self,
        source_id: int,
        target_id: int,
        sides: dict[str, MergeSide],
        *,
        drop_credentials_of: Optional[int] = None,
    ) -> None:
        s, t = source_id, target_id
        if drop_credentials_of is not None:
            for user_col in (OAuthIdentity.user_id, PasskeyCredential.user_id):
                await self.session.execute(
                    delete(user_col.class_).where(user_col == drop_credentials_of)
                )
        for column in (
            Subscription.user_id,
            Transaction.user_id,
            PromocodeActivation.user_id,
            PasskeyCredential.user_id,
            ApiToken.created_by_user_id,
            PushSubscription.user_id,
            ReferralReward.referrer_id,
        ):
            await self.session.execute(update(column.class_).where(column == s).values({column: t}))

        await self._move_deduplicated(
            BroadcastRecipient.user_id, BroadcastRecipient.broadcast_id, s, t
        )
        await self._move_deduplicated(
            AnnouncementView.user_id, AnnouncementView.announcement_id, s, t
        )
        await self._keep_earliest(
            PaymentWaitlistEntry.user_id, PaymentWaitlistEntry.created_at, s, t
        )
        await self._keep_earliest(AdLinkAttribution.user_id, AdLinkAttribution.created_at, s, t)
        await self._move_oauth(s, t, sides)
        await self._move_referrals(s, t, sides)
        await self._replace_in_promocode_allowlists(s, t)
        await self.session.flush()

    async def _move_deduplicated(
        self, user_col: InstrumentedAttribute[int], key: InstrumentedAttribute[Any], s: int, t: int
    ) -> None:
        model = user_col.class_
        taken = select(key).where(user_col == t)
        await self.session.execute(delete(model).where(user_col == s, key.in_(taken)))
        await self.session.execute(update(model).where(user_col == s).values({user_col: t}))

    async def _keep_earliest(
        self,
        user_col: InstrumentedAttribute[int],
        created_col: InstrumentedAttribute[datetime],
        s: int,
        t: int,
    ) -> None:
        model = user_col.class_
        rows = (
            await self.session.execute(
                select(user_col).where(user_col.in_((s, t))).order_by(created_col)
            )
        ).all()
        if len(rows) == 2:
            await self.session.execute(delete(model).where(user_col == rows[1][0]))
        await self.session.execute(update(model).where(user_col == s).values({user_col: t}))

    async def _move_oauth(self, s: int, t: int, sides: dict[str, MergeSide]) -> None:
        source_providers = set(
            await self.session.scalars(
                select(OAuthIdentity.provider).where(OAuthIdentity.user_id == s)
            )
        )
        target_providers = set(
            await self.session.scalars(
                select(OAuthIdentity.provider).where(OAuthIdentity.user_id == t)
            )
        )
        for provider in source_providers & target_providers:
            loser = t if sides.get(f"oauth:{provider}") == "source" else s
            await self.session.execute(
                delete(OAuthIdentity).where(
                    OAuthIdentity.user_id == loser, OAuthIdentity.provider == provider
                )
            )
        await self.session.execute(
            update(OAuthIdentity).where(OAuthIdentity.user_id == s).values(user_id=t)
        )

    async def _move_referrals(self, s: int, t: int, sides: dict[str, MergeSide]) -> None:
        await self.session.execute(
            delete(Referral).where(
                or_(
                    and_(Referral.referrer_id == s, Referral.referred_id == t),
                    and_(Referral.referrer_id == t, Referral.referred_id == s),
                )
            )
        )
        both_invited = (
            await self.session.scalar(select(func.count()).where(Referral.referred_id.in_((s, t))))
        ) == 2
        if both_invited:
            loser = t if sides.get("referred_by") == "source" else s
            await self.session.execute(delete(Referral).where(Referral.referred_id == loser))
        await self.session.execute(
            update(Referral).where(Referral.referred_id == s).values(referred_id=t)
        )
        await self.session.execute(
            update(Referral).where(Referral.referrer_id == s).values(referrer_id=t)
        )

    async def _replace_in_promocode_allowlists(self, s: int, t: int) -> None:
        promocodes = await self.session.scalars(
            select(Promocode).where(Promocode.allowed_user_ids.contains([s]))
        )
        for promocode in promocodes:
            ids = promocode.allowed_user_ids or []
            promocode.allowed_user_ids = list(dict.fromkeys(t if i == s else i for i in ids))

    async def write_target(self, target_id: int, values: dict[str, object]) -> UserDto:
        db_user = await self.session.get_one(User, target_id)
        for name, value in values.items():
            setattr(db_user, name, value)
        await self.session.flush()
        await self.session.refresh(db_user)
        return UserDto.model_validate(db_user, from_attributes=True)
