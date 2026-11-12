from unittest.mock import MagicMock

from app.telegram.routers.purchase import dialog


async def test_badged_plans_get_a_colored_button() -> None:
    data = {
        "plans": [
            {"id": 1, "label": "Plain", "badge": ""},
            {"id": 2, "label": "Best", "badge": "BEST_VALUE"},
            {"id": 3, "label": "Popular", "badge": "POPULAR"},
        ],
        "back_text": "Back",
    }

    keyboard = await dialog.plan.keyboard.render_keyboard(data, MagicMock())

    styles = {button.text: button.style for row in keyboard for button in row}
    assert styles == {"Plain": None, "Best": "primary", "Popular": "success", "Back": None}
