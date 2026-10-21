from datetime import datetime
from typing import Any, Final, Optional, Union

from sqlalchemy import ColumnElement, and_, delete, func, or_, select, tuple_, update
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
    UserRegistration,
)
from app.core.enums import SubscriptionStatus
from app.modules.account_merge.dto import (
    MergeConflictKey,
    MergeCountsDto,
    MergedUserDto,
    MergeLinksDto,
    MergeSide,
    oauth_conflict_key,
)
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
        ("user_registrations", "user_id"),
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
# ceiling on the walk up the referrers; a longer upline is left unchecked
_MAX_CHAIN_WALK: Final[int] = 64


class AccountMergeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_users(self, user_ids: list[int]) -> None:
        await self.session.execute(
            select(User.id).where(User.id.in_(user_ids)).order_by(User.id).with_for_update()
        )

    async def read_links(self, source_id: int, target_id: int) -> MergeLinksDto:
        source_referrer_id, source_referred_at = await self._referral_of(source_id)
        target_referrer_id, target_referred_at = await self._referral_of(target_id)
        return MergeLinksDto(
            source_referrer_id=source_referrer_id,
            target_referrer_id=target_referrer_id,
            source_oauth=await self._oauth_labels(source_id),
            target_oauth=await self._oauth_labels(target_id),
            source_referred_at=source_referred_at,
            target_referred_at=target_referred_at,
        )

    async def _referral_of(self, user_id: int) -> tuple[Optional[int], Optional[datetime]]:
        row = (
            await self.session.execute(
                select(Referral.referrer_id, Referral.created_at).where(
                    Referral.referred_id == user_id
                )
            )
        ).one_or_none()
        return (row[0], row[1]) if row else (None, None)

    async def _referrer_of(self, user_id: int) -> Optional[int]:
        return await self.session.scalar(
            select(Referral.referrer_id).where(Referral.referred_id == user_id)
        )

    async def reaches(self, start: int, user_ids: set[int]) -> bool:
        # walks start's upline, as the merge's own loop check does
        current: Optional[int] = start
        for _ in range(_MAX_CHAIN_WALK):
            if current is None:
                return False
            if current in user_ids:
                return True
            current = await self._referrer_of(current)
        return False

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
            await self._move_owner(column, s, t)

        await self._move_deduplicated(
            BroadcastRecipient.user_id,
            (BroadcastRecipient.broadcast_id, BroadcastRecipient.channel),
            s,
            t,
        )
        await self._move_deduplicated(
            AnnouncementView.user_id, (AnnouncementView.announcement_id,), s, t
        )
        await self._keep_earliest(
            PaymentWaitlistEntry.user_id, PaymentWaitlistEntry.created_at, s, t
        )
        await self._keep_earliest(AdLinkAttribution.user_id, AdLinkAttribution.created_at, s, t)
        await self._keep_earliest(UserRegistration.user_id, UserRegistration.created_at, s, t)
        await self._move_oauth(s, t, sides)
        await self._move_referrals(s, t, sides)
        await self._replace_in_promocode_allowlists(s, t)
        await self.session.flush()

    async def _move_owner(
        self,
        user_col: Union[InstrumentedAttribute[int], InstrumentedAttribute[Optional[int]]],
        s: int,
        t: int,
    ) -> None:
        # a change of owner is not an edit of the row: updated_at stays, since a
        # paid order's updated_at is its paid-at moment every revenue query reads
        model = user_col.class_
        values: dict[Any, Any] = {user_col: t}
        if hasattr(model, "updated_at"):
            values[model.updated_at] = model.updated_at
        await self.session.execute(update(model).where(user_col == s).values(values))

    async def _move_deduplicated(
        self,
        user_col: InstrumentedAttribute[int],
        keys: tuple[InstrumentedAttribute[Any], ...],
        s: int,
        t: int,
    ) -> None:
        model = user_col.class_
        taken = select(*keys).where(user_col == t)
        await self.session.execute(delete(model).where(user_col == s, tuple_(*keys).in_(taken)))
        await self._move_owner(user_col, s, t)

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
        await self._move_owner(user_col, s, t)

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
            loser = t if sides.get(oauth_conflict_key(provider)) == "source" else s
            await self.session.execute(
                delete(OAuthIdentity).where(
                    OAuthIdentity.user_id == loser, OAuthIdentity.provider == provider
                )
            )
        await self._move_owner(OAuthIdentity.user_id, s, t)

    async def _move_referrals(self, s: int, t: int, sides: dict[str, MergeSide]) -> None:
        await self.session.execute(
            delete(Referral).where(
                or_(
                    and_(Referral.referrer_id == s, Referral.referred_id == t),
                    and_(Referral.referrer_id == t, Referral.referred_id == s),
                )
            )
        )
        rows = await self.session.execute(
            select(Referral.referred_id, Referral.referrer_id).where(
                Referral.referred_id.in_((s, t))
            )
        )
        referrers = dict(rows.tuples().all())
        if len(referrers) == 2:
            # a row whose referrer was deleted (NULL) gives way to a real one
            if referrers[t] is None:
                loser = t
            elif referrers[s] is None:
                loser = s
            else:
                loser = t if sides.get(MergeConflictKey.REFERRED_BY) == "source" else s
            await self.session.execute(delete(Referral).where(Referral.referred_id == loser))
        await self._move_owner(Referral.referred_id, s, t)
        await self._move_owner(Referral.referrer_id, s, t)
        # s's upline may run through t's downline: target -> x -> source now loops
        current: Optional[int] = t
        for _ in range(_MAX_CHAIN_WALK):
            current = await self.session.scalar(
                select(Referral.referrer_id).where(Referral.referred_id == current)
            )
            if current is None:
                break
            if current == t:
                await self.session.execute(delete(Referral).where(Referral.referred_id == t))
                break

    async def _replace_in_promocode_allowlists(self, s: int, t: int) -> None:
        promocodes = await self.session.scalars(
            select(Promocode).where(Promocode.allowed_user_ids.contains([s]))
        )
        for promocode in promocodes:
            ids = promocode.allowed_user_ids or []
            promocode.allowed_user_ids = list(dict.fromkeys(t if i == s else i for i in ids))

    async def write_target(self, target_id: int, merged: MergedUserDto) -> UserDto:
        db_user = await self.session.get_one(User, target_id)
        db_user.telegram_id = merged.telegram_id
        db_user.username = merged.username
        db_user.email = merged.email
        db_user.email_undeliverable_at = merged.email_undeliverable_at
        db_user.login = merged.login
        db_user.password_hash = merged.password_hash
        db_user.password_change_required = merged.password_change_required
        db_user.name = merged.name
        db_user.language = merged.language
        db_user.personal_discount = merged.personal_discount
        db_user.personal_discount_promocode_id = merged.personal_discount_promocode_id
        db_user.purchase_discount = merged.purchase_discount
        db_user.purchase_discount_promocode_id = merged.purchase_discount_promocode_id
        db_user.role = merged.role
        db_user.permission_grants = merged.permission_grants
        db_user.permission_revokes = merged.permission_revokes
        db_user.ip_allowlist = merged.ip_allowlist
        db_user.notification_channels = merged.notification_channels
        db_user.notifications_seen_at = merged.notifications_seen_at
        db_user.notifications_cleared_at = merged.notifications_cleared_at
        db_user.points = merged.points
        db_user.bonus_days = merged.bonus_days
        db_user.is_trial_available = merged.is_trial_available
        db_user.is_blocked = merged.is_blocked
        db_user.marketing_opt_out = merged.marketing_opt_out
        db_user.loyalty_excluded = merged.loyalty_excluded
        db_user.rules_accepted_at = merged.rules_accepted_at
        await self.session.flush()
        await self.session.refresh(db_user)
        return UserDto.model_validate(db_user, from_attributes=True)
