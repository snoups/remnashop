from typing import Final

from sqlalchemy import (
    ARRAY,
    BigInteger,
    ColumnElement,
    Text,
    any_,
    false,
    func,
    literal,
    or_,
    select,
)

from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.enums import SubscriptionStatus


def _subscriptions_in(status: SubscriptionStatus) -> ColumnElement[int]:
    # per-user count, correlated to the outer User row
    return (
        select(func.count())
        .where(Subscription.user_id == User.id, Subscription.status == status)
        .correlate(User)
        .scalar_subquery()
    )


ACTIVE_SUBSCRIPTIONS: Final[ColumnElement[int]] = _subscriptions_in(SubscriptionStatus.ACTIVE)
LIMITED_SUBSCRIPTIONS: Final[ColumnElement[int]] = _subscriptions_in(SubscriptionStatus.LIMITED)
EXPIRED_SUBSCRIPTIONS: Final[ColumnElement[int]] = _subscriptions_in(SubscriptionStatus.EXPIRED)


def identity_filter(telegram_ids: set[int], emails: set[str]) -> ColumnElement[bool]:
    # one array bind each, not IN (...): a blacklist source can exceed asyncpg's
    # 32,767 bind-parameter cap. Emails are expected lowercased.
    return or_(
        User.telegram_id == any_(literal(list(telegram_ids), ARRAY(BigInteger)))
        if telegram_ids
        else false(),
        func.lower(User.email) == any_(literal(list(emails), ARRAY(Text))) if emails else false(),
    )
