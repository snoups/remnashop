from decimal import Decimal

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Locale, Role
from app.core.exceptions import PermissionDeniedError
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import (
    CreateAddOnDto,
    ReorderAddOnsDto,
    SetAddOnBasePriceDto,
    UpdateAddOnDto,
)
from app.modules.subscriptions.usecases import (
    CreateAddOnUseCase,
    DeleteAddOnUseCase,
    ListAddOnsUseCase,
    ReorderAddOnsUseCase,
    SetAddOnBasePriceUseCase,
    UpdateAddOnUseCase,
)
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


def _create_dto(name: str = "traffic-10gb") -> CreateAddOnDto:
    return CreateAddOnDto(name=name, type=AddOnType.TRAFFIC, amount=10, base_price=Decimal("1.99"))


async def test_owner_can_list_addons(
    addon_repository: AddOnRepository,
    uow: UnitOfWork,
) -> None:
    await addon_repository.create(_create_dto())
    use_case = ListAddOnsUseCase(addon_repository, uow)

    addons = await use_case(OWNER)

    assert len(addons) == 1


async def test_regular_user_cannot_list_addons(
    addon_repository: AddOnRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListAddOnsUseCase(addon_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_owner_can_create_addon(addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
    use_case = CreateAddOnUseCase(addon_repository, uow)

    addon = await use_case(OWNER, _create_dto())

    assert addon.name == "traffic-10gb"
    assert addon.is_active is False


async def test_regular_user_cannot_create_addon(
    addon_repository: AddOnRepository, uow: UnitOfWork
) -> None:
    use_case = CreateAddOnUseCase(addon_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, _create_dto())


async def test_owner_can_update_addon(addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
    created = await addon_repository.create(_create_dto())
    use_case = UpdateAddOnUseCase(addon_repository, uow)

    updated = await use_case(OWNER, UpdateAddOnDto(addon_id=created.id, amount=20))

    assert updated.amount == 20


async def test_regular_user_cannot_update_addon(
    addon_repository: AddOnRepository, uow: UnitOfWork
) -> None:
    created = await addon_repository.create(_create_dto())
    use_case = UpdateAddOnUseCase(addon_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, UpdateAddOnDto(addon_id=created.id, amount=20))


async def test_owner_can_delete_addon(addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
    created = await addon_repository.create(_create_dto())
    use_case = DeleteAddOnUseCase(addon_repository, uow)

    await use_case(OWNER, created.id)

    assert await addon_repository.list_all() == []


async def test_regular_user_cannot_delete_addon(
    addon_repository: AddOnRepository, uow: UnitOfWork
) -> None:
    created = await addon_repository.create(_create_dto())
    use_case = DeleteAddOnUseCase(addon_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, created.id)


async def test_owner_can_set_addon_base_price(
    addon_repository: AddOnRepository, uow: UnitOfWork
) -> None:
    created = await addon_repository.create(_create_dto())
    use_case = SetAddOnBasePriceUseCase(addon_repository, uow)

    updated = await use_case(
        OWNER, SetAddOnBasePriceDto(addon_id=created.id, base_price=Decimal("2.49"))
    )

    assert updated.base_price == Decimal("2.49")


async def test_regular_user_cannot_set_addon_base_price(
    addon_repository: AddOnRepository, uow: UnitOfWork
) -> None:
    created = await addon_repository.create(_create_dto())
    use_case = SetAddOnBasePriceUseCase(addon_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER, SetAddOnBasePriceDto(addon_id=created.id, base_price=Decimal("2.49"))
        )


async def test_owner_can_reorder_addons(addon_repository: AddOnRepository, uow: UnitOfWork) -> None:
    first = await addon_repository.create(_create_dto("a"))
    second = await addon_repository.create(_create_dto("b"))
    use_case = ReorderAddOnsUseCase(addon_repository, uow)

    reordered = await use_case(OWNER, ReorderAddOnsDto(addon_ids=[second.id, first.id]))

    assert [addon.id for addon in reordered] == [second.id, first.id]


async def test_regular_user_cannot_reorder_addons(
    addon_repository: AddOnRepository, uow: UnitOfWork
) -> None:
    created = await addon_repository.create(_create_dto())
    use_case = ReorderAddOnsUseCase(addon_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, ReorderAddOnsDto(addon_ids=[created.id]))
