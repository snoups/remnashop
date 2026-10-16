from typing import Any
from unittest.mock import MagicMock

from app.modules.users import SetBotBlockedDto
from app.telegram.routers.bot_member.handlers import on_bot_blocked, on_bot_unblocked


class _SetBotBlocked:
    def __init__(self) -> None:
        self.calls: list[SetBotBlockedDto] = []

    @property
    def system(self) -> "_SetBotBlocked":
        return self

    async def __call__(self, data: SetBotBlockedDto) -> None:
        self.calls.append(data)


def _update(telegram_id: int) -> Any:
    return MagicMock(from_user=MagicMock(id=telegram_id))


async def test_kick_and_return_toggle_the_flag() -> None:
    use_case = _SetBotBlocked()

    await on_bot_blocked(_update(51), use_case)  # type: ignore[arg-type]
    await on_bot_unblocked(_update(51), use_case)  # type: ignore[arg-type]

    assert use_case.calls == [
        SetBotBlockedDto(telegram_id=51, blocked=True),
        SetBotBlockedDto(telegram_id=51, blocked=False),
    ]
