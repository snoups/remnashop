from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import pytest
from remnapy import RemnawaveSDK
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.db.models.subscription import Subscription
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, Locale, PlanType, PurchaseType, Role, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.plans.dto import CreatePlanDto, PlanDto, SetPlanDurationDto, SetPlanDurationsDto
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    PurchaseRollbackDto,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.subscriptions.rollback import PurchaseRollbackService
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore
from tests.modules.subscriptions.factories import make_eligibility, snapshot_from_plan

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


@pytest.fixture
def purchase(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
    pricing_repository: PricingRepository,
) -> PurchaseSubscriptionUseCase:
    return PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        pricing_repository,
        idempotency_repository,
        UserRepository(subscription_repository.session),
        AppConfig.get(),
    )


@pytest.fixture
def service(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    pricing_repository: PricingRepository,
    remnawave_sdk: RemnawaveSDK,
    idempotency_repository: PurchaseIdempotencyRepository,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
) -> PurchaseRollbackService:
    return PurchaseRollbackService(
        subscription_repository,
        user_repository,
        SubscriptionLifecycleService(subscription_repository),
        PanelSubscriptionRevoker(subscription_repository, remnawave_sdk),
        pricing_repository,
        remnawave_sdk,
        idempotency_repository,
        event_publisher,
        uow,
    )


async def _plan(plan_repository: PlanRepository, code: str, device_limit: int = 2) -> PlanDto:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=code,
            name=code,
            type=PlanType.BOTH,
            traffic_limit=50,
            device_limit=device_limit,
        )
    )
    return await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("300"))],
        )
    )


async def _buy(
    purchase: PurchaseSubscriptionUseCase,
    buyer: UserDto,
    plan: PlanDto,
    purchase_type: PurchaseType,
    target: Optional[int] = None,
) -> SubscriptionDto:
    return await purchase(
        OWNER,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("300"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300"),
            currency=Currency.RUB,
            purchase_type=purchase_type,
            target_subscription_id=target,
        ),
    )


def _data(
    purchase_type: PurchaseType,
    fulfilled: Optional[int],
    target: Optional[int] = None,
    has_later_paid_order: bool = False,
) -> PurchaseRollbackDto:
    return PurchaseRollbackDto(
        purchase_type=purchase_type,
        target_subscription_id=target,
        fulfilled_subscription_id=fulfilled,
        duration_days=30,
        price_paid=Decimal("300"),
        currency=Currency.RUB,
        has_later_paid_order=has_later_paid_order,
    )


def _panel_expire(store: FakeUserStore, panel_id: int) -> datetime:
    return datetime.fromisoformat(store[panel_id]["expireAt"].replace("Z", "+00:00"))


async def _last_event(session: AsyncSession) -> Optional[str]:
    return await session.scalar(
        select(EventOutboxEntry.event_type).order_by(EventOutboxEntry.id.desc()).limit(1)
    )


async def _buyer(user_repository: UserRepository, telegram_id: int) -> UserDto:
    return await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))


async def test_rollback_new_revokes_the_subscription(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
) -> None:
    buyer = await _buyer(user_repository, 9101)
    bought = await _buy(purchase, buyer, await _plan(plan_repository, "rb_new"), PurchaseType.NEW)

    await service.rollback(OWNER, _data(PurchaseType.NEW, bought.id))

    after = await subscription_repository.get_by_id(bought.id)
    assert after.status is SubscriptionStatus.DELETED
    assert bought.remnawave_user_id not in remnawave_store
    assert await _last_event(subscription_repository.session) == "SubscriptionEditedEvent"


async def test_rollback_renew_shortens_db_and_panel(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
) -> None:
    buyer = await _buyer(user_repository, 9102)
    plan = await _plan(plan_repository, "rb_renew")
    bought = await _buy(purchase, buyer, plan, PurchaseType.NEW)
    renewed = await _buy(purchase, buyer, plan, PurchaseType.RENEW, target=bought.id)

    await service.rollback(OWNER, _data(PurchaseType.RENEW, renewed.id, target=renewed.id))

    after = await subscription_repository.get_by_id(renewed.id)
    assert after.status is SubscriptionStatus.ACTIVE
    assert after.expire_at == renewed.expire_at - timedelta(days=30)
    assert after.plan_snapshot.effective_credit_paid == Decimal("300")
    assert after.plan_snapshot.effective_credit_days == 30
    panel_expire = _panel_expire(remnawave_store, renewed.remnawave_user_id)
    assert abs(panel_expire - after.expire_at) < timedelta(seconds=1)
    assert await _last_event(subscription_repository.session) == "SubscriptionEditedEvent"


