from dishka import Scope
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.event_bus import EventBus
from app.core.ports import EventPublisher
from app.modules.advertising.repository import AdLinkRepository
from app.modules.auth import SessionRepository
from app.modules.backups import BackupRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.event_log.outbox_repository import EventOutboxRepository
from app.modules.event_log.repository import EventLogRepository
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.translations.repository import TranslationsRepository
from app.modules.users import UserRepository
from app.worker.container import create_worker_container


async def test_worker_container_resolves_outbox_task_dependencies(
    config: AppConfig,
) -> None:
    # process_outbox_entry_task/sweep_outbox_task (modules/event_log/tasks.py)
    # are FromDishka-injected with EventOutboxRepository/EventLogRepository/
    # EventBus/UnitOfWork. Dishka only validates provide()-registered classes
    # when the container is built -- a FromDishka parameter with no matching
    # provider doesn't fail worker startup, only every actual run of that task
    # (NoFactoryError at dispatch time). Add the equivalent resolution check
    # here for every future worker task module's dependencies, matching its
    # providers in create_worker_container().
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(EventOutboxRepository)
        await request_container.get(EventLogRepository)
        await request_container.get(EventBus)
        await request_container.get(UnitOfWork)
        await request_container.get(Redis)
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
        await request_container.get(SubscriptionRepository)
        await request_container.get(RemnawaveSDK)
        await request_container.get(UnitOfWork)
        await request_container.get(UserRepository)
        await request_container.get(SubscriptionLifecycleService)
    await container.close()


async def test_worker_container_resolves_payment_order_prune_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(PaymentOrderRepository)
        await request_container.get(UnitOfWork)
    await container.close()


async def test_worker_container_resolves_reconcile_paid_orders_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(PaymentOrderRepository)
        await request_container.get(SubscriptionRepository)
        await request_container.get(Redis)
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
        await request_container.get(Redis)
    await container.close()


async def test_worker_container_resolves_prune_stale_sessions_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(SessionRepository)
        await request_container.get(UnitOfWork)
    await container.close()


async def test_worker_container_resolves_backup_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(BackupRepository)
        await request_container.get(UnitOfWork)
        await request_container.get(Redis)
    await container.close()


async def test_worker_container_resolves_blacklist_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(BlacklistRepository)
        await request_container.get(UserRepository)
        await request_container.get(UnitOfWork)
        await request_container.get(EventPublisher)
        await request_container.get(Redis)
    await container.close()


async def test_worker_container_resolves_assign_referral_rewards_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(ReferralRepository)
        await request_container.get(UserRepository)
        await request_container.get(SubscriptionRepository)
        await request_container.get(PurchaseSubscriptionUseCase)
        await request_container.get(UnitOfWork)
        await request_container.get(EventPublisher)
    await container.close()


async def test_worker_container_resolves_ad_link_attribution_task_dependencies(
    config: AppConfig,
) -> None:
    container = create_worker_container(config)
    async with container(scope=Scope.REQUEST) as request_container:
        await request_container.get(AdLinkRepository)
        await request_container.get(UnitOfWork)
    await container.close()
