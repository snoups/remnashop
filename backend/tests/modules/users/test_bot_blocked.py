from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.modules.blacklist import BlacklistRepository
from app.modules.users import mark_bot_blocked
from app.modules.users.dto import CreateUserDto, RegisterTelegramUserDto, SetBotBlockedDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import RegisterTelegramUserUseCase, SetBotBlockedUseCase
from tests.fakes.events import RecordingEventPublisher


async def test_block_is_published_once_per_transition(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await user_repository.create(CreateUserDto(name="c", telegram_id=7701))
    publisher = RecordingEventPublisher()

    await mark_bot_blocked(user_repository, publisher, user.id)
    await mark_bot_blocked(user_repository, publisher, user.id)

    loaded = await user_repository.find_by_id(user.id)
    assert loaded is not None and loaded.is_bot_blocked is True
    assert [type(e).__name__ for e in publisher.events] == ["BotBlockedByUserEvent"]


async def test_chat_member_update_sets_and_clears_the_flag(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await user_repository.create(CreateUserDto(name="c", telegram_id=7702))
    publisher = RecordingEventPublisher()
    use_case = SetBotBlockedUseCase(user_repository, uow, publisher)

    await use_case.system(SetBotBlockedDto(telegram_id=7702, blocked=True))
    await use_case.system(SetBotBlockedDto(telegram_id=7702, blocked=False))
    await use_case.system(SetBotBlockedDto(telegram_id=7799, blocked=True))  # unknown

    loaded = await user_repository.find_by_id(user.id)
    assert loaded is not None and loaded.is_bot_blocked is False
    assert len(publisher.events) == 1


async def test_any_message_to_the_bot_clears_the_flag(
    user_repository: UserRepository, blacklist_repository: BlacklistRepository, uow: UnitOfWork
) -> None:
    user = await user_repository.create(CreateUserDto(name="Bob", telegram_id=7703))
    await user_repository.set_bot_blocked(user.id, True)
    use_case = RegisterTelegramUserUseCase(
        user_repository, blacklist_repository, uow, RecordingEventPublisher()
    )

    returned = await use_case.system(
        RegisterTelegramUserDto(telegram_id=7703, name="Bob", language=Locale.EN)
    )

    loaded = await user_repository.find_by_id(user.id)
    assert returned.is_bot_blocked is False
    assert loaded is not None and loaded.is_bot_blocked is False
