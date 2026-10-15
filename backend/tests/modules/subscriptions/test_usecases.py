from datetime import datetime, timezone
from uuid import uuid4

import pytest
from remnapy import RemnawaveSDK

from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Locale, Role, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    ListSubscriptionsDto,
    SubscriptionDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.subscriptions.usecases import (
    DeleteSubscriptionUseCase,
    ListSubscriptionsUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
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


def _update_use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    event_publisher,
    uow: UnitOfWork,
) -> UpdateSubscriptionUseCase:
    return UpdateSubscriptionUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
        SubscriptionLifecycleService(subscription_repository),
    )


def _seed_panel_user(store: FakeUserStore, remnawave_user_id: int) -> None:
    store[remnawave_user_id] = _user_payload(
        user_id=remnawave_user_id, username=f"fake_{remnawave_user_id}", expire_at=_EXPIRE_AT
    )


async def test_owner_can_list_subscriptions(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=201))
    await subscription_repository.create(_create_dto(user.id, 6001))
    use_case = ListSubscriptionsUseCase(subscription_repository, uow)

    subscriptions, total = await use_case(OWNER, ListSubscriptionsDto())

    assert len(subscriptions) == 1
    assert total == 1


async def test_regular_user_cannot_list_subscriptions(
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListSubscriptionsUseCase(subscription_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, ListSubscriptionsDto())


async def test_owner_can_update_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=202))
    _seed_panel_user(remnawave_store, 6002)
    created = await subscription_repository.create(_create_dto(user.id, 6002))
    use_case = _update_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)

    updated = await use_case(
        OWNER, UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=500)
    )

    assert updated.traffic_limit == 500


async def test_regular_user_cannot_update_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=203))
    _seed_panel_user(remnawave_store, 6003)
    created = await subscription_repository.create(_create_dto(user.id, 6003))
    use_case = _update_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER, UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=500)
        )


async def test_owner_can_update_subscription_squads(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=204))
    _seed_panel_user(remnawave_store, 6004)
    created = await subscription_repository.create(_create_dto(user.id, 6004))
    use_case = UpdateSubscriptionSquadsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )
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
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=205))
    _seed_panel_user(remnawave_store, 6005)
    created = await subscription_repository.create(_create_dto(user.id, 6005))
    use_case = UpdateSubscriptionSquadsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

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
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=206))
    _seed_panel_user(remnawave_store, 6006)
    created = await subscription_repository.create(_create_dto(user.id, 6006))
    use_case = DeleteSubscriptionUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        PanelSubscriptionRevoker(subscription_repository, remnawave_sdk),
        event_publisher,
        uow,
    )

    await use_case(OWNER, created.id)

    subscriptions = await subscription_repository.list_all()
    assert subscriptions[0].status == SubscriptionStatus.DELETED


async def test_delete_subscription_tolerates_user_already_removed_in_panel(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=208))
    created = await subscription_repository.create(_create_dto(user.id, 6008))
    use_case = DeleteSubscriptionUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        PanelSubscriptionRevoker(subscription_repository, remnawave_sdk),
        event_publisher,
        uow,
    )

    await use_case(OWNER, created.id)

    assert (await subscription_repository.get_by_id(created.id)).status == (
        SubscriptionStatus.DELETED
    )


async def test_regular_user_cannot_delete_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=207))
    _seed_panel_user(remnawave_store, 6007)
    created = await subscription_repository.create(_create_dto(user.id, 6007))
    use_case = DeleteSubscriptionUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        PanelSubscriptionRevoker(subscription_repository, remnawave_sdk),
        event_publisher,
        uow,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, created.id)


async def test_update_expire_at_pushes_to_panel_and_syncs_status(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9501))
    _seed_panel_user(remnawave_store, 9501)
    created = await subscription_repository.create(_create_dto(user.id, 9501))
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)

    updated = await _update_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)(
        OWNER, UpdateSubscriptionDto(subscription_id=created.id, expire_at=past)
    )

    assert updated.expire_at == past
    assert updated.status is SubscriptionStatus.EXPIRED
    assert remnawave_store[9501]["status"] == "EXPIRED"


async def test_update_keeps_db_unchanged_when_panel_fails(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9502))
    created = await subscription_repository.create(_create_dto(user.id, 9502))  # no panel user

    with pytest.raises(Exception):
        await _update_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)(
            OWNER, UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=999)
        )

    assert (await subscription_repository.get_by_id(created.id)).traffic_limit == 100


async def test_update_tag_only_does_not_call_panel(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9503))
    created = await subscription_repository.create(_create_dto(user.id, 9503))  # no panel user

    updated = await _update_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)(
        OWNER, UpdateSubscriptionDto(subscription_id=created.id, tag="vip")
    )

    assert updated.tag == "vip"


async def test_update_unlimited_traffic_stays_unlimited_with_addon(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9504))
    _seed_panel_user(remnawave_store, 9504)
    created = await subscription_repository.create(_create_dto(user.id, 9504))
    async with uow:
        await subscription_repository.grant_entitlement(
            subscription_id=created.id, addon_id=None, addon_type=AddOnType.TRAFFIC, amount=10
        )

    await _update_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)(
        OWNER, UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=0)
    )

    assert remnawave_store[9504]["trafficLimitBytes"] == 0


async def test_update_deleted_subscription_is_rejected(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9505))
    created = await subscription_repository.create(_create_dto(user.id, 9505))
    async with uow:
        await subscription_repository.mark_deleted(created.id)

    with pytest.raises(ValidationError):
        await _update_use_case(subscription_repository, remnawave_sdk, event_publisher, uow)(
            OWNER, UpdateSubscriptionDto(subscription_id=created.id, tag="x")
        )


class _FailingUpdateRepository(SubscriptionRepository):
    async def update(self, data: UpdateSubscriptionDto) -> SubscriptionDto:
        raise RuntimeError("db write failed")


async def test_update_reverts_panel_to_effective_limits_when_db_write_fails(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9506))
    _seed_panel_user(remnawave_store, 9506)
    created = await subscription_repository.create(_create_dto(user.id, 9506))
    async with uow:
        await subscription_repository.grant_entitlement(
            subscription_id=created.id, addon_id=None, addon_type=AddOnType.TRAFFIC, amount=10
        )
    failing = _FailingUpdateRepository(subscription_repository.session)

    with pytest.raises(RuntimeError):
        await _update_use_case(failing, remnawave_sdk, event_publisher, uow)(
            OWNER, UpdateSubscriptionDto(subscription_id=created.id, traffic_limit=200)
        )

    assert remnawave_store[9506]["trafficLimitBytes"] == 110 * GB_TO_BYTES


async def test_squads_edit_refused_when_the_subscription_was_deleted_meanwhile(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    event_publisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=206))
    _seed_panel_user(remnawave_store, 6006)
    created = await subscription_repository.create(_create_dto(user.id, 6006))
    real_update = remnawave_sdk.users.update_user

    async def _update_then_delete(request: object) -> object:
        result = await real_update(request)
        await subscription_repository.mark_deleted(created.id)
        return result

    monkeypatch.setattr(remnawave_sdk.users, "update_user", _update_then_delete)
    use_case = UpdateSubscriptionSquadsUseCase(
        subscription_repository,
        UserRepository(subscription_repository.session),
        remnawave_sdk,
        event_publisher,
        uow,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            OWNER,
            UpdateSubscriptionSquadsDto(
                subscription_id=created.id, internal_squads=[uuid4()], external_squad=None
            ),
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_DELETED
    assert (await subscription_repository.get_by_id(created.id)).internal_squads == []
