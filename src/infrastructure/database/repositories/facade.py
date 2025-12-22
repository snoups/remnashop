from sqlalchemy.ext.asyncio import AsyncSession

from .settings import SettingsRepository
from .user import UserRepository


class RepositoriesFacade:
    session: AsyncSession

    users: UserRepository
    settings: SettingsRepository

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self.users = UserRepository(session)
        self.settings = SettingsRepository(session)
