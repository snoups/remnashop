from datetime import date, datetime, time
from typing import Final

from app.core.actor import Actor
from app.core.constants import TIMEZONE
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.analytics.coverage import is_covered, paid_coverage, shift_months
from app.modules.analytics.dto import CohortRowDto, CohortsDto
from app.modules.transactions import TransactionRepository

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
        transaction_repository: TransactionRepository,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> CohortsDto:
        async with self._uow:
            now = datetime_now()
            today = now.date()
            this_month = _start_of_month(today)
            earliest_month = _add_months(this_month, -(_COHORT_MONTHS - 1))

            first_paid = await self._transaction_repository.first_paid_at_since(
                _month_start(earliest_month)
            )
            cohorts: dict[str, set[int]] = {}
            for user_id, paid_at in first_paid.items():
                key = paid_at.astimezone(TIMEZONE).strftime("%Y-%m")
                cohorts.setdefault(key, set()).add(user_id)

            payments: dict[int, list[tuple[datetime, int]]] = {}
            for user_id, paid_at, days in await self._transaction_repository.list_paid_periods(
                list(first_paid)
            ):
                payments.setdefault(user_id, []).append((paid_at, days))
            coverage = {user_id: paid_coverage(p) for user_id, p in payments.items()}

            rows = []
            for i in range(_COHORT_MONTHS):
                cohort_month = _add_months(earliest_month, i)
                users = cohorts.get(cohort_month.strftime("%Y-%m"), set())
                retention = []
                if users:
                    for m in range(_months_between(cohort_month, today) + 1):
                        # one point per user: a month-overlap check counts any 30-day plan in M1
                        active = 0
                        for user_id in users:
                            point = min(
                                shift_months(first_paid[user_id].astimezone(TIMEZONE), m), now
                            )
                            active += is_covered(coverage.get(user_id, []), point)
                        retention.append(active / len(users))
                rows.append(
                    CohortRowDto(
                        cohort=cohort_month.strftime("%Y-%m"),
                        cohort_size=len(users),
                        retention_by_month=retention,
                    )
                )
            return CohortsDto(cohorts=rows)


def _month_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=TIMEZONE)