async def test_rollback_change_restores_old_and_deletes_new(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
) -> None:
    buyer = await _buyer(user_repository, 9103)
    old = await _buy(
        purchase, buyer, await _plan(plan_repository, "rb_chg_old", 2), PurchaseType.NEW
    )
    new_plan = await _plan(plan_repository, "rb_chg_new", 5)
    new = await _buy(purchase, buyer, new_plan, PurchaseType.CHANGE, target=old.id)
    assert remnawave_store[old.remnawave_user_id]["hwidDeviceLimit"] == 5

    await service.rollback(OWNER, _data(PurchaseType.CHANGE, new.id, target=old.id))

    old_after = await subscription_repository.get_by_id(old.id)
    new_after = await subscription_repository.get_by_id(new.id)
    assert old_after.status is SubscriptionStatus.ACTIVE
    assert new_after.status is SubscriptionStatus.DELETED
    panel = remnawave_store[old.remnawave_user_id]
    assert panel["hwidDeviceLimit"] == 2
    assert abs(_panel_expire(remnawave_store, old.remnawave_user_id) - old.expire_at) < timedelta(
        seconds=1
    )
    assert await _last_event(subscription_repository.session) == "SubscriptionEditedEvent"


async def test_rollback_change_blocked_when_new_deleted(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    buyer = await _buyer(user_repository, 9104)
    old = await _buy(purchase, buyer, await _plan(plan_repository, "rb_blk_old"), PurchaseType.NEW)
    new_plan = await _plan(plan_repository, "rb_blk_new")
    new = await _buy(purchase, buyer, new_plan, PurchaseType.CHANGE, target=old.id)
    await subscription_repository.mark_deleted(new.id)
    data = _data(PurchaseType.CHANGE, new.id, target=old.id)

    result = await service.preview(data)
    assert result.available is False
    assert result.blocked_reason == "changed_again"
    with pytest.raises(ConflictError) as exc:
        await service.rollback(OWNER, data)
    assert exc.value.code is ErrorCode.SUBSCRIPTION_ROLLBACK_BLOCKED


async def test_rollback_change_blocked_by_later_paid_order(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    buyer = await _buyer(user_repository, 9105)
    old = await _buy(purchase, buyer, await _plan(plan_repository, "rb_lat_old"), PurchaseType.NEW)
    new_plan = await _plan(plan_repository, "rb_lat_new")
    new = await _buy(purchase, buyer, new_plan, PurchaseType.CHANGE, target=old.id)

    with pytest.raises(ConflictError) as exc:
        await service.rollback(
            OWNER, _data(PurchaseType.CHANGE, new.id, target=old.id, has_later_paid_order=True)
        )
    assert exc.value.code is ErrorCode.SUBSCRIPTION_ROLLBACK_BLOCKED
    after = await subscription_repository.get_by_id(new.id)
    assert after.status is SubscriptionStatus.ACTIVE


async def test_preview_flags_an_expired_old_term(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    buyer = await _buyer(user_repository, 9106)
    old = await _buy(purchase, buyer, await _plan(plan_repository, "rb_exp_old"), PurchaseType.NEW)
    new_plan = await _plan(plan_repository, "rb_exp_new")
    new = await _buy(purchase, buyer, new_plan, PurchaseType.CHANGE, target=old.id)
    await subscription_repository.session.execute(
        update(Subscription)
        .where(Subscription.id == old.id)
        .values(expire_at=datetime_now() - timedelta(days=1))
    )
    data = _data(PurchaseType.CHANGE, new.id, target=old.id)

    result = await service.preview(data)
    assert result.available is True
    assert result.blocked_reason is None
    assert result.old_term_expired is True

    await service.rollback(OWNER, data)
    old_after = await subscription_repository.get_by_id(old.id)
    assert old_after.status is SubscriptionStatus.EXPIRED


async def test_preview_not_provisioned(service: PurchaseRollbackService) -> None:
    result = await service.preview(_data(PurchaseType.NEW, None))
    assert result.available is False
    assert result.blocked_reason == "not_provisioned"
    assert result.old_term_expired is False


async def test_preview_renew_of_a_deleted_subscription(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    buyer = await _buyer(user_repository, 9107)
    bought = await _buy(purchase, buyer, await _plan(plan_repository, "rb_del"), PurchaseType.NEW)
    await subscription_repository.mark_deleted(bought.id)

    result = await service.preview(_data(PurchaseType.RENEW, bought.id, target=bought.id))
    assert result.blocked_reason == "subscription_deleted"


async def test_rollback_new_blocked_by_later_paid_order(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    buyer = await _buyer(user_repository, 9108)
    bought = await _buy(
        purchase, buyer, await _plan(plan_repository, "rb_new_lat"), PurchaseType.NEW
    )
    data = _data(PurchaseType.NEW, bought.id, has_later_paid_order=True)

    result = await service.preview(data)
    assert result.blocked_reason == "renewed_or_changed_later"
    with pytest.raises(ConflictError) as exc:
        await service.rollback(OWNER, data)
    assert exc.value.code is ErrorCode.SUBSCRIPTION_ROLLBACK_BLOCKED
    after = await subscription_repository.get_by_id(bought.id)
    assert after.status is SubscriptionStatus.ACTIVE


async def test_renew_rollback_racing_a_change_restores_the_live_row_on_the_panel(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _buyer(user_repository, 9109)
    plan = await _plan(plan_repository, "rb_race")
    bought = await _buy(purchase, buyer, plan, PurchaseType.NEW)
    renewed = await _buy(purchase, buyer, plan, PurchaseType.RENEW, target=bought.id)
    live_expire = datetime_now() + timedelta(days=90)
    original_update = remnawave_sdk.users.update_user
    raced: list[SubscriptionDto] = []

    async def update_then_race(request: object) -> object:
        response = await original_update(request)  # type: ignore[arg-type]
        if not raced:
            # a plan change commits between the panel call and the row lock
            await subscription_repository.mark_deleted(renewed.id)
            raced.append(
                await subscription_repository.create(
                    CreateSubscriptionDto(
                        user_id=buyer.id,
                        remnawave_user_id=renewed.remnawave_user_id,
                        status=SubscriptionStatus.ACTIVE,
                        traffic_limit=50,
                        device_limit=7,
                        expire_at=live_expire,
                        url="https://example.com/sub/race",
                        plan_snapshot=renewed.plan_snapshot,
                    )
                )
            )
            await subscription_repository.session.commit()
        return response

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_then_race)

    with pytest.raises(ConflictError) as exc:
        await service.rollback(OWNER, _data(PurchaseType.RENEW, renewed.id, target=renewed.id))
    assert exc.value.code is ErrorCode.SUBSCRIPTION_ROLLBACK_BLOCKED
    panel = remnawave_store[renewed.remnawave_user_id]
    assert panel["hwidDeviceLimit"] == 7
    panel_expire = _panel_expire(remnawave_store, renewed.remnawave_user_id)
    assert abs(panel_expire - live_expire) < timedelta(seconds=1)


async def test_rollback_undoes_a_renewal_that_reached_only_the_panel(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _buyer(user_repository, 9120)
    bought = await _buy(purchase, buyer, await _plan(plan_repository, "rb_pin"), PurchaseType.NEW)
    # the worker pinned and wrote the extension, then died before the database renew
    pinned = bought.expire_at + timedelta(days=30)
    remnawave_store[bought.remnawave_user_id]["expireAt"] = pinned.isoformat()

    async def _pinned(key: str) -> Optional[datetime]:
        return pinned if key == "order-key" else None

    monkeypatch.setattr(service._idempotency, "find_pending_renew_expire_at", _pinned)
    data = replace(_data(PurchaseType.RENEW, None, target=bought.id), idempotency_key="order-key")

    assert (await service.preview(data)).available
    await service.rollback(OWNER, data)

    panel_expire = _panel_expire(remnawave_store, bought.remnawave_user_id)
    assert abs(panel_expire - bought.expire_at) < timedelta(seconds=1)
    after = await subscription_repository.get_by_id(bought.id)
    assert after.expire_at == bought.expire_at


async def _renew_unlimited(
    purchase: PurchaseSubscriptionUseCase, buyer: UserDto, plan: PlanDto, target: int
) -> SubscriptionDto:
    return await purchase(
        OWNER,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("5000"), currency=Currency.RUB, duration_days=0
            ),
            duration_days=0,
            price_paid=Decimal("5000"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=target,
        ),
    )


def _unlimited_data(fulfilled: Optional[int], target: int) -> PurchaseRollbackDto:
    return replace(
        _data(PurchaseType.RENEW, fulfilled, target=target),
        duration_days=0,
        price_paid=Decimal("5000"),
    )


async def test_refund_unlimited_renewal_restores_previous_expiry_and_credit(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
) -> None:
    # nothing but the snapshot is read, so it holds after the idempotency row is pruned
    buyer = await _buyer(user_repository, 9130)
    plan = await _plan(plan_repository, "rb_forever")
    bought = await _buy(purchase, buyer, plan, PurchaseType.NEW)
    renewed = await _renew_unlimited(purchase, buyer, plan, bought.id)
    assert renewed.is_unlimited

    await service.rollback(OWNER, _unlimited_data(renewed.id, renewed.id))

    after = await subscription_repository.get_by_id(renewed.id)
    assert after.expire_at == bought.expire_at
    assert after.status is SubscriptionStatus.ACTIVE
    assert after.plan_snapshot.effective_credit_paid == Decimal("300")
    assert after.plan_snapshot.effective_credit_days == 30
    assert after.plan_snapshot.unlimited_from is None
    panel_expire = _panel_expire(remnawave_store, renewed.remnawave_user_id)
    assert abs(panel_expire - bought.expire_at) < timedelta(seconds=1)


async def test_refund_pending_unlimited_renewal_restores_row_expiry(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    remnawave_store: FakeUserStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _buyer(user_repository, 9131)
    bought = await _buy(
        purchase, buyer, await _plan(plan_repository, "rb_forever_pin"), PurchaseType.NEW
    )
    pinned = bought.expire_at.replace(year=2099)
    remnawave_store[bought.remnawave_user_id]["expireAt"] = pinned.isoformat()

    async def _pinned(key: str) -> Optional[datetime]:
        return pinned if key == "order-key" else None

    monkeypatch.setattr(service._idempotency, "find_pending_renew_expire_at", _pinned)
    data = replace(_unlimited_data(None, bought.id), idempotency_key="order-key")

    await service.rollback(OWNER, data)

    panel_expire = _panel_expire(remnawave_store, bought.remnawave_user_id)
    assert abs(panel_expire - bought.expire_at) < timedelta(seconds=1)


async def test_refund_of_a_finite_renewal_under_a_later_unlimited_one_keeps_it_unlimited(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
) -> None:
    # the refunded days come off the term the unlimited renewal replaced, not off 2099
    buyer = await _buyer(user_repository, 9132)
    plan = await _plan(plan_repository, "rb_finite_under_forever")
    bought = await _buy(purchase, buyer, plan, PurchaseType.NEW)
    month = await _buy(purchase, buyer, plan, PurchaseType.RENEW, target=bought.id)
    forever = await _renew_unlimited(purchase, buyer, plan, bought.id)

    await service.rollback(OWNER, _data(PurchaseType.RENEW, month.id, target=month.id))

    after = await subscription_repository.get_by_id(bought.id)
    assert after.expire_at == forever.expire_at
    assert _panel_expire(remnawave_store, bought.remnawave_user_id).year == 2099
    assert after.plan_snapshot.credit_paid == Decimal("5000")
    assert after.plan_snapshot.unlimited_from == bought.expire_at
    assert after.plan_snapshot.unlimited_from_credit_paid == Decimal("300")
    assert after.plan_snapshot.unlimited_from_credit_days == 30

    await service.rollback(OWNER, _unlimited_data(forever.id, forever.id))

    restored = await subscription_repository.get_by_id(bought.id)
    assert restored.expire_at == bought.expire_at
    assert restored.plan_snapshot.effective_credit_paid == Decimal("300")


async def test_refund_of_an_unlimited_renewal_made_finite_since_is_blocked(
    purchase: PurchaseSubscriptionUseCase,
    service: PurchaseRollbackService,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
) -> None:
    # the term it replaced is stale: putting it back would drop what came after
    buyer = await _buyer(user_repository, 9133)
    plan = await _plan(plan_repository, "rb_forever_made_finite")
    bought = await _buy(purchase, buyer, plan, PurchaseType.NEW)
    forever = await _renew_unlimited(purchase, buyer, plan, bought.id)
    finite = datetime_now() + timedelta(days=200)
    await subscription_repository.session.execute(
        update(Subscription).where(Subscription.id == forever.id).values(expire_at=finite)
    )
    remnawave_store[forever.remnawave_user_id]["expireAt"] = finite.isoformat()
    data = _unlimited_data(forever.id, forever.id)

    preview = await service.preview(data)
    with pytest.raises(ConflictError):
        await service.rollback(OWNER, data)

    assert preview.blocked_reason == "renewed_or_changed_later"
    assert (await subscription_repository.get_by_id(forever.id)).expire_at == finite
