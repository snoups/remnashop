from app.core.db.uow import UnitOfWork
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases.set_marketing_opt_out import SetMarketingOptOutUseCase


async def test_customer_toggles_own_flag(user_repository: UserRepository, uow: UnitOfWork) -> None:
    user = await user_repository.create(CreateUserDto(name="c", telegram_id=9901))
    use_case = SetMarketingOptOutUseCase(user_repository, uow)

    await use_case(user, True)
    loaded = await user_repository.get_by_id(user.id)
    assert loaded is not None and loaded.marketing_opt_out is True

    await use_case(user, False)
    loaded = await user_repository.get_by_id(user.id)
    assert loaded is not None and loaded.marketing_opt_out is False
