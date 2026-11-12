import sys
from typing import Any

import pytest

from app.telegram import notice


@pytest.fixture(autouse=True)
def _plain_notices(monkeypatch: pytest.MonkeyPatch) -> None:
    # handlers are checked for what they say; the notice itself in test_notice.py
    async def _answer(event: Any, text: str, **kwargs: Any) -> None:
        await event.answer(text)

    for name, module in list(sys.modules.items()):
        if (
            name.startswith("app.telegram.")
            and module is not notice
            and getattr(module, "answer_notice", None) is notice.answer_notice
        ):
            monkeypatch.setattr(module, "answer_notice", _answer)
