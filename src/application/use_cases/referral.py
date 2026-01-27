from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import UserDao
from src.application.dto import UserDto


class ValidateReferralCode(Interactor[str, bool]):
    required_permission = None

    def __init__(self, user_dao: UserDao) -> None:
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, referral_code: str) -> bool:
        referrer = await self.user_dao.get_by_referral_code(referral_code)
        if not referrer or referrer.telegram_id == actor.telegram_id:
            logger.warning(
                f"Invalid referral code '{referral_code}' or self-referral by '{actor.telegram_id}'"
            )
            return False
        return True
