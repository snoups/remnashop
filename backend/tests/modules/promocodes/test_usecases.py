from datetime import timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.db.models.plan import Plan
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AddOnType,
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseType,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreateAddOnDto,
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import convert_for_report
from app.modules.pricing.repository import PricingRepository
from app.modules.promocodes.dto import (
    ActivatePromocodeDto,
    CreatePromocodeDto,
    ListPromocodeActivatedUsersDto,
    ListPromocodesDto,
    UpdatePromocodeDto,
)
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import (
    ActivatePromocodeUseCase,
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    GetPromocodeSummaryUseCase,
    ListPromocodeActivatedUsersUseCase,
    ListPromocodesUseCase,
    UpdatePromocodeUseCase,
)
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto, PurchaseSubscriptionDto
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.subscriptions.factories import (
    make_eligibility,
    make_plan_snapshot,
    snapshot_from_plan,
)

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def test_owner_can_create_duration_promocode(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )

    promo = await use_case(
        OWNER,
        CreatePromocodeDto(code="ADMIN10", reward_type=PromocodeRewardType.DURATION, reward=10),
    )

    assert promo.code == "ADMIN10"
    assert promo.is_active is True


async def test_regular_user_cannot_create_promocode(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            CreatePromocodeDto(code="X", reward_type=PromocodeRewardType.DURATION, reward=10),
        )


async def test_create_duration_promocode_requires_positive_reward(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            CreatePromocodeDto(code="ZERO", reward_type=PromocodeRewardType.DURATION, reward=0),
        )


@pytest.mark.parametrize(
    "reward_type", [PromocodeRewardType.PERSONAL_DISCOUNT, PromocodeRewardType.PURCHASE_DISCOUNT]
)
@pytest.mark.parametrize("reward", [None, 0, 101])
async def test_create_discount_promocode_requires_percent_in_range(
    promocode_repository: PromocodeRepository,
    uow,
    event_publisher,
    reward_type: PromocodeRewardType,
    reward: Optional[int],
) -> None:
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER, CreatePromocodeDto(code="DISC", reward_type=reward_type, reward=reward)
        )


async def test_create_traffic_promocode_requires_matching_addon_type(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    addon_repository = AddOnRepository(promocode_repository.session)
    devices_addon = await addon_repository.create(
        CreateAddOnDto(
            name="Bonus devices", type=AddOnType.DEVICES, amount=2, base_price=Decimal("0.99")
        )
    )
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        addon_repository,
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            CreatePromocodeDto(
                code="MISMATCH",
                reward_type=PromocodeRewardType.TRAFFIC,
                reward_addon_id=devices_addon.id,
            ),
        )


async def test_create_traffic_promocode_with_matching_addon_succeeds(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    addon_repository = AddOnRepository(promocode_repository.session)
    traffic_addon = await addon_repository.create(
        CreateAddOnDto(
            name="Bonus traffic", type=AddOnType.TRAFFIC, amount=50, base_price=Decimal("1.99")
        )
    )
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        addon_repository,
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )

    promo = await use_case(
        OWNER,
        CreatePromocodeDto(
            code="TRAFFIC50",
            reward_type=PromocodeRewardType.TRAFFIC,
            reward_addon_id=traffic_addon.id,
        ),
    )

    assert promo.reward_addon_id == traffic_addon.id


async def test_create_subscription_promocode_requires_duration(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    plan_repository = PlanRepository(promocode_repository.session)
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="promo-plan",
            name="Promo Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        plan_repository,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            CreatePromocodeDto(
                code="NODURATION",
                reward_type=PromocodeRewardType.SUBSCRIPTION,
                reward_plan_id=plan.id,
            ),
        )


