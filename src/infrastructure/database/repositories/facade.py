from sqlalchemy.ext.asyncio import AsyncSession

from .payment_gateway import PaymentGatewayRepository
from .plan import PlanRepository
from .promocode import PromocodeRepository
from .subscription import SubscriptionRepository
from .transaction import TransactionRepository
from .user import UserRepository


class RepositoriesFacade:
    session: AsyncSession

    gateways: PaymentGatewayRepository
    plans: PlanRepository
    promocodes: PromocodeRepository
    subscriptions: SubscriptionRepository
    transactions: TransactionRepository
    users: UserRepository

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self.gateways = PaymentGatewayRepository(session)
        self.plans = PlanRepository(session)
        self.promocodes = PromocodeRepository(session)
        self.subscriptions = SubscriptionRepository(session)
        self.transactions = TransactionRepository(session)
        self.users = UserRepository(session)
