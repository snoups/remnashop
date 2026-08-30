from decimal import Decimal

import pytest

from app.core.enums import AddOnType, Currency
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import (
    CreateAddOnDto,
    ReorderAddOnsDto,
    SetAddOnPriceDto,
    SetAddOnPricesDto,
    UpdateAddOnDto,
)


def _create_dto(name: str = "traffic-10gb") -> CreateAddOnDto:
    return CreateAddOnDto(name=name, type=AddOnType.TRAFFIC, amount=10)


async def test_create_then_list_all_returns_addon(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    addons = await addon_repository.list_all()

    assert len(addons) == 1
    assert addons[0].id == created.id
    assert addons[0].name == "traffic-10gb"
    assert addons[0].is_active is False
    assert addons[0].prices == []


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


async def test_set_prices_replaces_full_set(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    updated = await addon_repository.set_prices(
        SetAddOnPricesDto(
            addon_id=created.id,
            prices=[SetAddOnPriceDto(currency=Currency.RUB, price=Decimal("99.00"))],
        )
    )

    assert [p.price for p in updated.prices] == [Decimal("99.00")]


async def test_set_prices_again_drops_previous_set(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())
    await addon_repository.set_prices(
        SetAddOnPricesDto(
            addon_id=created.id,
            prices=[SetAddOnPriceDto(currency=Currency.RUB, price=Decimal("99.00"))],
        )
    )

    updated = await addon_repository.set_prices(
        SetAddOnPricesDto(
            addon_id=created.id,
            prices=[SetAddOnPriceDto(currency=Currency.USD, price=Decimal("1.50"))],
        )
    )

    assert [(p.currency, p.price) for p in updated.prices] == [(Currency.USD, Decimal("1.50"))]


async def test_reorder_applies_new_order(addon_repository: AddOnRepository) -> None:
    first = await addon_repository.create(_create_dto("a"))
    second = await addon_repository.create(_create_dto("b"))

    reordered = await addon_repository.reorder(ReorderAddOnsDto(addon_ids=[second.id, first.id]))

    assert [addon.id for addon in reordered] == [second.id, first.id]


async def test_reorder_rejects_incomplete_id_set(addon_repository: AddOnRepository) -> None:
    first = await addon_repository.create(_create_dto("a"))
    await addon_repository.create(_create_dto("b"))

    with pytest.raises(ValidationError):
        await addon_repository.reorder(ReorderAddOnsDto(addon_ids=[first.id]))


async def test_get_by_id_returns_addon(addon_repository: AddOnRepository) -> None:
    created = await addon_repository.create(_create_dto())

    fetched = await addon_repository.get_by_id(created.id)

    assert fetched.id == created.id
    assert fetched.name == "traffic-10gb"


async def test_get_by_id_unknown_addon_raises_not_found(addon_repository: AddOnRepository) -> None:
    with pytest.raises(NotFoundError):
        await addon_repository.get_by_id(999_999)
