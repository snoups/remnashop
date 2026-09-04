from sqlalchemy import select

from app.core.db.models import DialogButton, DialogWindow
from app.core.enums import ButtonLinkType, DialogFlow, DialogWindowKind


async def test_window_with_buttons_round_trips(session) -> None:
    window = DialogWindow(
        key="menu.main",
        kind=DialogWindowKind.SEED,
        flow=DialogFlow.MENU,
        banner_name=None,
        default_snapshot={"buttons": []},
        buttons=[
            DialogButton(
                row=0,
                column=0,
                text_key="btn-menu.subscription",
                link_type=ButtonLinkType.NAVIGATE,
                target_window_key="subscription.main",
            )
        ],
    )
    session.add(window)
    await session.flush()
    await session.refresh(window)

    loaded = await session.scalar(select(DialogWindow).where(DialogWindow.key == "menu.main"))
    assert loaded is not None
    assert loaded.is_enabled is True
    assert loaded.position == 0
    assert len(loaded.buttons) == 1
    assert loaded.buttons[0].link_type == ButtonLinkType.NAVIGATE
    assert loaded.buttons[0].is_hidden is False


async def test_deleting_window_cascades_buttons(session) -> None:
    window = DialogWindow(
        key="custom.x",
        kind=DialogWindowKind.CUSTOM,
        flow=DialogFlow.CUSTOM,
        default_snapshot={},
        buttons=[
            DialogButton(
                row=0,
                column=0,
                text_key="k",
                link_type=ButtonLinkType.URL,
                url_value="https://example.com",
            )
        ],
    )
    session.add(window)
    await session.flush()
    await session.delete(window)
    await session.flush()
    assert (await session.scalars(select(DialogButton))).all() == []
