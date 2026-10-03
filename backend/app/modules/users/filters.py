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

# per-user count of active subscriptions, correlated to the outer User row
ACTIVE_SUBSCRIPTIONS: Final[ColumnElement[int]] = (
    select(func.count())
    .where(Subscription.user_id == User.id, Subscription.status == SubscriptionStatus.ACTIVE)
    .correlate(User)
    .scalar_subquery()
)


def identity_filter(telegram_ids: set[int], emails: set[str]) -> ColumnElement[bool]:
    # one array bind each, not IN (...): a blacklist source can exceed asyncpg's
    # 32,767 bind-parameter cap. Emails are expected lowercased.
    return or_(
        User.telegram_id == any_(literal(list(telegram_ids), ARRAY(BigInteger)))
        if telegram_ids
        else false(),
        func.lower(User.email) == any_(literal(list(emails), ARRAY(Text))) if emails else false(),
    )
