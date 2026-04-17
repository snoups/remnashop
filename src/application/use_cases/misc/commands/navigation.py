from loguru import logger

from src.application.common import Interactor, Redirect
from src.application.common.dao import UserDao
from src.application.dto import UserDto


class RedirectMenu(Interactor[int, None]):
    required_permission = None

    def __init__(
        self,
        user_dao: UserDao,
        redirect: Redirect,
    ) -> None:
        self.user_dao = user_dao
        self.redirect = redirect

    async def _execute(self, actor: UserDto, telegram_id: int) -> None:
        user = await self.user_dao.get_by_telegram_id(telegram_id)

        if user is None:
            logger.warning(f"User with telegram_id '{telegram_id}' not found for redirection")
            return

        if user.is_privileged:
            logger.debug(f"Skipping redirection for privileged user '{telegram_id}'")
            return

        await self.redirect.to_main_menu(telegram_id)