async def test_update_promocode_deactivates(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    create_use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )
    created = await create_use_case(
        OWNER, CreatePromocodeDto(code="TOGGLE", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    update_use_case = UpdatePromocodeUseCase(promocode_repository, uow, event_publisher)

    updated = await update_use_case(
        OWNER, UpdatePromocodeDto(promocode_id=created.id, is_active=False)
    )

    assert updated.is_active is False


async def test_update_promocode_rejects_emptying_an_allowed_promocodes_allowlist(
    promocode_repository: PromocodeRepository, uow, event_publisher
) -> None:
    # the patch carries no availability, so the merged state is validated: an
    # ALLOWED promocode with an empty allowlist would be redeemable by nobody
    create_use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )
    created = await create_use_case(
        OWNER,
        CreatePromocodeDto(
            code="ALLOWLIST",
            reward_type=PromocodeRewardType.DURATION,
            reward=5,
            availability=PromocodeAvailability.ALLOWED,
            allowed_user_ids=[1],
        ),
    )
    update_use_case = UpdatePromocodeUseCase(promocode_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await update_use_case(
            OWNER, UpdatePromocodeDto(promocode_id=created.id, allowed_user_ids=[])
        )

    unchanged = await promocode_repository.get_by_id(created.id)
    assert unchanged.allowed_user_ids == [1]


async def test_delete_promocode(
    promocode_repository: PromocodeRepository,
    user_repository: UserRepository,
    uow,
    event_publisher,
) -> None:
    create_use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
        event_publisher,
    )
    created = await create_use_case(
        OWNER, CreatePromocodeDto(code="DELME", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    delete_use_case = DeletePromocodeUseCase(
        promocode_repository, user_repository, uow, event_publisher
    )

    await delete_use_case(OWNER, created.id)

    assert await promocode_repository.get_by_code("DELME") is None


async def test_list_promocodes_requires_view_permission(
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListPromocodesUseCase(promocode_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, ListPromocodesDto())


async def test_generate_promocode_code_returns_unique_code(
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
) -> None:
    use_case = GeneratePromocodeCodeUseCase(promocode_repository, uow)

    code = await use_case(OWNER)

    assert len(code) == 10
    assert await promocode_repository.get_by_code(code) is None


def _activate_use_case(
    promocode_repository,
    subscription_repository,
    user_repository,
    remnawave_sdk,
    uow,
    event_publisher,
    grant_addon_dispatch: Optional[RecordingDispatch] = None,
) -> ActivatePromocodeUseCase:
    purchase_use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        PurchaseIdempotencyRepository(subscription_repository.session),
    )
    return ActivatePromocodeUseCase(
        promocode_repository,
        subscription_repository,
        PlanRepository(promocode_repository.session),
        make_eligibility(promocode_repository.session),
        user_repository,
        purchase_use_case,
        uow,
        event_publisher,
        grant_addon_dispatch or RecordingDispatch(),
    )


async def test_activate_unknown_code_raises_not_found(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(NotFoundError):
        await use_case(REGULAR_USER, ActivatePromocodeDto(code="NOPE"))


async def test_activate_subscription_reward_creates_new_subscription(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    # promocode_activations.user_id is a real FK and REGULAR_USER (id=2) has no
    # row; the other activate tests fail before claim_activation
    actor = await user_repository.create(CreateUserDto(name="Bob", telegram_id=301))
    plan_repository = PlanRepository(promocode_repository.session)
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="free-plan",
            name="Free Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    await promocode_repository.create(
        CreatePromocodeDto(
            code="FREEPLAN",
            reward_type=PromocodeRewardType.SUBSCRIPTION,
            reward_plan_id=plan.id,
            reward_duration_days=30,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case(actor, ActivatePromocodeDto(code="FREEPLAN"))

    active = await subscription_repository.get_active_by_user(actor.id)
    assert len(active) == 1
    assert active[0].plan_snapshot.plan_id == plan.id


async def test_activate_subscription_reward_for_unavailable_plan_does_not_spend_the_code(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    # a plan the actor can't get must not burn a single-use code they could
    # redeem once the plan is back
    actor = await user_repository.create(CreateUserDto(name="Carol", telegram_id=305))
    plan_repository = PlanRepository(promocode_repository.session)
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="paused-plan",
            name="Paused Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="PAUSEDPLAN",
            reward_type=PromocodeRewardType.SUBSCRIPTION,
            reward_plan_id=plan.id,
            reward_duration_days=30,
            max_activations=1,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(actor, ActivatePromocodeDto(code="PAUSEDPLAN"))
    assert await promocode_repository.get_activations_count(promo.id) == 0

    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    await use_case(actor, ActivatePromocodeDto(code="PAUSEDPLAN"))
    assert len(await subscription_repository.get_active_by_user(actor.id)) == 1


async def test_activate_subscription_reward_requires_a_referrer_for_invited_plan(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    referral_repository: ReferralRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    unreferred_actor = await user_repository.create(
        CreateUserDto(name="Unreferred", telegram_id=302)
    )
    referred_actor = await user_repository.create(CreateUserDto(name="Referred", telegram_id=303))
    referrer = await user_repository.create(CreateUserDto(name="Referrer", telegram_id=304))
    await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=referred_actor.id, level=1
    )
    plan_repository = PlanRepository(promocode_repository.session)
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="invited-plan",
            name="Invited Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=plan.id,
            availability=PlanAvailability.INVITED,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="INVITEDPLAN",
            reward_type=PromocodeRewardType.SUBSCRIPTION,
            reward_plan_id=plan.id,
            reward_duration_days=30,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(unreferred_actor, ActivatePromocodeDto(code="INVITEDPLAN"))

    await use_case(referred_actor, ActivatePromocodeDto(code="INVITEDPLAN"))

    active = await subscription_repository.get_active_by_user(referred_actor.id)
    assert len(active) == 1
    assert active[0].plan_snapshot.plan_id == plan.id


async def test_activate_new_availability_allows_a_user_with_no_purchase_history(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Fresh", telegram_id=910))
    await promocode_repository.create(
        CreatePromocodeDto(
            code="NEWONLY",
            reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
            reward=10,
            availability=PromocodeAvailability.NEW,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case(actor, ActivatePromocodeDto(code="NEWONLY"))  # must not raise


async def test_activate_new_availability_denies_a_user_with_a_deleted_subscription(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    # "new" means never bought a non-trial subscription, so a DELETED row
    # still disqualifies
    actor = await user_repository.create(CreateUserDto(name="Returning", telegram_id=911))
    await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=actor.id,
            remnawave_user_id=911_001,
            status=SubscriptionStatus.DELETED,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() - timedelta(days=1),
            url="https://example.com/sub/911",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="NEWONLY2",
            reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
            reward=10,
            availability=PromocodeAvailability.NEW,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(actor, ActivatePromocodeDto(code="NEWONLY2"))


async def test_activate_existing_availability_denies_a_user_with_no_purchase_history(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Fresh2", telegram_id=912))
    await promocode_repository.create(
        CreatePromocodeDto(
            code="EXISTONLY",
            reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
            reward=10,
            availability=PromocodeAvailability.EXISTING,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(actor, ActivatePromocodeDto(code="EXISTONLY"))


async def test_activate_existing_availability_allows_a_user_with_a_deleted_subscription(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Returning2", telegram_id=913))
    await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=actor.id,
            remnawave_user_id=913_001,
            status=SubscriptionStatus.DELETED,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() - timedelta(days=1),
            url="https://example.com/sub/913",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="EXISTONLY2",
            reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
            reward=10,
            availability=PromocodeAvailability.EXISTING,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case(actor, ActivatePromocodeDto(code="EXISTONLY2"))  # must not raise


async def test_activate_allowed_availability_denies_other_users(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    await promocode_repository.create(
        CreatePromocodeDto(
            code="VIPONLY",
            reward_type=PromocodeRewardType.DURATION,
            reward=10,
            availability=PromocodeAvailability.ALLOWED,
            allowed_user_ids=[999],
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(REGULAR_USER, ActivatePromocodeDto(code="VIPONLY"))


async def test_activate_invited_availability_always_denies(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    await promocode_repository.create(
        CreatePromocodeDto(
            code="INVITEONLY",
            reward_type=PromocodeRewardType.DURATION,
            reward=10,
            availability=PromocodeAvailability.INVITED,
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(REGULAR_USER, ActivatePromocodeDto(code="INVITEONLY"))


async def test_activate_duration_reward_requires_target_subscription(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    await promocode_repository.create(
        CreatePromocodeDto(code="NEEDSTARGET", reward_type=PromocodeRewardType.DURATION, reward=10)
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError):
        await use_case(REGULAR_USER, ActivatePromocodeDto(code="NEEDSTARGET"))


async def test_activate_duration_reward_extends_subscription_expiry(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Carol", telegram_id=302))
    plan_repository = PlanRepository(promocode_repository.session)
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="duration-plan",
            name="Duration Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    purchase_use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        PurchaseIdempotencyRepository(subscription_repository.session),
    )
    subscription = await purchase_use_case(
        actor,
        PurchaseSubscriptionDto(
            user_id=actor.id,
            plan_snapshot=snapshot_from_plan(plan, currency=Currency.USD, duration_days=30),
            duration_days=30,
            price_paid=Decimal(0),
            currency=Currency.USD,
            purchase_type=PurchaseType.NEW,
        ),
    )
    expire_before = subscription.expire_at

    await promocode_repository.create(
        CreatePromocodeDto(code="EXTEND10", reward_type=PromocodeRewardType.DURATION, reward=10)
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case(
        actor, ActivatePromocodeDto(code="EXTEND10", target_subscription_id=subscription.id)
    )

    updated = await subscription_repository.get_by_id(subscription.id)
    assert updated.expire_at > expire_before


async def test_activate_traffic_reward_dispatches_the_addon_grant(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
    monkeypatch,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Dave", telegram_id=303))
    plan_repository = PlanRepository(promocode_repository.session)
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="traffic-plan",
            name="Traffic Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    purchase_use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        PurchaseIdempotencyRepository(subscription_repository.session),
    )
    subscription = await purchase_use_case(
        actor,
        PurchaseSubscriptionDto(
            user_id=actor.id,
            plan_snapshot=snapshot_from_plan(plan, currency=Currency.USD, duration_days=30),
            duration_days=30,
            price_paid=Decimal(0),
            currency=Currency.USD,
            purchase_type=PurchaseType.NEW,
        ),
    )
    traffic_before = subscription.effective_traffic_limit

    addon_repository = AddOnRepository(promocode_repository.session)
    traffic_addon = await addon_repository.create(
        CreateAddOnDto(
            name="Bonus traffic", type=AddOnType.TRAFFIC, amount=50, base_price=Decimal("1.99")
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="TRAFFICBOOST",
            reward_type=PromocodeRewardType.TRAFFIC,
            reward_addon_id=traffic_addon.id,
        )
    )
    grant_dispatch = RecordingDispatch()
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        grant_dispatch,
    )

    await use_case(
        actor, ActivatePromocodeDto(code="TRAFFICBOOST", target_subscription_id=subscription.id)
    )

    assert len(grant_dispatch.messages) == 1
    assert grant_dispatch.messages[0]["subscription_id"] == subscription.id
    assert grant_dispatch.messages[0]["addon_id"] == traffic_addon.id
    activation = await promocode_repository.get_activation_by_user(
        (await promocode_repository.get_by_code("TRAFFICBOOST")).id, actor.id
    )
    assert activation is not None
    assert grant_dispatch.messages[0]["idempotency_key"] == f"promocode-activation:{activation.id}"
    # The grant itself is the task's job now, so nothing changed here yet.
    unchanged = await subscription_repository.get_by_id(subscription.id)
    assert unchanged.effective_traffic_limit == traffic_before


async def test_activate_promocode_applies_personal_discount(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Eve", telegram_id=304))
    await promocode_repository.create(
        CreatePromocodeDto(
            code="DISC50", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=50
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case(actor, ActivatePromocodeDto(code="DISC50"))

    updated = await user_repository.get_by_id(actor.id)
    assert updated is not None
    assert updated.personal_discount == 50


async def test_activate_promocode_zero_reward_personal_discount_is_a_noop(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Frank", telegram_id=305))
    # Seeded nonzero so "wrote 0" and "never wrote" are distinguishable --
    # dropping the `if promo.reward:` guard must fail this test.
    async with uow:
        await user_repository.update_fields(actor.id, UpdateUserDto(personal_discount=40))
    await promocode_repository.create(
        CreatePromocodeDto(
            code="DISC0", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=0
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case(actor, ActivatePromocodeDto(code="DISC0"))

    updated = await user_repository.get_by_id(actor.id)
    assert updated is not None
    assert updated.personal_discount == 40


async def test_activate_promocode_applies_purchase_discount(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Grace", telegram_id=306))
    await promocode_repository.create(
        CreatePromocodeDto(
            code="ONEOFF20", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=20
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    await use_case(actor, ActivatePromocodeDto(code="ONEOFF20"))

    updated = await user_repository.get_by_id(actor.id)
    assert updated is not None
    assert updated.purchase_discount == 20


def _summary_use_case(
    promocode_repository: PromocodeRepository, uow: UnitOfWork
) -> GetPromocodeSummaryUseCase:
    session = promocode_repository.session
    return GetPromocodeSummaryUseCase(
        promocode_repository, TransactionRepository(session), PricingRepository(session), uow
    )


async def test_promocode_summary_counts_statuses_and_activations(
    promocode_repository: PromocodeRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    capped = await promocode_repository.create(
        CreatePromocodeDto(
            code="CAPPED", reward_type=PromocodeRewardType.DURATION, reward=5, max_activations=1
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="OLD",
            reward_type=PromocodeRewardType.DURATION,
            reward=5,
            expires_at=datetime_now() - timedelta(days=1),
        )
    )
    user = await user_repository.create(
        CreateUserDto(name="buyer", telegram_id=uuid4().int % 10**9)
    )
    await promocode_repository.claim_activation(capped.id, user.id, None)

    summary = await _summary_use_case(promocode_repository, uow)(OWNER)

    assert summary.total_count == 2
    assert summary.active_count == 1
    assert summary.activations_count == 1
    assert summary.activated_users_count == 1
    assert summary.activations_by_promocode == {capped.id: 1}


async def test_promocode_summary_requires_permission(
    promocode_repository: PromocodeRepository, uow: UnitOfWork
) -> None:
    with pytest.raises(PermissionDeniedError):
        await _summary_use_case(promocode_repository, uow)(REGULAR_USER)


async def test_list_promocode_activated_users_returns_newest_first(
    promocode_repository: PromocodeRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="MANY", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    first = await user_repository.create(
        CreateUserDto(name="first", telegram_id=uuid4().int % 10**9)
    )
    second = await user_repository.create(
        CreateUserDto(name="second", telegram_id=uuid4().int % 10**9)
    )
    await promocode_repository.claim_activation(promo.id, first.id, None)
    await promocode_repository.claim_activation(promo.id, second.id, None)
    use_case = ListPromocodeActivatedUsersUseCase(promocode_repository, user_repository, uow)

    users, total = await use_case(
        OWNER, ListPromocodeActivatedUsersDto(promocode_id=promo.id, page=1, page_size=1)
    )

    assert total == 2
    assert [user.name for user in users] == ["second"]


async def test_list_promocode_activated_users_unknown_promocode_raises(
    promocode_repository: PromocodeRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    use_case = ListPromocodeActivatedUsersUseCase(promocode_repository, user_repository, uow)

    with pytest.raises(NotFoundError):
        await use_case(OWNER, ListPromocodeActivatedUsersDto(promocode_id=999_999))


async def test_list_promocode_activated_users_requires_permission(
    promocode_repository: PromocodeRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    use_case = ListPromocodeActivatedUsersUseCase(promocode_repository, user_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, ListPromocodeActivatedUsersDto(promocode_id=1))


async def test_promocode_summary_totals_granted_rewards(
    promocode_repository: PromocodeRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    days = await promocode_repository.create(
        CreatePromocodeDto(
            code="DAYS", reward_type=PromocodeRewardType.DURATION, reward=10, is_reusable=True
        )
    )
    user = await user_repository.create(
        CreateUserDto(name="buyer", telegram_id=uuid4().int % 10**9)
    )
    for promo_id in (days.id, days.id):
        await promocode_repository.claim_activation(promo_id, user.id, None)

    summary = await _summary_use_case(promocode_repository, uow)(OWNER)

    assert summary.granted_days == 20
    assert summary.granted_subscriptions_count == 0


def _order(user_id: int, *, promocode_id: Optional[int], final_price: str) -> CreateTransactionDto:
    return CreateTransactionDto(
        user_id=user_id,
        plan_id=None,
        plan_snapshot=make_plan_snapshot(),
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.YOOKASSA,
        base_price=Decimal("500"),
        discount_percent=20,
        discount_source=DiscountSource.PERSONAL,
        final_price=Decimal(final_price),
        anchor_base_price=Decimal("500"),
        anchor_final_price=Decimal(final_price),
        discount_promocode_id=promocode_id,
        customer_email=None,
        idempotency_key=uuid4().hex,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_promocode_summary_sums_paid_promocode_discounts(
    promocode_repository: PromocodeRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="OFF20", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=20
        )
    )
    user = await user_repository.create(
        CreateUserDto(name="buyer", telegram_id=uuid4().int % 10**9)
    )
    orders = TransactionRepository(promocode_repository.session)
    paid = await orders.create(_order(user.id, promocode_id=promo.id, final_price="400"))
    await orders.mark_status(paid.id, TransactionStatus.PAID)
    await orders.create(_order(user.id, promocode_id=promo.id, final_price="400"))  # pending
    admin_discount = await orders.create(_order(user.id, promocode_id=None, final_price="400"))
    await orders.mark_status(admin_discount.id, TransactionStatus.PAID)
    rate_table = await PricingRepository(promocode_repository.session).get_rate_table()

    summary = await _summary_use_case(promocode_repository, uow)(OWNER)

    assert summary.discounted_orders_count == 1
    assert summary.report_currency is rate_table.anchor
    assert summary.discount_amount == convert_for_report(
        Decimal("100"), Currency.RUB, rate_table.anchor, rate_table
    )


async def test_admin_discount_clears_promocode_source(
    promocode_repository: PromocodeRepository, user_repository: UserRepository
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="SRC", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=15)
    )
    user = await user_repository.create(
        CreateUserDto(name="buyer", telegram_id=uuid4().int % 10**9)
    )
    await user_repository.update_fields(
        user.id, UpdateUserDto(personal_discount=15, personal_discount_promocode_id=promo.id)
    )

    updated = await user_repository.update_fields(user.id, UpdateUserDto(personal_discount=5))

    assert updated is not None
    assert updated.personal_discount == 5
    assert updated.personal_discount_promocode_id is None


async def _plan_with_subscription(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user: UserDto,
    code: str,
    *,
    allow_promocodes: bool = True,
) -> tuple[int, int]:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=code,
            name=code,
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
            allow_promocodes=allow_promocodes,
        )
    )
    subscription = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=user.id,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://example.test/sub",
            plan_snapshot=make_plan_snapshot(plan_id=plan.id),
        )
    )
    return plan.id, subscription.id


@pytest.mark.parametrize(
    ("listed", "allow_promocodes"),
    [(False, True), (True, False)],
    ids=["plan-not-listed", "plan-refuses-promocodes"],
)
async def test_activate_refuses_a_subscription_on_a_disallowed_plan(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
    listed: bool,
    allow_promocodes: bool,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Pat", telegram_id=330))
    plan_repository = PlanRepository(promocode_repository.session)
    plan_id, subscription_id = await _plan_with_subscription(
        plan_repository,
        subscription_repository,
        actor,
        "rules-plan",
        allow_promocodes=allow_promocodes,
    )
    other = await plan_repository.create(
        CreatePlanDto(
            public_code="other", name="other", type=PlanType.BOTH, traffic_limit=1, device_limit=1
        )
    )
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="PLANONLY",
            reward_type=PromocodeRewardType.DURATION,
            reward=10,
            allowed_plan_ids=[plan_id] if listed else [other.id],
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            actor, ActivatePromocodeDto(code="PLANONLY", target_subscription_id=subscription_id)
        )

    assert error.value.code is ErrorCode.PROMOCODE_PLAN_NOT_ALLOWED
    assert await promocode_repository.get_activations_count(promo.id) == 0


async def test_activate_on_a_deleted_plan_is_not_refused_for_the_plan(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Gone", telegram_id=331))
    plan_repository = PlanRepository(promocode_repository.session)
    plan_id, subscription_id = await _plan_with_subscription(
        plan_repository, subscription_repository, actor, "gone-plan", allow_promocodes=False
    )
    await plan_repository.session.execute(delete(Plan).where(Plan.id == plan_id))
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="ANYPLAN", reward_type=PromocodeRewardType.DURATION, reward=10)
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    # the fake panel has no user behind this row, so the reward step fails —
    # after the plan checks let it through and the activation was claimed
    with pytest.raises(Exception) as error:
        await use_case(
            actor, ActivatePromocodeDto(code="ANYPLAN", target_subscription_id=subscription_id)
        )

    assert getattr(error.value, "code", None) is not ErrorCode.PROMOCODE_PLAN_NOT_ALLOWED
    assert await promocode_repository.get_activations_count(promo.id) == 1


async def test_activate_on_a_listed_plan_passes_the_plan_checks(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="Lis", telegram_id=332))
    plan_repository = PlanRepository(promocode_repository.session)
    plan_id, subscription_id = await _plan_with_subscription(
        plan_repository, subscription_repository, actor, "listed-plan"
    )
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="LISTED",
            reward_type=PromocodeRewardType.DURATION,
            reward=10,
            allowed_plan_ids=[plan_id],
        )
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )

    # the reward step then fails on the fake panel; the plan checks let it through
    with pytest.raises(Exception) as error:
        await use_case(
            actor, ActivatePromocodeDto(code="LISTED", target_subscription_id=subscription_id)
        )

    assert getattr(error.value, "code", None) is not ErrorCode.PROMOCODE_PLAN_NOT_ALLOWED
    assert await promocode_repository.get_activations_count(promo.id) == 1


async def test_deleting_a_promocode_ends_the_discounts_it_gave(
    promocode_repository: PromocodeRepository,
    user_repository: UserRepository,
    uow,
    event_publisher,
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="GONEDISC", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=20
        )
    )
    holder = await user_repository.create(CreateUserDto(name="Holder", telegram_id=340))
    bystander = await user_repository.create(CreateUserDto(name="Admin-given", telegram_id=341))
    async with uow:
        await user_repository.update_fields(
            holder.id,
            UpdateUserDto(
                purchase_discount=20,
                purchase_discount_promocode_id=promo.id,
                personal_discount=10,
                personal_discount_promocode_id=promo.id,
            ),
        )
        await user_repository.update_fields(bystander.id, UpdateUserDto(personal_discount=15))

    await DeletePromocodeUseCase(promocode_repository, user_repository, uow, event_publisher)(
        OWNER, promo.id
    )

    after = await user_repository.get_by_id(holder.id)
    assert after is not None
    assert (after.purchase_discount, after.personal_discount) == (0, 0)
    untouched = await user_repository.get_by_id(bystander.id)
    assert untouched is not None
    assert untouched.personal_discount == 15
