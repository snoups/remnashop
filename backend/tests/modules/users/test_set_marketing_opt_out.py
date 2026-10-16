from app.core.db.uow import UnitOfWork
from app.modules.users.dto import CreateUserDto, SetMarketingOptOutDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import SetMarketingOptOutUseCase
from tests.fakes.events import RecordingEventPublisher


async def test_customer_toggles_own_flag(user_repository: UserRepository, uow: UnitOfWork) -> None:
    user = await user_repository.create(CreateUserDto(name="c", telegram_id=9901))
    publisher = RecordingEventPublisher()
    use_case = SetMarketingOptOutUseCase(user_repository, uow, publisher)

    await use_case(user, SetMarketingOptOutDto(opted_out=True))
    loaded = await user_repository.find_by_id(user.id)
    assert loaded is not None and loaded.marketing_opt_out is True

    await use_case(user, SetMarketingOptOutDto(opted_out=False))
    loaded = await user_repository.find_by_id(user.id)
    assert loaded is not None and loaded.marketing_opt_out is False
    assert [(e.user_id, e.opted_out, e.source) for e in publisher.events] == [  # type: ignore[attr-defined]
        (user.id, True, "account"),
        (user.id, False, "account"),
    ]


async def test_unchanged_flag_publishes_nothing(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await user_repository.create(CreateUserDto(name="c", telegram_id=9902))
    publisher = RecordingEventPublisher()

    await SetMarketingOptOutUseCase(user_repository, uow, publisher)(
        user, SetMarketingOptOutDto(opted_out=False)
    )

    assert publisher.events == []
