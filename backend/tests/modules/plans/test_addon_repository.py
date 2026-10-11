from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.enums import AddOnType, Currency
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreateAddOnDto,
    SetAddOnBasePriceDto,
    SetAddOnPriceOverrideDto,
    UpdateAddOnDto,
)


def _create_dto(
    name: str = "traffic-10gb", base_price: Decimal = Decimal("1.99")
) -> CreateAddOnDto:
    return CreateAddOnDto(name=name, type=AddOnType.TRAFFIC, amount=10, base_price=base_price)


async def test_create_then_list_all_returns_addon(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    addons = await addon_repository.list_all()

    assert len(addons) == 1
    assert addons[0].id == created.id
    assert addons[0].name == "traffic-10gb"
    assert addons[0].is_active is False
    assert addons[0].base_price == Decimal("1.99")
    assert addons[0].overrides == []


async def test_create_assigns_incrementing_order_index(addon_repository: AddOnRepository) -> None:
    first = await addon_repository.create(_create_dto("a"))
    second = await addon_repository.create(_create_dto("b"))

    assert first.order_index == 0
    assert second.order_index == 1


async def test_create_duplicate_name_raises_conflict(addon_repository: AddOnRepository) -> None:
    await addon_repository.create(_create_dto("dup"))

    with pytest.raises(ConflictError):
        await addon_repository.create(_create_dto("dup"))


async def test_update_unknown_addon_raises_not_found(addon_repository: AddOnRepository) -> None:
    with pytest.raises(NotFoundError):
        await addon_repository.update(UpdateAddOnDto(addon_id=999_999, name="x"))


async def test_partial_update_leaves_other_fields_untouched(
    addon_repository: AddOnRepository,
) -> None:
    created = await addon_repository.create(_create_dto())

    updated = await addon_repository.update(UpdateAddOnDto(addon_id=created.id, amount=20))

    assert updated.amount == 20
    assert updated.name == "traffic-10gb"  # untouched
    assert updated.is_active is False  # untouched


async def test_update_can_activate(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    updated = await addon_repository.update(UpdateAddOnDto(addon_id=created.id, is_active=True))

    assert updated.is_active is True


async def test_delete_removes_addon(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    await addon_repository.delete(created.id)

    assert await addon_repository.list_all() == []


async def test_delete_unknown_addon_raises_not_found(addon_repository: AddOnRepository) -> None:
    with pytest.raises(NotFoundError):
        await addon_repository.delete(999_999)


async def test_set_base_price_updates_addon(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    updated = await addon_repository.set_base_price(
        SetAddOnBasePriceDto(addon_id=created.id, base_price=Decimal("2.49"))
    )

    assert updated.base_price == Decimal("2.49")


async def test_set_price_override_upserts_and_unpins(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    pinned = await addon_repository.set_price_override(
        SetAddOnPriceOverrideDto(addon_id=created.id, currency=Currency.RUB, price=Decimal("120"))
    )
    assert pinned.overrides[0].currency is Currency.RUB
    assert pinned.overrides[0].price == Decimal("120")

    unpinned = await addon_repository.set_price_override(
        SetAddOnPriceOverrideDto(addon_id=created.id, currency=Currency.RUB, price=None)
    )
    assert unpinned.overrides == []


async def test_get_by_id_returns_addon(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    fetched = await addon_repository.get_by_id(created.id)

    assert fetched.id == created.id
    assert fetched.name == "traffic-10gb"


async def test_get_by_id_unknown_addon_raises_not_found(addon_repository: AddOnRepository) -> None:
    with pytest.raises(NotFoundError):
        await addon_repository.get_by_id(999_999)


async def test_create_does_not_report_an_invalid_price_as_a_taken_name(
    addon_repository: AddOnRepository,
) -> None:
    with pytest.raises(IntegrityError):
        await addon_repository.create(_create_dto(name="free", base_price=Decimal("0")))
