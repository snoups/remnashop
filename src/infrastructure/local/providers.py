from dishka import Provider, Scope, provide
from remnapy import RemnawaveSDK

from src.application.common.dao import (
    BroadcastDao,
    PaymentGatewayDao,
    PlanDao,
    ReferralDao,
    SettingsDao,
    SubscriptionDao,
    TransactionDao,
    UserDao,
    WaitlistDao,
    WebhookDao,
)
from src.application.common.uow import UnitOfWork

from .store import (
    InMemoryBroadcastDao,
    InMemoryPaymentGatewayDao,
    InMemoryPlanDao,
    InMemoryReferralDao,
    InMemoryRemnawaveSDK,
    InMemorySettingsDao,
    InMemoryStore,
    InMemorySubscriptionDao,
    InMemoryTransactionDao,
    InMemoryUnitOfWork,
    InMemoryUserDao,
    InMemoryWaitlistDao,
    InMemoryWebhookDao,
)


class LocalDatabaseProvider(Provider):
    scope = Scope.APP

    @provide
    def store(self) -> InMemoryStore:
        return InMemoryStore()

    @provide(scope=Scope.REQUEST)
    def uow(self) -> UnitOfWork:
        return InMemoryUnitOfWork()


class LocalDaoProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def user(self, store: InMemoryStore) -> UserDao:
        return InMemoryUserDao(store)

    @provide
    def settings(self, store: InMemoryStore) -> SettingsDao:
        return InMemorySettingsDao(store)

    @provide
    def plan(self, store: InMemoryStore) -> PlanDao:
        return InMemoryPlanDao(store)

    @provide
    def subscription(self, store: InMemoryStore) -> SubscriptionDao:
        return InMemorySubscriptionDao(store)

    @provide
    def payment_gateway(self, store: InMemoryStore) -> PaymentGatewayDao:
        return InMemoryPaymentGatewayDao(store)

    @provide
    def transaction(self, store: InMemoryStore) -> TransactionDao:
        return InMemoryTransactionDao(store)

    @provide
    def referral(self, store: InMemoryStore) -> ReferralDao:
        return InMemoryReferralDao(store)

    @provide
    def broadcast(self, store: InMemoryStore) -> BroadcastDao:
        return InMemoryBroadcastDao(store)

    @provide(scope=Scope.APP)
    def webhook(self, store: InMemoryStore) -> WebhookDao:
        return InMemoryWebhookDao(store)

    @provide(scope=Scope.APP)
    def waitlist(self, store: InMemoryStore) -> WaitlistDao:
        return InMemoryWaitlistDao(store)


class LocalRemnawaveProvider(Provider):
    scope = Scope.APP

    @provide
    def remnawave_sdk(self) -> RemnawaveSDK:
        return InMemoryRemnawaveSDK()  # type: ignore[return-value]
