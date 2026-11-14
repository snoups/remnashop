from aiogram import Bot, F, Router
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from dishka import FromDishka
from fluentogram import TranslatorHub

from app.core.constants import INLINE_INVITE_QUERY
from app.modules.referrals import GetOwnReferralStatsUseCase, GetReferralSettingsUseCase
from app.modules.users import FindTelegramUserUseCase
from app.telegram.dialogs.rendering import label_with_icon
from app.telegram.i18n import get_translator
from app.telegram.routers.referrals.getters import referral_url

router = Router(name=__name__)


@router.inline_query(F.query == INLINE_INVITE_QUERY)
async def on_invite_query(
    inline_query: InlineQuery,
    bot: Bot,
    find_user: FromDishka[FindTelegramUserUseCase],
    get_referral_settings: FromDishka[GetReferralSettingsUseCase],
    get_own_referral_stats: FromDishka[GetOwnReferralStatsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    # inline queries skip the user middleware: the account is looked up here
    user = await find_user.system(inline_query.from_user.id)
    if user is None or user.is_blocked or not (await get_referral_settings.system()).enabled:
        await inline_query.answer([], cache_time=0, is_personal=True)
        return
    stats = await get_own_referral_stats(user)
    me = await bot.me()
    if not stats.referral_code or not me.username:
        await inline_query.answer([], cache_time=0, is_personal=True)
        return
    runner = get_translator(i18n, user)
    url = referral_url(me.username, stats.referral_code)
    await inline_query.answer(
        [
            InlineQueryResultArticle(
                id=stats.referral_code,
                title=runner.get("inline-invite.title"),
                description=runner.get("inline-invite.description"),
                input_message_content=InputTextMessageContent(
                    message_text=runner.get("inline-invite.message", bot_name=me.first_name)
                ),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [label_with_icon(runner, "inline-invite.start").inline_button(url=url)]
                    ]
                ),
            )
        ],
        cache_time=0,
        is_personal=True,
    )
