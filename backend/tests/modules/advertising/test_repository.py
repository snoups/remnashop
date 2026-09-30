from decimal import Decimal

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import AdLinkChannel, Currency
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.advertising.dto import CreateAdLinkDto, UpdateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_create_and_get_by_id(ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
    async with uow:
        created = await ad_link_repository.create(
            CreateAdLinkDto(name="YouTube Jan", code="yt-jan-2026")
        )

    fetched = await ad_link_repository.get_by_id(created.id)
    assert fetched.code == "yt-jan-2026"
    assert fetched.is_active is True
    assert fetched.cost == Decimal(0)
    assert fetched.cost_currency == Currency.USD


async def test_get_by_id_unknown_raises_not_found(
    ad_link_repository: AdLinkRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await ad_link_repository.get_by_id(999_999)


async def test_create_duplicate_code_raises_conflict(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await ad_link_repository.create(CreateAdLinkDto(name="A", code="dup-code"))

    with pytest.raises(ConflictError):
        async with uow:
            await ad_link_repository.create(CreateAdLinkDto(name="B", code="dup-code"))


async def test_update_leaves_unset_fields_unchanged(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    async with uow:
        created = await ad_link_repository.create(
            CreateAdLinkDto(name="Original", code="update-me", cost=Decimal("10"))
        )

    updated = await ad_link_repository.update(
        UpdateAdLinkDto(ad_link_id=created.id, is_active=False)
    )

    assert updated.is_active is False
    assert updated.name == "Original"
    assert updated.cost == Decimal("10")


async def test_delete_removes_the_row(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    async with uow:
        created = await ad_link_repository.create(CreateAdLinkDto(name="Gone", code="delete-me"))

    await ad_link_repository.delete_if_no_attributions(created.id)

    with pytest.raises(NotFoundError):
        await ad_link_repository.get_by_id(created.id)


async def test_attribution_lifecycle(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(CreateAdLinkDto(name="Attr", code="attr-code"))
    user = await user_repository.create(CreateUserDto(name="Attributed", telegram_id=920_001))

    assert await ad_link_repository.count_attributions(ad_link.id) == 0

    attribution = await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
    )

    assert attribution.channel == AdLinkChannel.BOT
    assert await ad_link_repository.count_attributions(ad_link.id) == 1
    assert await ad_link_repository.count_attributions_by_channel(ad_link.id) == {
        AdLinkChannel.BOT: 1
    }
    assert await ad_link_repository.list_attributed_user_ids(ad_link.id) == [user.id]

    daily = await ad_link_repository.daily_attribution_counts(ad_link.id)
    assert len(daily) == 1
    assert daily[0].count == 1

    attributions, total = await ad_link_repository.list_attributions_paginated(ad_link.id)
    assert total == 1
    assert attributions[0].user_id == user.id


async def test_create_attribution_twice_for_same_user_raises_conflict(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(CreateAdLinkDto(name="Dup", code="attr-dup"))
    user = await user_repository.create(CreateUserDto(name="Dup User", telegram_id=920_002))

    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
    )

    with pytest.raises(ConflictError):
        await ad_link_repository.create_attribution(
            ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.WEBCABINET
        )


async def test_get_user_attribution_returns_link_or_none(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(CreateAdLinkDto(name="Promo", code="attr-user"))
    user = await user_repository.create(CreateUserDto(name="Came", telegram_id=920_101))
    other = await user_repository.create(CreateUserDto(name="Organic", telegram_id=920_102))
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
    )

    attribution = await ad_link_repository.get_user_attribution(user.id)

    assert attribution is not None
    assert (attribution.name, attribution.code) == ("Promo", "attr-user")
    assert await ad_link_repository.get_user_attribution(other.id) is None


async def test_update_rejects_disabling_every_channel(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(
            CreateAdLinkDto(name="Channels", code="channels", allow_webcabinet=False)
        )

    with pytest.raises(ValidationError):
        await ad_link_repository.update(UpdateAdLinkDto(ad_link_id=ad_link.id, allow_bot=False))


async def test_daily_attribution_counts_split_by_channel(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    user_repository: UserRepository,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(CreateAdLinkDto(name="Daily", code="daily-split"))
    for index, channel in enumerate(
        [AdLinkChannel.BOT, AdLinkChannel.BOT, AdLinkChannel.WEBCABINET]
    ):
        user = await user_repository.create(
            CreateUserDto(name=f"Daily {index}", telegram_id=920_101 + index)
        )
        await ad_link_repository.create_attribution(
            ad_link_id=ad_link.id, user_id=user.id, channel=channel
        )

    [day] = await ad_link_repository.daily_attribution_counts(ad_link.id)
    assert day.count == 3
    assert day.by_channel == {AdLinkChannel.BOT: 2, AdLinkChannel.WEBCABINET: 1}


async def test_list_paginated_puts_active_first_then_newest(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    async with uow:
        old_active = await ad_link_repository.create(CreateAdLinkDto(name="A", code="order-a"))
        paused = await ad_link_repository.create(CreateAdLinkDto(name="B", code="order-b"))
        new_active = await ad_link_repository.create(CreateAdLinkDto(name="C", code="order-c"))
    await ad_link_repository.update(UpdateAdLinkDto(ad_link_id=paused.id, is_active=False))

    links, _ = await ad_link_repository.list_paginated()
    ours = [link.id for link in links if link.code.startswith("order-")]
    assert ours == [new_active.id, old_active.id, paused.id]
