from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from src.core.logger import setup_logger

from .broker import broker


def scheduler() -> TaskiqScheduler:
    setup_logger()
    scheduler = TaskiqScheduler(
        broker=broker,
        sources=[LabelScheduleSource(broker)],
    )
    return scheduler
