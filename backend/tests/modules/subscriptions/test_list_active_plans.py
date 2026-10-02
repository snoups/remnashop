from decimal import Decimal
from uuid import uuid4

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PlanAvailability, PlanType, Role, SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.usecases import ListActivePlansUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_eligibility, make_plan_snapshot

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def _add_minimal_squad(plan_repository: PlanRepository, plan_id: int) -> None:
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan_id, internal_squads=[uuid4()], external_squad=None)
    )


async def _add_minimal_duration(plan_repository: PlanRepository, plan_id: int) -> None:
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan_id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("9.99"))],
        )
    )


async def test_regular_user_can_list_active_plans(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    plans = await use_case(REGULAR_USER)

    assert [plan.id for plan in plans] == [created.id]


async def test_list_active_plans_excludes_inactive(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    assert await use_case(REGULAR_USER) == []


async def test_list_active_plans_excludes_plan_restricted_to_other_actor(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="vip", name="VIP", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.ALLOWED,
            allowed_telegram_ids=[999_999],
            allowed_emails=[],
        )
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    assert await use_case(REGULAR_USER) == []


async def test_list_active_plans_includes_plan_allowed_for_actor_telegram_id(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="vip", name="VIP", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.ALLOWED,
            allowed_telegram_ids=[555],
            allowed_emails=[],
        )
    )
    invited_user = UserDto(
        id=3, telegram_id=555, name="Invited", role=Role.USER, language=Locale.EN
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    plans = await use_case(invited_user)

    assert [plan.id for plan in plans] == [created.id]


async def test_list_active_plans_excludes_link_availability_plan(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="secret",
            name="Secret",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.LINK,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    assert await use_case(REGULAR_USER) == []


async def test_list_active_plans_includes_new_availability_plan_for_a_fresh_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="newbie",
            name="Newbie",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.NEW,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    plans = await use_case(REGULAR_USER)

    assert [plan.id for plan in plans] == [created.id]


async def test_list_active_plans_excludes_existing_availability_plan_for_a_fresh_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="loyal", name="Loyal", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.EXISTING,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    assert await use_case(REGULAR_USER) == []


async def test_list_active_plans_includes_existing_availability_plan_for_a_returning_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    returning_user = await user_repository.create(CreateUserDto(name="Returning", telegram_id=920))
    await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=returning_user.id,
            remnawave_user_id=920_001,
            status=SubscriptionStatus.EXPIRED,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now(),
            url="https://example.com/sub/920",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="loyal2",
            name="Loyal2",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.EXISTING,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    plans = await use_case(returning_user)

    assert [plan.id for plan in plans] == [created.id]


async def test_invited_plan_visible_only_to_referred_users(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="INV",
            name="Invite-only",
            type=PlanType.UNLIMITED,
            traffic_limit=0,
            device_limit=0,
        )
    )
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.INVITED,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )
    referrer = await user_repository.create(CreateUserDto(name="r", telegram_id=7001))
    referred = await user_repository.create(CreateUserDto(name="ref", telegram_id=7002))
    unreferred = await user_repository.create(CreateUserDto(name="u", telegram_id=7003))
    await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=referred.id, level=1
    )
    use_case = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )

    plans_for_referred = await use_case(referred)
    plans_for_unreferred = await use_case(unreferred)

    assert created.public_code in {p.public_code for p in plans_for_referred}
    assert created.public_code not in {p.public_code for p in plans_for_unreferred}
