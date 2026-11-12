from unittest.mock import AsyncMock, MagicMock

from app.telegram.routers.referrals.inline import on_invite_query


def _query() -> MagicMock:
    query = MagicMock(answer=AsyncMock())
    query.from_user.id = 42
    return query


async def _run(query: MagicMock, *, user: object, enabled: bool = True, code: object = "ABC"):
    bot = MagicMock(me=AsyncMock(return_value=MagicMock(username="shop_bot", first_name="Shop")))
    runner = MagicMock(get=lambda key, **kwargs: key)
    await on_invite_query(
        query,
        bot,
        find_user=MagicMock(system=AsyncMock(return_value=user)),
        get_referral_settings=MagicMock(system=AsyncMock(return_value=MagicMock(enabled=enabled))),
        get_own_referral_stats=AsyncMock(return_value=MagicMock(referral_code=code)),
        i18n=MagicMock(get_translator_by_locale=MagicMock(return_value=runner)),
    )


async def test_invite_answers_with_the_message_and_the_referral_button() -> None:
    query = _query()

    await _run(query, user=MagicMock(is_blocked=False))

    [result] = query.answer.await_args.args[0]
    assert result.input_message_content.message_text == "inline-invite.message"
    assert result.reply_markup.inline_keyboard[0][0].url == "https://t.me/shop_bot?start=ref_ABC"


async def test_invite_answers_nothing_to_an_unknown_blocked_or_disabled_case() -> None:
    for kwargs in (
        {"user": None},
        {"user": MagicMock(is_blocked=True)},
        {"user": MagicMock(is_blocked=False), "enabled": False},
        {"user": MagicMock(is_blocked=False), "code": None},
    ):
        query = _query()
        await _run(query, **kwargs)  # type: ignore[arg-type]
        assert query.answer.await_args.args[0] == []
