from dishka import Scope
from remnapy import RemnawaveSDK

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.modules.event_log.repository import EventLogRepository
from app.modules.plans import PlanRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.translations.repository import TranslationsRepository
from app.modules.users import UserRepository
from app.worker.container import create_worker_container


async def test_worker_container_resolves_persist_event_task_dependencies(
    config: AppConfig,
) -> None:
    # persist_event_task (modules/event_log/tasks.py) is FromDishka-injected
    # with EventLogRepository/UnitOfWork. Dishka only validates provide()-
    # registered classes when the container is built -- a FromDishka
    # parameter with no matching provider doesn't fail worker startup, only
    # every actual run of that task (NoFactoryError at dispatch time). Add
    # the equivalent resolution check here for every future worker task
    # module's dependencies, matching its providers in create_worker_container().
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(EventLogRepository)
        await request_container.get(UnitOfWork)
    await container.close()


async def test_worker_container_resolves_translation_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(TranslationsRepository)
        await request_container.get(UnitOfWork)
    await container.close()


async def test_worker_container_resolves_purchase_subscription_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(PlanRepository)
        await request_container.get(SubscriptionRepository)
        await request_container.get(RemnawaveSDK)
        await request_container.get(UnitOfWork)
        await request_container.get(UserRepository)
        await request_container.get(SubscriptionLifecycleService)
    await container.close()


async def test_worker_container_resolves_reconcile_subscriptions_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(SubscriptionRepository)
        await request_container.get(RemnawaveSDK)
        await request_container.get(UnitOfWork)
        await request_container.get(EventPublisher)
        await request_container.get(SubscriptionLifecycleService)
    await container.close()
