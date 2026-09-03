from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.enums import (
    AddOnType,
    Currency,
    Locale,
    PlanAvailability,
    PlanType,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseType,
    Role,
    SubscriptionStatus,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.promocodes.dto import ActivatePromocodeDto, CreatePromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import (
    ActivatePromocodeUseCase,
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    ListPromocodesUseCase,
    UpdatePromocodeUseCase,
)
from app.modules.referrals import ReferralRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import (
    CreateAddOnDto,
    CreateSubscriptionDto,
    PurchaseSubscriptionDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import GrantAddOnUseCase, PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot, snapshot_from_plan

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def test_owner_can_create_duration_promocode(
    promocode_repository: PromocodeRepository, uow
) -> None:
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
    )

    promo = await use_case(
        OWNER,
        CreatePromocodeDto(code="ADMIN10", reward_type=PromocodeRewardType.DURATION, reward=10),
    )

    assert promo.code == "ADMIN10"
    assert promo.is_active is True


async def test_regular_user_cannot_create_promocode(
    promocode_repository: PromocodeRepository, uow
) -> None:
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            CreatePromocodeDto(code="X", reward_type=PromocodeRewardType.DURATION, reward=10),
        )


async def test_create_duration_promocode_requires_positive_reward(
    promocode_repository: PromocodeRepository, uow
) -> None:
    use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            CreatePromocodeDto(code="ZERO", reward_type=PromocodeRewardType.DURATION, reward=0),
        )


async def test_create_traffic_promocode_requires_matching_addon_type(
    promocode_repository: PromocodeRepository, uow
) -> None:
    addon_repository = AddOnRepository(promocode_repository.session)
    devices_addon = await addon_repository.create(
        CreateAddOnDto(name="Bonus devices", type=AddOnType.DEVICES, amount=2)
    )
    use_case = CreatePromocodeUseCase(
        promocode_repository, addon_repository, PlanRepository(promocode_repository.session), uow
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
    promocode_repository: PromocodeRepository, uow
) -> None:
    addon_repository = AddOnRepository(promocode_repository.session)
    traffic_addon = await addon_repository.create(
        CreateAddOnDto(name="Bonus traffic", type=AddOnType.TRAFFIC, amount=50)
    )
    use_case = CreatePromocodeUseCase(
        promocode_repository, addon_repository, PlanRepository(promocode_repository.session), uow
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
    promocode_repository: PromocodeRepository, uow
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
        promocode_repository, AddOnRepository(promocode_repository.session), plan_repository, uow
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


async def test_update_promocode_deactivates(promocode_repository: PromocodeRepository, uow) -> None:
    create_use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
    )
    created = await create_use_case(
        OWNER, CreatePromocodeDto(code="TOGGLE", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    update_use_case = UpdatePromocodeUseCase(promocode_repository, uow)

    updated = await update_use_case(
        OWNER, UpdatePromocodeDto(promocode_id=created.id, is_active=False)
    )

    assert updated.is_active is False


async def test_delete_promocode(promocode_repository: PromocodeRepository, uow) -> None:
    create_use_case = CreatePromocodeUseCase(
        promocode_repository,
        AddOnRepository(promocode_repository.session),
        PlanRepository(promocode_repository.session),
        uow,
    )
    created = await create_use_case(
        OWNER, CreatePromocodeDto(code="DELME", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    delete_use_case = DeletePromocodeUseCase(promocode_repository, uow)

    await delete_use_case(OWNER, created.id)

    assert await promocode_repository.get_by_code("DELME") is None


async def test_list_promocodes_requires_view_permission(
    promocode_repository: PromocodeRepository,
) -> None:
    use_case = ListPromocodesUseCase(promocode_repository)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_generate_promocode_code_returns_unique_code(
    promocode_repository: PromocodeRepository,
) -> None:
    use_case = GeneratePromocodeCodeUseCase(promocode_repository)

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
) -> ActivatePromocodeUseCase:
    settings_repository = SettingsRepository(promocode_repository.session)
    purchase_use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    grant_addon_use_case = GrantAddOnUseCase(
        subscription_repository,
        AddOnRepository(promocode_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
    )
    return ActivatePromocodeUseCase(
        promocode_repository,
        subscription_repository,
        PlanRepository(promocode_repository.session),
        settings_repository,
        user_repository,
        purchase_use_case,
        grant_addon_use_case,
        ReferralRepository(promocode_repository.session),
        uow,
        event_publisher,
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
    # promocode_activations.user_id is a real FK -- REGULAR_USER (id=2) has no
    # backing row, so claim_activation's insert would violate it; every other
    # activate test raises before reaching claim_activation and never needs this.
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
            durations=[
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[SetPlanPriceDto(currency=Currency.RUB, price=Decimal("500.00"))],
                )
            ],
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
            durations=[
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[SetPlanPriceDto(currency=Currency.RUB, price=Decimal("500.00"))],
                )
            ],
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
    # "New" means never purchased a non-trial subscription, not "has none
    # ACTIVE right now" -- a DELETED row still disqualifies, matching main.
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
            durations=[
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[SetPlanPriceDto(currency=Currency.RUB, price=Decimal("500.00"))],
                )
            ],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    purchase_use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        user_repository,
        SettingsRepository(promocode_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
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


async def test_activate_traffic_reward_grants_addon_to_subscription(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
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
            durations=[
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[SetPlanPriceDto(currency=Currency.RUB, price=Decimal("500.00"))],
                )
            ],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
    purchase_use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        user_repository,
        SettingsRepository(promocode_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
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
        CreateAddOnDto(name="Bonus traffic", type=AddOnType.TRAFFIC, amount=50)
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="TRAFFICBOOST",
            reward_type=PromocodeRewardType.TRAFFIC,
            reward_addon_id=traffic_addon.id,
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

    await use_case(
        actor, ActivatePromocodeDto(code="TRAFFICBOOST", target_subscription_id=subscription.id)
    )

    updated = await subscription_repository.get_by_id(subscription.id)
    assert updated.effective_traffic_limit == traffic_before + traffic_addon.amount


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
