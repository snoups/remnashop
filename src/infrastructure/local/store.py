from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Optional
from uuid import UUID, uuid4

from packaging.version import Version
from remnapy.enums.users import TrafficLimitStrategy

from src.application.dto import (
    BroadcastDto,
    BroadcastMessageDto,
    GatewayStatsDto,
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PlanIncomeDto,
    PlanPriceDto,
    PlanSnapshotDto,
    PlanSubStatsDto,
    PriceDetailsDto,
    ReferralDto,
    ReferralRewardDto,
    ReferralStatisticsDto,
    SettingsDto,
    SubscriptionDto,
    SubscriptionStatsDto,
    TransactionDto,
    UserDto,
    UserPaymentStatsDto,
)
from src.application.dto.message_payload import MessagePayloadDto
from src.core.enums import (
    BroadcastAudience,
    BroadcastMessageStatus,
    BroadcastStatus,
    Currency,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PurchaseType,
    ReferralRewardType,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from src.core.utils.converters import days_to_datetime


class InMemoryUnitOfWork:
    async def __aenter__(self) -> "InMemoryUnitOfWork":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@dataclass
class InMemoryStore:
    users: dict[int, UserDto] = field(default_factory=dict)
    settings: SettingsDto = field(default_factory=SettingsDto)
    plans: dict[int, PlanDto] = field(default_factory=dict)
    subscriptions: dict[int, SubscriptionDto] = field(default_factory=dict)
    current_subscription_by_user: dict[int, int] = field(default_factory=dict)
    gateways: dict[int, PaymentGatewayDto] = field(default_factory=dict)
    transactions: dict[UUID, TransactionDto] = field(default_factory=dict)
    referrals: list[ReferralDto] = field(default_factory=list)
    rewards: list[ReferralRewardDto] = field(default_factory=list)
    broadcasts: dict[UUID, BroadcastDto] = field(default_factory=dict)
    waitlist: set[int] = field(default_factory=set)
    webhooks: dict[int, set[str]] = field(default_factory=dict)
    next_ids: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        plan = PlanDto(
            id=1,
            public_code="preview",
            name="Preview VPN",
            description="Локальный план для теста интерфейса",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
            is_active=True,
            durations=[
                PlanDurationDto(
                    id=1,
                    days=30,
                    prices=[PlanPriceDto(id=1, currency=Currency.RUB, price=Decimal("199"))],
                )
            ],
        )
        self.plans[1] = plan
        self.gateways[1] = PaymentGatewayDto(
            id=1,
            type=PaymentGatewayType.TELEGRAM_STARS,
            currency=Currency.RUB,
            is_active=True,
        )
        self.next_ids.update(
            user=1,
            plan=2,
            subscription=1,
            gateway=2,
            transaction=1,
            referral=1,
            reward=1,
            broadcast=1,
        )

    def next_id(self, key: str) -> int:
        value = self.next_ids.get(key, 1)
        self.next_ids[key] = value + 1
        return value


class InMemoryUserDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create(self, user: UserDto) -> UserDto:
        self.store.users[user.telegram_id] = user
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserDto]:
        return self.store.users.get(telegram_id)

    async def get_by_telegram_ids(self, telegram_ids: list[int]) -> list[UserDto]:
        return [u for tid in telegram_ids if (u := self.store.users.get(tid))]

    async def get_by_partial_name(self, query: str) -> list[UserDto]:
        query = query.lower()
        return [u for u in self.store.users.values() if query in u.name.lower()]

    async def get_by_referral_code(self, referral_code: str) -> Optional[UserDto]:
        return next((u for u in self.store.users.values() if u.referral_code == referral_code), None)

    async def get_all(self, limit: Optional[int] = None, offset: int = 0) -> list[UserDto]:
        users = list(self.store.users.values())[offset:]
        return users[:limit] if limit else users

    async def update(self, user: UserDto) -> Optional[UserDto]:
        self.store.users[user.telegram_id] = user
        return user

    async def delete(self, telegram_id: int) -> bool:
        return self.store.users.pop(telegram_id, None) is not None

    async def count(self) -> int:
        return len(self.store.users)

    async def exists(self, telegram_id: int) -> bool:
        return telegram_id in self.store.users

    async def filter_by_role(self, role: list[Role]) -> list[UserDto]:
        return [u for u in self.store.users.values() if u.role in role]

    async def set_trial_available(self, telegram_id: int, is_trial_available: bool) -> None:
        if user := self.store.users.get(telegram_id):
            user.is_trial_available = is_trial_available

    async def set_bot_blocked_status(self, telegram_id: int, is_bot_blocked: bool) -> None:
        if user := self.store.users.get(telegram_id):
            user.is_bot_blocked = is_bot_blocked

    async def set_current_subscription(self, telegram_id: int, subscription_id: int) -> None:
        self.store.current_subscription_by_user[telegram_id] = subscription_id

    async def clear_current_subscription(self, telegram_id: int) -> None:
        self.store.current_subscription_by_user.pop(telegram_id, None)

    async def get_blocked_users(self) -> list[UserDto]:
        return [u for u in self.store.users.values() if u.is_blocked or u.is_bot_blocked]

    async def get_recent_activity_users(self, excluded_ids: list[int] | None = None) -> list[UserDto]:
        excluded = set(excluded_ids or [])
        return [u for u in self.store.users.values() if u.telegram_id not in excluded][:5]

    async def get_recent_registered_users(self, limit: int = 5) -> list[UserDto]:
        return list(self.store.users.values())[-limit:]

    async def unblock_all(self) -> None:
        for user in self.store.users.values():
            user.is_blocked = False
            user.is_bot_blocked = False

    async def count_blocked(self) -> int:
        return len(await self.get_blocked_users())

    async def has_any_subscription(self, telegram_id: int, *, include_trial: bool = True) -> bool:
        return bool(await InMemorySubscriptionDao(self.store).get_all_by_user(telegram_id))

    async def is_invited_user(self, telegram_id: int) -> bool:
        return False

    async def toggle_blocked_status(self, telegram_id: int) -> None:
        if user := self.store.users.get(telegram_id):
            user.is_blocked = not user.is_blocked

    async def count_active_non_blocked(self) -> int:
        return len([u for u in self.store.users.values() if not u.is_bot_blocked])

    async def count_with_active_subscription(self) -> int:
        return len(self.store.current_subscription_by_user)

    async def count_without_subscription(self) -> int:
        return len(self.store.users) - len(self.store.current_subscription_by_user)

    async def count_with_expired_subscription(self) -> int:
        return 0

    async def count_with_trial_subscription(self) -> int:
        return len([s for s in self.store.subscriptions.values() if s.is_trial])

    async def get_active_non_blocked(self) -> list[UserDto]:
        return [u for u in self.store.users.values() if not u.is_bot_blocked]

    async def get_active_by_plan(self, plan_id: int) -> list[UserDto]:
        return await self.get_active_non_blocked()

    async def get_with_active_subscription(self) -> list[UserDto]:
        return [self.store.users[tid] for tid in self.store.current_subscription_by_user if tid in self.store.users]

    async def get_without_subscription(self) -> list[UserDto]:
        return [u for u in self.store.users.values() if u.telegram_id not in self.store.current_subscription_by_user]

    async def get_with_expired_subscription(self) -> list[UserDto]:
        return []

    async def get_with_trial_subscription(self) -> list[UserDto]:
        return []

    async def count_new(self, days: int) -> int:
        return len(self.store.users)

    async def count_bot_blocked(self) -> int:
        return len([u for u in self.store.users.values() if u.is_bot_blocked])


class InMemorySettingsDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def get(self) -> SettingsDto:
        return self.store.settings

    async def update(self, settings: SettingsDto) -> Optional[SettingsDto]:
        self.store.settings = settings
        return settings

    async def create_default(self) -> SettingsDto:
        self.store.settings = SettingsDto()
        return self.store.settings


class InMemoryPlanDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create(self, plan: PlanDto) -> PlanDto:
        plan.id = plan.id or self.store.next_id("plan")
        self.store.plans[plan.id] = plan
        return plan

    async def get_by_id(self, plan_id: int) -> Optional[PlanDto]:
        return self.store.plans.get(plan_id)

    async def get_by_name(self, name: str) -> Optional[PlanDto]:
        return next((p for p in self.store.plans.values() if p.name == name), None)

    async def get_active_plans(self) -> list[PlanDto]:
        return [p for p in self.store.plans.values() if p.is_active and not p.is_trial]

    async def get_active_trial_plans(self) -> list[PlanDto]:
        return [p for p in self.store.plans.values() if p.is_active and p.is_trial]

    async def get_all(self) -> list[PlanDto]:
        return list(self.store.plans.values())

    async def get_by_public_code(self, public_code: str) -> Optional[PlanDto]:
        return next((p for p in self.store.plans.values() if p.public_code == public_code), None)

    async def update(self, plan: PlanDto) -> Optional[PlanDto]:
        if plan.id is None:
            return None
        self.store.plans[plan.id] = plan
        return plan

    async def update_status(self, plan_id: int, is_active: bool) -> Optional[PlanDto]:
        if plan := self.store.plans.get(plan_id):
            plan.is_active = is_active
        return plan

    async def delete(self, plan_id: int) -> bool:
        return self.store.plans.pop(plan_id, None) is not None

    async def filter_by_availability(self, availability: PlanAvailability) -> list[PlanDto]:
        return [p for p in self.store.plans.values() if p.availability == availability]

    async def get_active_allowed_plans(self) -> list[PlanDto]:
        return await self.get_active_plans()

    async def count_non_trial(self) -> int:
        return len([p for p in self.store.plans.values() if not p.is_trial])


class InMemorySubscriptionDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create(self, subscription: SubscriptionDto, telegram_id: int) -> SubscriptionDto:
        subscription.id = subscription.id or self.store.next_id("subscription")
        self.store.subscriptions[subscription.id] = subscription
        self.store.current_subscription_by_user[telegram_id] = subscription.id
        return subscription

    async def get_by_id(self, subscription_id: int) -> Optional[SubscriptionDto]:
        return self.store.subscriptions.get(subscription_id)

    async def get_by_remna_id(self, remna_id: UUID) -> Optional[SubscriptionDto]:
        return next((s for s in self.store.subscriptions.values() if s.user_remna_id == remna_id), None)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[SubscriptionDto]:
        return await self.get_current(telegram_id)

    async def get_all_by_user(self, telegram_id: int) -> list[SubscriptionDto]:
        current = await self.get_current(telegram_id)
        return [current] if current else []

    async def get_current(self, telegram_id: int) -> Optional[SubscriptionDto]:
        sub_id = self.store.current_subscription_by_user.get(telegram_id)
        return self.store.subscriptions.get(sub_id) if sub_id else None

    async def update(self, subscription: SubscriptionDto) -> Optional[SubscriptionDto]:
        if subscription.id is None:
            return None
        self.store.subscriptions[subscription.id] = subscription
        return subscription

    async def update_status(self, subscription_id: int, status: SubscriptionStatus) -> Optional[SubscriptionDto]:
        if subscription := self.store.subscriptions.get(subscription_id):
            subscription.status = status
        return subscription

    async def exists(self, remna_id: UUID) -> bool:
        return bool(await self.get_by_remna_id(remna_id))

    async def count_active_by_plan(self, plan_id: int) -> int:
        return len(self.store.subscriptions)

    async def get_all_active_internal_squads(self) -> list[UUID]:
        return []

    async def count_total_trials(self) -> int:
        return len([s for s in self.store.subscriptions.values() if s.is_trial])

    async def count_converted_from_trial(self) -> int:
        return 0

    async def get_stats(self) -> SubscriptionStatsDto:
        total = len(self.store.subscriptions)
        return SubscriptionStatsDto(total, total, 0, 0, 0, 0, 0, 0, total, total)

    async def get_plan_sub_stats(self) -> list[PlanSubStatsDto]:
        return [PlanSubStatsDto(1, "Preview VPN", len(self.store.subscriptions), len(self.store.subscriptions), 0, 0, 0, 0, 0, len(self.store.subscriptions), len(self.store.subscriptions), 30)]


class InMemoryPaymentGatewayDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create(self, gateway: PaymentGatewayDto) -> PaymentGatewayDto:
        gateway.id = gateway.id or self.store.next_id("gateway")
        self.store.gateways[gateway.id] = gateway
        return gateway

    async def get_by_id(self, gateway_id: int) -> Optional[PaymentGatewayDto]:
        return self.store.gateways.get(gateway_id)

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGatewayDto]:
        return next((g for g in self.store.gateways.values() if g.type == gateway_type), None)

    async def get_active(self) -> list[PaymentGatewayDto]:
        return [g for g in self.store.gateways.values() if g.is_active]

    async def get_all(self, only_active: bool = False, sorted: bool = True) -> list[PaymentGatewayDto]:
        gateways = await self.get_active() if only_active else list(self.store.gateways.values())
        return gateways if not sorted else sorted_gateways(gateways)

    async def update(self, gateway: PaymentGatewayDto) -> Optional[PaymentGatewayDto]:
        if gateway.id is None:
            return None
        self.store.gateways[gateway.id] = gateway
        return gateway

    async def set_active_status(self, gateway_type: PaymentGatewayType, is_active: bool) -> None:
        if gateway := await self.get_by_type(gateway_type):
            gateway.is_active = is_active

    async def count_active(self) -> int:
        return len(await self.get_active())


def sorted_gateways(gateways: list[PaymentGatewayDto]) -> list[PaymentGatewayDto]:
    return sorted(gateways, key=lambda gateway: gateway.order_index)


class InMemoryTransactionDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create(self, transaction: TransactionDto) -> TransactionDto:
        transaction.id = transaction.id or self.store.next_id("transaction")
        self.store.transactions[transaction.payment_id] = transaction
        return transaction

    async def get_by_payment_id(self, payment_id: UUID) -> Optional[TransactionDto]:
        return self.store.transactions.get(payment_id)

    async def get_by_user(self, telegram_id: int) -> list[TransactionDto]:
        return [t for t in self.store.transactions.values() if t.user_telegram_id == telegram_id]

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[TransactionDto]:
        return list(self.store.transactions.values())[offset : offset + limit]

    async def get_by_status(self, status: TransactionStatus) -> list[TransactionDto]:
        return [t for t in self.store.transactions.values() if t.status == status]

    async def update_status(self, payment_id: UUID, status: TransactionStatus) -> Optional[TransactionDto]:
        if transaction := self.store.transactions.get(payment_id):
            transaction.status = status
        return transaction

    async def exists(self, payment_id: UUID) -> bool:
        return payment_id in self.store.transactions

    async def cancel_old(self, minutes: int = 30) -> int:
        return 0

    async def count(self) -> int:
        return len(self.store.transactions)

    async def count_paying_users(self) -> int:
        return len({t.user_telegram_id for t in self.store.transactions.values()})

    async def count_total(self) -> int:
        return await self.count()

    async def count_completed(self) -> int:
        return len([t for t in self.store.transactions.values() if t.is_completed])

    async def count_free(self) -> int:
        return len([t for t in self.store.transactions.values() if t.pricing.is_free])

    async def get_gateway_stats(self) -> list[GatewayStatsDto]:
        return [GatewayStatsDto(PaymentGatewayType.TELEGRAM_STARS, Decimal(0), Decimal(0), Decimal(0), Decimal(0), 0, Decimal(0), len(self.store.transactions), 0, 0)]

    async def get_plan_income(self) -> list[PlanIncomeDto]:
        return [PlanIncomeDto(1, Currency.RUB, 0)]

    async def get_user_payment_stats(self, telegram_id: int) -> tuple[Optional[datetime], list[UserPaymentStatsDto]]:
        return None, []


class InMemoryReferralDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create_referral(self, referral: ReferralDto) -> ReferralDto:
        referral.id = referral.id or self.store.next_id("referral")
        self.store.referrals.append(referral)
        return referral

    async def get_by_referred_id(self, referred_id: int) -> Optional[ReferralDto]:
        return next((r for r in self.store.referrals if r.referred.telegram_id == referred_id), None)

    async def get_referrals_count(self, referrer_id: int) -> int:
        return len([r for r in self.store.referrals if r.referrer.telegram_id == referrer_id])

    async def get_referrals_list(self, referrer_id: int, limit: int = 100, offset: int = 0) -> list[ReferralDto]:
        return [r for r in self.store.referrals if r.referrer.telegram_id == referrer_id][offset : offset + limit]

    async def create_reward(self, reward: ReferralRewardDto, referral_id: int) -> ReferralRewardDto:
        reward.id = reward.id or self.store.next_id("reward")
        self.store.rewards.append(reward)
        return reward

    async def get_pending_rewards(self) -> list[ReferralRewardDto]:
        return [r for r in self.store.rewards if not r.is_issued]

    async def mark_reward_as_issued(self, reward_id: int) -> None:
        for reward in self.store.rewards:
            if reward.id == reward_id:
                reward.is_issued = True

    async def get_total_rewards_amount(self, telegram_id: int, reward_type: ReferralRewardType) -> int:
        return sum(r.amount for r in self.store.rewards if r.user_telegram_id == telegram_id and r.type == reward_type)

    async def get_referral_chain(self, referred_id: int) -> tuple[Optional[ReferralDto], Optional[ReferralDto]]:
        return await self.get_by_referred_id(referred_id), None

    async def get_stats(self) -> ReferralStatisticsDto:
        return ReferralStatisticsDto(0, 0, 0, 0, 0, 0, 0, 0)

    async def get_user_referral_stats(self, telegram_id: int) -> dict:
        return {"referrals_count": 0, "payments_count": 0}

    async def get_referrals_with_payment_count(self, referrer_id: int) -> int:
        return 0


class InMemoryBroadcastDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create(self, broadcast: BroadcastDto) -> BroadcastDto:
        broadcast.id = broadcast.id or self.store.next_id("broadcast")
        self.store.broadcasts[broadcast.task_id] = broadcast
        return broadcast

    async def get_by_task_id(self, task_id: UUID) -> Optional[BroadcastDto]:
        return self.store.broadcasts.get(task_id)

    async def get_all(self) -> list[BroadcastDto]:
        return list(self.store.broadcasts.values())

    async def update_status(self, task_id: UUID, status: BroadcastStatus) -> None:
        if broadcast := self.store.broadcasts.get(task_id):
            broadcast.status = status

    async def add_messages(self, task_id: UUID, messages: list[BroadcastMessageDto]) -> list[BroadcastMessageDto]:
        if broadcast := self.store.broadcasts.get(task_id):
            broadcast.messages.extend(messages)
        return messages

    async def update_message_status(self, task_id: UUID, telegram_id: int, status: BroadcastMessageStatus, message_id: Optional[int] = None) -> None:
        return None

    async def update_stats(self, task_id: UUID, success_count: int, failed_count: int) -> None:
        if broadcast := self.store.broadcasts.get(task_id):
            broadcast.success_count = success_count
            broadcast.failed_count = failed_count

    async def get_active(self) -> list[BroadcastDto]:
        return [b for b in self.store.broadcasts.values() if b.status == BroadcastStatus.PROCESSING]

    async def delete_old(self, days: int = 7) -> int:
        return 0

    async def bulk_update_messages(self, messages: list[BroadcastMessageDto]) -> None:
        return None


class InMemoryWebhookDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def is_hash_exists(self, bot_id: int, webhook_hash: str) -> bool:
        return webhook_hash in self.store.webhooks.get(bot_id, set())

    async def save_hash(self, bot_id: int, webhook_hash: str) -> None:
        self.store.webhooks.setdefault(bot_id, set()).add(webhook_hash)

    async def clear_all_hashes(self, bot_id: int) -> None:
        self.store.webhooks.pop(bot_id, None)

    async def get_current_hash(self, bot_id: int) -> Optional[str]:
        hashes = self.store.webhooks.get(bot_id, set())
        return next(iter(hashes), None)


class InMemoryWaitlistDao:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def exists(self, telegram_id: int) -> bool:
        return telegram_id in self.store.waitlist

    async def add(self, telegram_id: int) -> None:
        self.store.waitlist.add(telegram_id)

    async def get_members(self) -> list[int]:
        return list(self.store.waitlist)

    async def clear(self) -> None:
        self.store.waitlist.clear()


class InMemoryRemnawave:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def try_connection(self) -> Version:
        return Version("9.9.9")

    async def create_user(self, user: UserDto, plan: Optional[PlanSnapshotDto] = None, subscription: Optional[SubscriptionDto] = None) -> Any:
        return _fake_remna_user(user.telegram_id, subscription.user_remna_id if subscription else uuid4())

    async def update_user(self, user: UserDto, uuid: UUID, plan: Optional[PlanSnapshotDto] = None, subscription: Optional[SubscriptionDto] = None, reset_traffic: bool = False) -> Any:
        return _fake_remna_user(user.telegram_id, uuid)

    async def delete_user(self, uuid: UUID) -> bool:
        return True

    async def get_user_by_uuid(self, uuid: UUID) -> Optional[Any]:
        return _fake_remna_user(0, uuid)

    async def get_user_by_telegram_id(self, telegram_id: int) -> list[Any]:
        return [_fake_remna_user(telegram_id, uuid4())]

    async def get_devices(self, uuid: UUID) -> list[Any]:
        return [SimpleNamespace(hwid="preview-device-hwid", platform="ios", device_model="iPhone", user_agent="Preview")]

    async def delete_device(self, user_uuid: UUID, hwid: str) -> Optional[int]:
        return 0

    async def reset_traffic(self, uuid: UUID) -> Optional[Any]:
        return _fake_remna_user(0, uuid)

    async def revoke_subscription(self, uuid: UUID) -> None:
        return None

    def apply_sync(self, target: Any, source: Any) -> Any:
        return target


