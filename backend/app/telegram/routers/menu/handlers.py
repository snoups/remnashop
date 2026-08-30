from aiogram import Router
from aiogram.enums import ContentType
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, Message
from dishka import FromDishka
from loguru import logger

from app.core.config import AppConfig
from app.core.enums import BannerName
from app.modules.banners import BannerRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto
from app.telegram.banners import get_banner

router = Router(name=__name__)


@router.message(CommandStart())
@router.message(Command("menu"))
async def on_menu(
    message: Message,
    user: UserDto,
    config: FromDishka[AppConfig],
    settings_repository: FromDishka[SettingsRepository],
    banner_repository: FromDishka[BannerRepository],
) -> None:
    # Test route only -- real main menu is an aiogram-dialog Window, not built yet.
    # `user` is populated by UserMiddleware (get-or-create), not looked up here.
    text = f"Главное меню (заглушка), {user.name}."
    settings = await settings_repository.get_bot_settings()

    if settings.banners_enabled:
        banner = await get_banner(
            banner_repository, config, BannerName.MENU, user.language, config.default_locale
        )
        if banner is not None:
            data, content_type = banner
            file = BufferedInputFile(data, filename=f"{BannerName.MENU}.bin")
            if content_type == ContentType.ANIMATION:
                await message.answer_animation(file, caption=text)
            else:
                await message.answer_photo(file, caption=text)
            return
        logger.warning(f"Banner '{BannerName.MENU}' not found, falling back to text-only")

    await message.answer(text)
