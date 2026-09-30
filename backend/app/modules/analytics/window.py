from datetime import datetime, timedelta

from app.core.enums import Role
from app.core.utils.time import datetime_now
from app.modules.users import UserRepository


async def resolve_since(user_repository: UserRepository, days: int) -> datetime:
    today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = today_start.date()
    if days == 0:
        first_registration = await user_repository.earliest_registration(Role.USER)
        start_date = first_registration or today
    else:
        start_date = today - timedelta(days=days - 1)
    return today_start - timedelta(days=(today - start_date).days)
