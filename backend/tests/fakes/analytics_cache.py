from collections.abc import Awaitable, Callable
from typing import Optional

from app.modules.analytics.cache import AnalyticsCache, ReportT


class PassThroughAnalyticsCache(AnalyticsCache):
    """Always computes: a shared Redis would hand one test another's report."""

    def __init__(self) -> None:
        pass

    async def get_or_compute(
        self,
        report: str,
        params: Optional[object],
        model: type[ReportT],
        compute: Callable[[], Awaitable[ReportT]],
    ) -> ReportT:
        return await compute()
