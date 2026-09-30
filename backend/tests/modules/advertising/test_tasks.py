from app.core.db.uow import UnitOfWork
from app.core.enums import AdLinkChannel
from app.modules.advertising.dto import CreateAdLinkDto, UpdateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.advertising.tasks import record_ad_link_attribution
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_record_attribution_for_active_link(
    ad_link_repository: AdLinkRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(
            CreateAdLinkDto(name="Task Test", code="task-active")
        )
        user = await user_repository.create(CreateUserDto(name="Active", telegram_id=950_001))

    await record_ad_link_attribution(
        user_id=user.id,
        ad_link_code="task-active",
        channel=AdLinkChannel.BOT.value,
        ad_link_repository=ad_link_repository,
        uow=uow,
    )

    assert await ad_link_repository.count_attributions(ad_link.id) == 1


async def test_record_attribution_unknown_code_is_a_no_op(
    ad_link_repository: AdLinkRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        user = await user_repository.create(CreateUserDto(name="Unknown", telegram_id=950_002))

    # No exception, no row -- nothing else to assert against directly since
    # there's no ad_link id to query attributions for.
    await record_ad_link_attribution(
        user_id=user.id,
        ad_link_code="does-not-exist",
        channel=AdLinkChannel.BOT.value,
        ad_link_repository=ad_link_repository,
        uow=uow,
    )


async def test_record_attribution_inactive_link_is_a_no_op(
    ad_link_repository: AdLinkRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(
            CreateAdLinkDto(name="Inactive", code="task-inactive")
        )
        user = await user_repository.create(CreateUserDto(name="Inactive", telegram_id=950_003))
    await ad_link_repository.update(UpdateAdLinkDto(ad_link_id=ad_link.id, is_active=False))

    await record_ad_link_attribution(
        user_id=user.id,
        ad_link_code="task-inactive",
        channel=AdLinkChannel.BOT.value,
        ad_link_repository=ad_link_repository,
        uow=uow,
    )

    assert await ad_link_repository.count_attributions(ad_link.id) == 0


async def test_record_attribution_duplicate_is_swallowed(
    ad_link_repository: AdLinkRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(CreateAdLinkDto(name="Dup Task", code="task-dup"))
        user = await user_repository.create(CreateUserDto(name="Dup", telegram_id=950_004))
        await ad_link_repository.create_attribution(
            ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
        )

    await record_ad_link_attribution(
        user_id=user.id,
        ad_link_code="task-dup",
        channel=AdLinkChannel.WEBCABINET.value,
        ad_link_repository=ad_link_repository,
        uow=uow,
    )

    assert await ad_link_repository.count_attributions(ad_link.id) == 1


async def test_record_attribution_disallowed_channel_is_a_no_op(
    ad_link_repository: AdLinkRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        ad_link = await ad_link_repository.create(
            CreateAdLinkDto(name="Web Only", code="task-web-only", allow_bot=False)
        )
        user = await user_repository.create(CreateUserDto(name="WebOnly", telegram_id=950_009))

    await record_ad_link_attribution(
        user_id=user.id,
        ad_link_code="task-web-only",
        channel=AdLinkChannel.BOT.value,
        ad_link_repository=ad_link_repository,
        uow=uow,
    )

    assert await ad_link_repository.count_attributions(ad_link.id) == 0