def _fake_remna_user(telegram_id: int, uuid: UUID) -> Any:
    return SimpleNamespace(
        uuid=uuid,
        username=f"preview-{telegram_id}",
        telegram_id=telegram_id,
        status=SubscriptionStatus.ACTIVE,
        expire_at=days_to_datetime(30),
        subscription_url="https://example.com/sub/preview",
        traffic_limit_bytes=100 * 1024**3,
        hwid_device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        tag=None,
        active_internal_squads=[],
        external_squad_uuid=None,
    )


class InMemoryRemnawaveSDK:
    def __init__(self) -> None:
        self.system = _SystemApi()
        self.hosts = _HostsApi()
        self.nodes = _NodesApi()
        self.inbounds = _InboundsApi()
        self.users = _UsersApi()
        self.hwid = _HwidApi()


class _SystemApi:
    async def get_metadata(self) -> Any:
        return SimpleNamespace(version="9.9.9")

    async def get_stats(self) -> Any:
        return SimpleNamespace(
            cpu=SimpleNamespace(cores=4),
            memory=SimpleNamespace(used=512 * 1024**2, total=2 * 1024**3),
            uptime=3600,
            users=SimpleNamespace(
                total_users=1,
                status_counts={"ACTIVE": 1, "DISABLED": 0, "LIMITED": 0, "EXPIRED": 0},
            ),
            online_stats=SimpleNamespace(last_day=1, last_week=1, never_online=0, online_now=1),
        )


class _HostsApi:
    async def get_all_hosts(self) -> list[Any]:
        return [SimpleNamespace(remark="Preview host", is_disabled=False, address="preview.local", port=443, inbound_uuid=uuid4())]


class _NodesApi:
    async def get_all_nodes(self) -> list[Any]:
        return [SimpleNamespace(country_code="NL", name="Preview node", is_connected=True, address="node.local", port=443, xray_uptime=3600, users_online=1, traffic_used_bytes=1024**3, traffic_limit_bytes=100 * 1024**3)]


class _InboundsApi:
    async def get_all_inbounds(self) -> Any:
        return SimpleNamespace(inbounds=[SimpleNamespace(uuid=uuid4(), tag="preview", type="vless", port=443, network="tcp", security="reality")])


class _UsersApi:
    async def get_user_by_uuid(self, uuid: UUID) -> Any:
        return _fake_remna_user(0, uuid)

    async def get_users_by_telegram_id(self, telegram_id: int) -> Any:
        return SimpleNamespace(root=[_fake_remna_user(telegram_id, uuid4())])

    async def create_user(self, request: Any) -> Any:
        return _fake_remna_user(getattr(request, "telegram_id", 0), getattr(request, "uuid", uuid4()))

    async def update_user(self, request: Any) -> Any:
        return _fake_remna_user(getattr(request, "telegram_id", 0), getattr(request, "uuid", uuid4()))

    async def delete_user(self, uuid: UUID) -> Any:
        return SimpleNamespace(is_deleted=True)

    async def reset_user_traffic(self, uuid: UUID) -> Any:
        return _fake_remna_user(0, uuid)

    async def revoke_user_subscription(self, uuid: UUID) -> None:
        return None


class _HwidApi:
    async def get_hwid_user(self, uuid: UUID) -> Any:
        return SimpleNamespace(total=1, devices=[SimpleNamespace(hwid="preview-device-hwid", platform="ios", device_model="iPhone", user_agent="Preview")])

    async def delete_hwid_to_user(self, request: Any) -> Any:
        return SimpleNamespace(total=0)
