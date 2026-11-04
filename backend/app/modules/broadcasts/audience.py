from datetime import datetime, timedelta
from typing import Final, Optional

from sqlalchemy import ColumnElement, and_, exists, or_, select

from app.core.db.filters import in_ids
from app.core.db.models.ad_link_attribution import AdLinkAttribution
from app.core.db.models.referral import Referral
from app.core.db.models.subscription import Subscription
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.enums import (
    BroadcastCategory,
    BroadcastChannel,
    BroadcastDelivery,
    BroadcastSubscriptionFilter,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.broadcasts.channels import sends_telegram
from app.modules.broadcasts.dto import BroadcastAudienceDto

_LIVE: Final[tuple[SubscriptionStatus, ...]] = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.LIMITED,
)


def _has_subscription(*conditions: ColumnElement[bool]) -> ColumnElement[bool]:
    return exists(select(Subscription.id).where(Subscription.user_id == User.id, *conditions))


def _live(*conditions: ColumnElement[bool]) -> ColumnElement[bool]:
    return _has_subscription(Subscription.status.in_(_LIVE), *conditions)


def _subscription_bucket(bucket: BroadcastSubscriptionFilter) -> ColumnElement[bool]:
    if bucket is BroadcastSubscriptionFilter.ACTIVE:
        return _live(Subscription.is_trial.is_(False))
    if bucket is BroadcastSubscriptionFilter.TRIAL:
        return _live(Subscription.is_trial.is_(True))
    if bucket is BroadcastSubscriptionFilter.EXPIRED:
        return and_(_has_subscription(Subscription.status == SubscriptionStatus.EXPIRED), ~_live())
    if bucket is BroadcastSubscriptionFilter.LIMITED:
        return _has_subscription(Subscription.status == SubscriptionStatus.LIMITED)
    return ~_has_subscription(Subscription.status != SubscriptionStatus.DELETED)


_PAID: Final[ColumnElement[bool]] = exists(
    select(Transaction.id).where(
        Transaction.user_id == User.id,
        Transaction.status == TransactionStatus.PAID,
        Transaction.is_test.is_(False),
    )
)
_REFERRED: Final[ColumnElement[bool]] = exists(
    select(Referral.id).where(Referral.referred_id == User.id)
)


def _flag(condition: ColumnElement[bool], wanted: bool) -> ColumnElement[bool]:
    return condition if wanted else ~condition


def _subscription_conditions(
    audience: BroadcastAudienceDto, now: datetime
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if audience.subscription:
        conditions.append(or_(*(_subscription_bucket(b) for b in audience.subscription)))
    if audience.plan_ids:
        conditions.append(
            _live(Subscription.plan_snapshot["plan_id"].as_integer().in_(audience.plan_ids))
        )
    if audience.expires_within_days is not None:
        conditions.append(
            _live(
                Subscription.expire_at >= now,
                Subscription.expire_at < now + timedelta(days=audience.expires_within_days),
            )
        )
    if audience.expired_within_days is not None:
        conditions.append(
            _has_subscription(
                Subscription.status == SubscriptionStatus.EXPIRED,
                Subscription.expire_at >= now - timedelta(days=audience.expired_within_days),
                Subscription.expire_at < now,
            )
        )
        conditions.append(~_live())
    if audience.not_connected_within_days is not None:
        conditions.append(
            _live(
                Subscription.first_connected_at.is_(None),
                Subscription.created_at >= now - timedelta(days=audience.not_connected_within_days),
            )
        )
    return conditions


def _profile_conditions(audience: BroadcastAudienceDto) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if audience.paid is not None:
        conditions.append(_flag(_PAID, audience.paid))
    if audience.locales:
        conditions.append(User.language.in_(audience.locales))
    registered_from = range_start_utc(audience.registered_from)
    registered_to = range_end_utc(audience.registered_to)
    if registered_from is not None:
        conditions.append(User.created_at >= registered_from)
    if registered_to is not None:
        conditions.append(User.created_at < registered_to)
    if audience.ad_link_ids:
        conditions.append(
            exists(
                select(AdLinkAttribution.id).where(
                    AdLinkAttribution.user_id == User.id,
                    AdLinkAttribution.ad_link_id.in_(audience.ad_link_ids),
                )
            )
        )
    if audience.referred is not None:
        conditions.append(_flag(_REFERRED, audience.referred))
    if audience.has_telegram is not None:
        conditions.append(_flag(User.telegram_id.is_not(None), audience.has_telegram))
    if audience.has_email is not None:
        conditions.append(_flag(User.email.is_not(None), audience.has_email))
    return conditions


def deliverable_email() -> ColumnElement[bool]:
    return and_(User.email.is_not(None), User.email_undeliverable_at.is_(None))


def _bot_reachable() -> ColumnElement[bool]:
    return and_(User.telegram_id.is_not(None), User.is_bot_blocked.is_(False))


def channel_condition(
    channel: BroadcastChannel, delivery: BroadcastDelivery, email_fallback: bool
) -> Optional[ColumnElement[bool]]:
    # None: the delivery mode never sends on this channel. A customer who blocked the bot is no
    # Telegram recipient (counted or materialized); the fallback email reaches them like one
    # without Telegram, as customer notifications do.
    if channel is BroadcastChannel.TELEGRAM:
        return _bot_reachable() if sends_telegram(delivery) else None
    if delivery is BroadcastDelivery.TELEGRAM:
        return and_(~_bot_reachable(), deliverable_email()) if email_fallback else None
    return deliverable_email()


def audience_predicate(
    audience: BroadcastAudienceDto, category: BroadcastCategory, now: datetime
) -> ColumnElement[bool]:
    conditions: list[ColumnElement[bool]] = [
        User.role == Role.USER,
        User.deleted_at.is_(None),
        User.is_blocked.is_(False),
    ]
    if category is BroadcastCategory.MARKETING:
        conditions.append(User.marketing_opt_out.is_(False))

    if audience.user_ids:
        return and_(*conditions, in_ids(User.id, audience.user_ids))

    conditions += _subscription_conditions(audience, now)
    conditions += _profile_conditions(audience)
    return and_(*conditions)
