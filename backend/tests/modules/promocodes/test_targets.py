from datetime import timedelta
from typing import Any

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import GB_TO_BYTES
from app.core.enums import PromocodeRewardType, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.time import datetime_now
from app.modules.plans import AddOnRepository, PlanRepository
from app.modules.promocodes.dto import (
    ActivatePromocodeDto,
    CreatePromocodeDto,
    ListPromocodeTargetsDto,
)
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.targets import PromocodeTargets, reward_takes_effect
from app.modules.promocodes.usecases import ListPromocodeTargetsUseCase
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions import PanelTrafficUsage
from app.modules.subscriptions.dto import CreateSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.promocodes.test_usecases import _activate_use_case
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

NOW = datetime_now()
DURATION = PromocodeRewardType.DURATION
TRAFFIC = PromocodeRewardType.TRAFFIC
DEVICES = PromocodeRewardType.DEVICES


def _sub(status: SubscriptionStatus, **overrides: Any) -> SubscriptionDto:
    fields: dict[str, Any] = {
        "user_id": 1,
        "remnawave_user_id": 1,
        "status": status,
        "traffic_limit": 100,
        "device_limit": 3,
        "effective_traffic_limit": 100,
        "effective_device_limit": 3,
        "expire_at": NOW + timedelta(days=10),
        "url": "https://example.com/sub/1",
        "plan_snapshot": make_plan_snapshot(),
    }
    return SubscriptionDto(**(fields | overrides))


def _takes(sub: SubscriptionDto, reward: PromocodeRewardType, used_gb: float, extra_gb: int = 0):
    used = None if used_gb < 0 else int(used_gb * GB_TO_BYTES)
    return reward_takes_effect(sub, reward, used_traffic=used, extra_traffic_gb=extra_gb, now=NOW)


@pytest.mark.parametrize("reward", [DURATION, TRAFFIC, DEVICES])
def test_an_active_subscription_takes_every_reward(reward: PromocodeRewardType) -> None:
    assert _takes(_sub(SubscriptionStatus.ACTIVE), reward, -1)


@pytest.mark.parametrize("status", list(SubscriptionStatus))
def test_a_trial_takes_no_reward(status: SubscriptionStatus) -> None:
    trial = _sub(status, is_trial=True)
    assert not any(_takes(trial, reward, 0, 100) for reward in (DURATION, TRAFFIC, DEVICES))


def test_days_bring_back_an_expired_subscription_with_traffic_left() -> None:
    expired = _sub(SubscriptionStatus.EXPIRED, expire_at=NOW - timedelta(days=40))
    assert _takes(expired, DURATION, 99.9)
    assert _takes(_sub(SubscriptionStatus.EXPIRED, effective_traffic_limit=0), DURATION, 5000)


@pytest.mark.parametrize("status", [SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED])
def test_days_are_no_use_once_the_traffic_is_spent_for_good(status: SubscriptionStatus) -> None:
    assert not _takes(_sub(status), DURATION, 100)


@pytest.mark.parametrize("status", [SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED])
def test_days_help_a_spent_subscription_whose_traffic_resets(status: SubscriptionStatus) -> None:
    monthly = _sub(status, traffic_limit_strategy=TrafficLimitStrategy.MONTH)
    assert _takes(monthly, DURATION, 100)


def test_traffic_or_devices_dont_bring_back_an_expired_subscription() -> None:
    expired = _sub(SubscriptionStatus.EXPIRED)
    assert not _takes(expired, TRAFFIC, 0, 50)
    assert not _takes(expired, DEVICES, 0)


def test_traffic_brings_back_a_limited_subscription_only_past_what_is_used() -> None:
    limited = _sub(SubscriptionStatus.LIMITED)
    assert _takes(limited, TRAFFIC, 120, 50)
    assert not _takes(limited, TRAFFIC, 150, 50)


def test_traffic_doesnt_bring_back_a_limited_subscription_whose_term_ran_out() -> None:
    lapsed = _sub(SubscriptionStatus.LIMITED, expire_at=NOW - timedelta(days=1))
    assert not _takes(lapsed, TRAFFIC, 100, 50)


def test_devices_dont_bring_back_a_limited_subscription() -> None:
    assert not _takes(_sub(SubscriptionStatus.LIMITED), DEVICES, 100)


def test_an_unknown_usage_or_a_disabled_subscription_takes_nothing() -> None:
    assert not _takes(_sub(SubscriptionStatus.EXPIRED), DURATION, -1)
    assert not _takes(_sub(SubscriptionStatus.DISABLED), DURATION, 0)


def _panel_user(store: FakeUserStore, remnawave_user_id: int, used_gb: int) -> None:
    store[remnawave_user_id] = _user_payload(
        user_id=remnawave_user_id,
        username=f"fake_{remnawave_user_id}",
        expire_at=NOW + timedelta(days=1),
    )
    store[remnawave_user_id]["userTraffic"]["usedTrafficBytes"] = used_gb * GB_TO_BYTES


async def test_targets_list_what_days_leave_active(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    remnawave_store: FakeUserStore,
    uow,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="owner", telegram_id=901))

    async def owned(
        remnawave_user_id: int,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
        **fields: Any,
    ) -> SubscriptionDto:
        return await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=owner.id,
                status=status,
                remnawave_user_id=remnawave_user_id,
                traffic_limit=100,
                device_limit=3,
                expire_at=NOW + timedelta(days=30),
                url=f"https://example.com/sub/{remnawave_user_id}",
                plan_snapshot=make_plan_snapshot(),
                **fields,
            )
        )

    active = await owned(9101)
    lapsed = await owned(9102, status=SubscriptionStatus.EXPIRED)
    spent = await owned(9103, status=SubscriptionStatus.EXPIRED)
    await owned(9104, is_trial=True)
    _panel_user(remnawave_store, 9102, used_gb=10)
    _panel_user(remnawave_store, 9103, used_gb=100)
    await promocode_repository.create(
        CreatePromocodeDto(code="DAYS7", reward_type=DURATION, reward=7)
    )
    use_case = ListPromocodeTargetsUseCase(
        promocode_repository,
        subscription_repository,
        ReferralRepository(promocode_repository.session),
        PromocodeTargets(
            PlanRepository(promocode_repository.session),
            AddOnRepository(promocode_repository.session),
            PanelTrafficUsage(remnawave_sdk),
            uow,
        ),
        uow,
    )
    targets = await use_case(owner, ListPromocodeTargetsDto(code="days7"))

    assert [t.id for t in targets] == [active.id, lapsed.id]
    assert spent.id not in [t.id for t in targets]


async def test_activation_refuses_a_trial_target(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    trial = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=902,
        remnawave_user_id=9201,
        is_trial=True,
    )
    await promocode_repository.create(
        CreatePromocodeDto(code="TRIALDAYS", reward_type=DURATION, reward=7)
    )
    use_case = _activate_use_case(
        promocode_repository,
        subscription_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )
    actor = await user_repository.find_by_id(trial.user_id)
    assert actor is not None

    with pytest.raises(ValidationError) as refused:
        await use_case(
            actor, ActivatePromocodeDto(code="TRIALDAYS", target_subscription_id=trial.id)
        )
    assert refused.value.code is ErrorCode.TARGET_SUBSCRIPTION_NOT_ACTIVE
