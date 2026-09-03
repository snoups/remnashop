from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from app.worker.broker import broker, retry_schedule_source

scheduler = TaskiqScheduler(
    broker=broker, sources=[LabelScheduleSource(broker), retry_schedule_source]
)
