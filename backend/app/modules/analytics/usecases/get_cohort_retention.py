from datetime import date, datetime, time
from typing import Final

from app.core.constants import TIMEZONE
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.analytics.dto import CohortRowDto, CohortsDto
from app.modules.payments import PaymentOrderRepository
from app.modules.users import UserDto, UserRepository

_COHORT_MONTHS: Final[int] = 12


def _start_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


class GetCohortRetentionUseCase(UseCase[None, CohortsDto]):
    required_permission = Permission.ANALYTICS_COHORTS_VIEW

    def __init__(
        self,
        user_repository: UserRepository,
        payment_order_repository: PaymentOrderRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._payment_order_repository = payment_order_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> CohortsDto:
        async with self._uow:
            now = datetime_now()
            today = now.date()
            earliest_month = _add_months(_start_of_month(today), -(_COHORT_MONTHS - 1))
            earliest_since = datetime.combine(earliest_month, time.min, tzinfo=TIMEZONE)

            registrations = await self._user_repository.list_id_and_registration_date_since(
                earliest_since, Role.USER
            )
            cohorts: dict[str, set[int]] = {}
            registered_month_by_user: dict[int, str] = {}
            for user_id, registered_on in registrations:
                key = _start_of_month(registered_on).strftime("%Y-%m")
                cohorts.setdefault(key, set()).add(user_id)
                registered_month_by_user[user_id] = key

            all_user_ids = list(registered_month_by_user.keys())
            paid_pairs = await self._payment_order_repository.list_paid_user_month_pairs(
                all_user_ids, earliest_since
            )
            activity: dict[str, dict[str, set[int]]] = {}
            for user_id, paid_month in paid_pairs:
                cohort_key = registered_month_by_user.get(user_id)
                if cohort_key is None:
                    continue
                month_key = paid_month.strftime("%Y-%m")
                activity.setdefault(cohort_key, {}).setdefault(month_key, set()).add(user_id)

            rows = []
            for i in range(_COHORT_MONTHS):
                cohort_date = _add_months(_start_of_month(today), -(_COHORT_MONTHS - 1 - i))
                cohort_key = cohort_date.strftime("%Y-%m")
                cohort_users = cohorts.get(cohort_key, set())
                if not cohort_users:
                    rows.append(
                        CohortRowDto(cohort=cohort_key, cohort_size=0, retention_by_month=[])
                    )
                    continue
                months_elapsed = _months_between(cohort_date, today) + 1
                cohort_activity = activity.get(cohort_key, {})
                retention = [
                    len(cohort_activity.get(_add_months(cohort_date, m).strftime("%Y-%m"), set()))
                    / len(cohort_users)
                    for m in range(months_elapsed)
                ]
                rows.append(
                    CohortRowDto(
                        cohort=cohort_key,
                        cohort_size=len(cohort_users),
                        retention_by_month=retention,
                    )
                )

            return CohortsDto(cohorts=rows)
