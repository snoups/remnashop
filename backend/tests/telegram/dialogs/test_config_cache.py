from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import BannerName, ButtonLinkType, DialogFlow
from app.modules.dialogs.dto import CreateCustomWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.telegram.dialogs.config_cache import DialogConfigCache

_SNAPSHOT = {
    "banner_name": "menu",
    "buttons": [
        {
            "key": "trial",
            "text_key": "btn-menu.trial",
            "row": 0,
            "column": 0,
            "link_type": "action",
            "action_key": "get_trial",
            "target_window_key": None,
            "url_value": None,
            "visibility_condition": None,
            "style": None,
            "icon_custom_emoji_id": None,
            "is_hidden": False,
        },
    ],
}


def _session_maker(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


async def test_get_window_lazy_loads(
    session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)

    cache = DialogConfigCache(_session_maker(session))
    window = await cache.get_window("menu.main")

    assert window.key == "menu.main"
    assert len(window.buttons) == 1
    assert window.buttons[0].link_type == ButtonLinkType.ACTION


async def test_get_button_finds_by_id(
    session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    cache = DialogConfigCache(_session_maker(session))
    window = await cache.get_window("menu.main")
    button_id = window.buttons[0].id

    found = await cache.get_button("menu.main", button_id)

    assert found is not None
    assert found.action_key == "get_trial"


async def test_get_button_missing_returns_none(
    session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    cache = DialogConfigCache(_session_maker(session))

    assert await cache.get_button("menu.main", 999999) is None
    assert await cache.get_button("no.such.window", 1) is None


async def test_custom_window_slot_comes_from_the_window_row(
    session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.create_custom_window(
        "custom.bbb", CreateCustomWindowDto(banner_name=None, position=0)
    )
    await dialog_repository.create_custom_window(
        "custom.aaa", CreateCustomWindowDto(banner_name=None, position=0)
    )
    cache = DialogConfigCache(_session_maker(session))

    # Slots are handed out on creation, so they follow creation order rather
    # than anything about the key itself.
    assert await cache.custom_window_slot("custom.bbb") == 0
    assert await cache.custom_window_slot("custom.aaa") == 1
    assert await cache.custom_window_slot("no.such.window") is None
    assert await cache.key_for_slot(0) == "custom.bbb"
    assert await cache.key_for_slot(49) is None


async def test_deleting_a_custom_window_leaves_the_others_where_they_were(
    session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    # The whole point of storing the slot: a user sitting in custom.ccc must not
    # get moved into a different window because an earlier one was deleted.
    for key in ("custom.aaa", "custom.bbb", "custom.ccc"):
        await dialog_repository.create_custom_window(
            key, CreateCustomWindowDto(banner_name=None, position=0)
        )
    await dialog_repository.delete_custom_window("custom.aaa")

    cache = DialogConfigCache(_session_maker(session))

    assert await cache.custom_window_slot("custom.bbb") == 1
    assert await cache.custom_window_slot("custom.ccc") == 2
    # ...and the freed slot is what the next window gets.
    await dialog_repository.create_custom_window(
        "custom.ddd", CreateCustomWindowDto(banner_name=None, position=0)
    )
    await cache.reload()
    assert await cache.custom_window_slot("custom.ddd") == 0
