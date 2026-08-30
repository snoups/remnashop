from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SubscriptionStatus
from app.core.exceptions import PermissionDeniedError
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    DeleteSubscriptionUseCase,
    ListSubscriptionsUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)

_EXPIRE_AT = datetime(2030, 1, 1, tzinfo=timezone.utc)


def _create_dto(user_id: int, remnawave_user_id: int) -> CreateSubscriptionDto:
    return CreateSubscriptionDto(
        user_id=user_id,
        remnawave_user_id=remnawave_user_id,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=3,
        expire_at=_EXPIRE_AT,
        url="https://example.com/sub/token",
        plan_snapshot=make_plan_snapshot(),
    )


async def test_owner_can_list_subscriptions(
    subscription_repository: SubscriptionRepository, user_repository: UserRepository
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=201))
    await subscription_repository.create(_create_dto(user.id, 6001))
    use_case = ListSubscriptionsUseCase(subscription_repository)

    subscriptions = await use_case(OWNER)

    assert len(subscriptions) == 1


async def test_regular_user_cannot_list_subscriptions(
    subscription_repository: SubscriptionRepository,
) -> None:
    use_case = ListSubscriptionsUseCase(subscription_repository)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_owner_can_update_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=202))
    created = await subscription_repository.create(_create_dto(user.id, 6002))
    use_case = UpdateSubscriptionUseCase(subscription_repository, uow)

    updated = await use_case(
        OWNER, UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=500)
    )

    assert updated.traffic_limit == 500


async def test_regular_user_cannot_update_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=203))
    created = await subscription_repository.create(_create_dto(user.id, 6003))
    use_case = UpdateSubscriptionUseCase(subscription_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER, UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=500)
        )


async def test_owner_can_update_subscription_squads(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=204))
    created = await subscription_repository.create(_create_dto(user.id, 6004))
    use_case = UpdateSubscriptionSquadsUseCase(subscription_repository, uow)
    squad = uuid4()

    updated = await use_case(
        OWNER,
        UpdateSubscriptionSquadsDto(
            subscription_id=created.id, internal_squads=[squad], external_squad=None
        ),
    )

    assert updated.internal_squads == [squad]


async def test_regular_user_cannot_update_subscription_squads(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=205))
    created = await subscription_repository.create(_create_dto(user.id, 6005))
    use_case = UpdateSubscriptionSquadsUseCase(subscription_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdateSubscriptionSquadsDto(
                subscription_id=created.id, internal_squads=[], external_squad=None
            ),
        )


async def test_owner_can_delete_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=206))
    created = await subscription_repository.create(_create_dto(user.id, 6006))
    use_case = DeleteSubscriptionUseCase(subscription_repository, uow)

    await use_case(OWNER, created.id)

    subscriptions = await subscription_repository.list_all()
    assert subscriptions[0].status == SubscriptionStatus.DELETED


async def test_regular_user_cannot_delete_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=207))
    created = await subscription_repository.create(_create_dto(user.id, 6007))
    use_case = DeleteSubscriptionUseCase(subscription_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, created.id)
