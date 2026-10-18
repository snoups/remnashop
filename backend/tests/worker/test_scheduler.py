from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from app.core.broker import retry_schedule_source
from app.worker.scheduler import scheduler


def test_scheduler_is_a_taskiq_scheduler_bound_to_the_shared_broker() -> None:
    assert isinstance(scheduler, TaskiqScheduler)
    assert any(isinstance(source, LabelScheduleSource) for source in scheduler.sources)


def test_scheduler_also_polls_the_retry_schedule_source() -> None:
    assert retry_schedule_source in scheduler.sources


async def test_task_schedule_labels_are_discovered() -> None:
    import app.modules.subscriptions.tasks  # noqa: F401, PLC0415 - registers the task on the broker

    source = next(s for s in scheduler.sources if isinstance(s, LabelScheduleSource))
    await source.startup()
    schedules = await source.get_schedules()

    task_name = "app.modules.subscriptions.tasks:prune_subscription_idempotency_task"
    assert any(s.task_name == task_name for s in schedules)
