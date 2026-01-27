from loguru import logger

from src.application.common import Interactor, Notifier, Redirect
from src.application.common.dao import UserDao
from src.application.dto import UserDto


class RedirectMenu(Interactor[int, None]):
    required_permission = None

    def __init__(
        self,
        user_dao: UserDao,
        redirect: Redirect,
        notifier: Notifier,
    ) -> None:
        self.user_dao = user_dao
        self.redirect = redirect
        self.notifier = notifier

    async def _execute(self, actor: UserDto, telegram_id: int) -> None:
        user = await self.user_dao.get_by_telegram_id(telegram_id)

        if user is None:
            logger.warning(f"User with telegram_id '{telegram_id}' not found for redirection")
            return

        if user.is_privileged:
            await self.notifier.notify_user(user, i18n_key="ntf-error.lost-context")
            logger.debug(f"Skipping redirection for privileged user '{telegram_id}'")
            return

        await self.notifier.notify_user(user, i18n_key="ntf-error.lost-context-restart")
        await self.redirect.to_main_menu(telegram_id)
